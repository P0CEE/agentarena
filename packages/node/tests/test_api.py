"""L'API HTTP d'un node, testée en ASGI sans socket."""

import asyncio

import httpx
from conftest import CLIENT, STAKE, VALIDATORS, DirectTransport

from arena_chain.genesis import make_genesis
from arena_chain.tx import make_tx

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
