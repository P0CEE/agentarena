"""L'API HTTP d'un node, testée en ASGI sans socket."""

import asyncio

import httpx
from conftest import CLIENT, STAKE, VALIDATORS, DirectTransport

from arena_chain.genesis import make_genesis
from arena_chain.tx import make_tx, txid

from arena_node.engine import Engine
from arena_node.server import create_app


def single_node() -> Engine:
    # Un validateur unique detient 100% du stake : quorum immediat.
    wallet = VALIDATORS[0]
    allocations = {wallet.address: 1_000_000, CLIENT.address: 1_000_000}
    state, genesis_block = make_genesis(allocations, {wallet.address: STAKE})
    return Engine(wallet, state, genesis_block, peers=[], transport=DirectTransport({}),
                  block_time=0.0, round_timeout=10_000.0)


def test_api_de_lecture_et_soumission() -> None:
    async def scenario():
        engine = single_node()
        app = create_app(engine)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://node") as client:
            status = (await client.get("/status")).json()
            assert status["height"] == 0
            assert status["validators"] == 1
            assert status["proposer_next"] is True

            tx = make_tx(CLIENT, 0, {"type": "transfer", "to": "d" * 40, "amount": 7})
            response = await client.post("/tx", json=tx)
            assert response.status_code == 200

            await engine.propose_if_leader()  # finalise le bloc 1

            blocks = (await client.get("/blocks", params={"from": 0})).json()["blocks"]
            assert len(blocks) == 2  # genesis + bloc 1
            assert blocks[1]["block"]["header"]["height"] == 1
            assert len(blocks[1]["qc"]) == 1
            assert blocks[1]["hash"] and blocks[1]["txids"] == [txid(tx)]
            assert blocks[1]["block"]["header"]["prev_hash"] == blocks[0]["hash"]

            headers = (await client.get("/chain")).json()["headers"]
            assert headers[-1]["height"] == 1

            agents = (await client.get("/agents")).json()["agents"]
            assert agents[engine.wallet.address]["free"] == STAKE

            assert (await client.get("/tasks")).json() == {"tasks": {}}
            assert (await client.get("/tasks/inconnue")).status_code == 404

    asyncio.run(scenario())


def test_tx_invalide_rejetee_en_400() -> None:
    async def scenario():
        engine = single_node()
        app = create_app(engine)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://node") as client:
            tx = make_tx(CLIENT, 0, {"type": "transfer", "to": "d" * 40, "amount": 7})
            tx["signature"] = "0" * 128
            response = await client.post("/tx", json=tx)
            assert response.status_code == 400
            assert "signature" in response.json()["detail"]

    asyncio.run(scenario())


def test_transactions_new_transfer_custodial_applique() -> None:
    async def scenario():
        engine = single_node()
        app = create_app(engine, sponsor_wallet=CLIENT)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://node") as client:
            dest = "d" * 40
            # sender omis : le sponsor signe par defaut
            response = await client.post(
                "/transactions/new", json={"recipient": dest, "amount": 250}
            )
            assert response.status_code == 201
            assert response.json()["block_pending"] is True

            # sender explicite dont le node detient la seed (son propre wallet)
            explicit = await client.post(
                "/transactions/new",
                json={"sender": engine.wallet.address, "recipient": dest, "amount": 50},
            )
            assert explicit.status_code == 201

            await engine.propose_if_leader()  # finalise le bloc 1

            account = (await client.get(f"/accounts/{dest}")).json()
            assert account["balance"] == 300

    asyncio.run(scenario())


def test_transactions_new_rejets_en_400() -> None:
    async def scenario():
        engine = single_node()
        app = create_app(engine, sponsor_wallet=CLIENT)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://node") as client:
            dest = "d" * 40
            negatif = await client.post(
                "/transactions/new", json={"recipient": dest, "amount": -5}
            )
            assert negatif.status_code == 400
            assert "positif" in negatif.json()["detail"]

            insuffisant = await client.post(
                "/transactions/new", json={"recipient": dest, "amount": 2_000_000}
            )
            assert insuffisant.status_code == 400
            assert "solde insuffisant" in insuffisant.json()["detail"]

            inconnu = await client.post(
                "/transactions/new",
                json={"sender": "a" * 40, "recipient": dest, "amount": 5},
            )
            assert inconnu.status_code == 400
            assert "ne detient pas la seed" in inconnu.json()["detail"]

    asyncio.run(scenario())


def test_transactions_new_sans_sponsor_exige_sender() -> None:
    async def scenario():
        engine = single_node()
        app = create_app(engine)  # pas de wallet sponsor sur ce node
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://node") as client:
            response = await client.post(
                "/transactions/new", json={"recipient": "d" * 40, "amount": 5}
            )
            assert response.status_code == 400
            assert "sponsor" in response.json()["detail"]

    asyncio.run(scenario())


def test_mine_attend_et_retourne_le_bloc_avec_la_tx() -> None:
    async def scenario():
        engine = single_node()
        app = create_app(engine, sponsor_wallet=CLIENT)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://node") as client:
            posted = await client.post(
                "/transactions/new", json={"recipient": "d" * 40, "amount": 9}
            )
            tid = posted.json()["txid"]

            request = asyncio.create_task(client.get("/mine"))
            while not engine.subscribers:  # /mine doit etre abonne avant le bloc
                await asyncio.sleep(0)
            await engine.propose_if_leader()  # finalise le bloc 1

            response = await request
            assert response.status_code == 200
            body = response.json()
            assert body["block"]["header"]["height"] == 1
            assert tid in [txid(tx) for tx in body["block"]["txs"]]
            assert tid in body["txids"] and body["hash"]
            assert body["consensus"]["proposer"] == engine.wallet.address
            assert body["consensus"]["round"] == 0
            assert body["consensus"]["voters"] == [engine.wallet.address]

    asyncio.run(scenario())


def test_mine_504_si_le_reseau_est_halte() -> None:
    async def scenario():
        # Personne n'appelle propose_if_leader : aucun bloc ne sera finalise.
        wallet = VALIDATORS[0]
        allocations = {wallet.address: 1_000_000, CLIENT.address: 1_000_000}
        state, genesis_block = make_genesis(allocations, {wallet.address: STAKE})
        engine = Engine(wallet, state, genesis_block, peers=[], transport=DirectTransport({}),
                        block_time=0.0, round_timeout=0.01)
        app = create_app(engine)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://node") as client:
            response = await client.get("/mine")
            assert response.status_code == 504
            assert "halte" in response.json()["detail"]
            assert engine.subscribers == []  # la file d'attente est bien desabonnee

    asyncio.run(scenario())


def test_nodes_register_catch_up_et_convergence() -> None:
    async def scenario():
        # A (seul validateur) produit des blocs ; B partage le genesis mais
        # demarre isole : les deux chaines sont en desaccord.
        registry: dict[str, Engine] = {}
        transport = DirectTransport(registry)
        wallet_a, wallet_b = VALIDATORS[0], VALIDATORS[1]
        allocations = {
            wallet_a.address: 1_000_000,
            wallet_b.address: 1_000_000,
            CLIENT.address: 1_000_000,
        }
        agents = {wallet_a.address: STAKE}

        def build(wallet):
            state, genesis_block = make_genesis(allocations, agents)
            return Engine(wallet, state, genesis_block, peers=[], transport=transport,
                          block_time=0.0, round_timeout=10_000.0)

        engine_a, engine_b = build(wallet_a), build(wallet_b)
        registry["http://node-a"] = engine_a
        registry["http://node-b"] = engine_b

        await engine_a.handle_tx(make_tx(CLIENT, 0, {"type": "transfer", "to": "d" * 40, "amount": 3}))
        await engine_a.propose_if_leader()
        await engine_a.propose_if_leader()
        assert engine_a.height == 2 and engine_b.height == 0

        app = create_app(engine_b)
        asgi = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=asgi, base_url="http://node-b") as client:
            assert (await client.post("/nodes/register", json={"url": "ftp://x"})).status_code == 400

            mort = await client.post("/nodes/register", json={"url": "http://mort"})
            assert mort.status_code == 400
            assert "injoignable" in mort.json()["detail"]

            soi = await client.post("/nodes/register", json={"url": "http://node-b"})
            assert soi.status_code == 400
            assert "lui-meme" in soi.json()["detail"]

            ok = await client.post("/nodes/register", json={"url": "http://node-a"})
            assert ok.status_code == 200
            assert ok.json()["peers"] == ["http://node-a"]
            assert engine_b.behind is True

            again = await client.post("/nodes/register", json={"url": "http://node-a"})
            assert again.json()["peers"] == ["http://node-a"]  # idempotent

            await engine_b.sync()  # ce que fait la boucle run quand behind est leve
            assert engine_b.height == engine_a.height == 2
            assert engine_b.state.root() == engine_a.state.root()

            assert (await client.get("/nodes")).json()["peers"] == ["http://node-a"]

    asyncio.run(scenario())


def test_endpoint_sponsor_cree_une_task() -> None:
    async def scenario():
        # La sortition exige 10 agents eligibles, mais l'engine unique doit
        # proposer ET atteindre le quorum seul : il detient >2/3 du stake.
        from test_manche_e2e import AGENTS10

        wallet = AGENTS10[0]
        allocations = {w.address: 1_000_000 for w in AGENTS10} | {CLIENT.address: 1_000_000}
        agents = {w.address: 1 for w in AGENTS10}
        agents[wallet.address] = 1_000_000
        state, genesis_block = make_genesis(allocations, agents)
        engine = Engine(wallet, state, genesis_block, peers=[], transport=DirectTransport({}),
                        block_time=0.0, round_timeout=10_000.0)
        app = create_app(engine, sponsor_wallet=CLIENT)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://node") as client:
            bad = await client.post("/sponsor/tasks", json={"brief": "b", "prize": 1})
            assert bad.status_code == 400  # MIN_PRICE rejete immediatement, pas au seal
            assert "MIN_PRICE" in bad.json()["detail"]

            ok = await client.post(
                "/sponsor/tasks", json={"brief": "fais une todo-list", "prize": 50_000}
            )
            assert ok.status_code == 200
            task_id = ok.json()["task"]
            await engine.propose_if_leader()
            assert task_id in engine.state.data["tasks"]

    asyncio.run(scenario())


def test_evenements_sse_publies() -> None:
    async def scenario():
        engine = single_node()
        queue = engine.subscribe()
        await engine.propose_if_leader()
        event = queue.get_nowait()
        assert event["type"] == "block"
        assert event["height"] == 1

    asyncio.run(scenario())
