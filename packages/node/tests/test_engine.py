"""Scénarios BFT : finalité, tolérance aux pannes, halt, catch-up, gossip."""

import asyncio

from conftest import CLIENT, VALIDATORS, advance, leader_of, make_cluster

from arena_chain.tx import make_tx


def run(coro) -> None:
    asyncio.run(coro)


def test_quatre_nodes_finalisent_des_blocs() -> None:
    async def scenario():
        cluster = make_cluster()
        for _ in range(3):
            await leader_of(cluster).propose_if_leader()
        assert all(engine.height == 3 for engine in cluster.values())
        roots = {engine.state.root() for engine in cluster.values()}
        assert len(roots) == 1  # tous les nodes ont exactement le meme state

    run(scenario())


def test_une_tx_gossipee_traverse_le_reseau() -> None:
    async def scenario():
        cluster = make_cluster()
        first = next(iter(cluster.values()))
        tx = make_tx(CLIENT, 0, {"type": "transfer", "to": "d" * 40, "amount": 42})
        await first.handle_tx(tx)  # gossip idempotent vers tous les peers
        assert all(len(engine.mempool) == 1 for engine in cluster.values())

        await leader_of(cluster).propose_if_leader()
        assert all(engine.state.balance("d" * 40) == 42 for engine in cluster.values())
        assert all(len(engine.mempool) == 0 for engine in cluster.values())

    run(scenario())


def test_un_node_mort_sur_quatre_le_reseau_continue() -> None:
    async def scenario():
        cluster = make_cluster()
        dead = leader_of(cluster)  # le pire cas : c'est le leader qui meurt
        del cluster[dead.wallet.address]

        # Pacemaker : les 3 vivants (3/4 > 2/3) votent le timeout -> round + 1.
        for engine in cluster.values():
            await engine.fire_timeout()
        assert all(engine.round == 1 for engine in cluster.values())

        await leader_of(cluster).propose_if_leader()
        assert all(engine.height == 1 for engine in cluster.values())

    run(scenario())


def test_deux_nodes_morts_sur_quatre_la_chaine_s_arrete() -> None:
    async def scenario():
        cluster = make_cluster()
        survivors = dict(list(cluster.items())[:2])
        for addr in list(cluster):
            if addr not in survivors:
                del cluster[addr]

        # 2/4 du stake : ni bloc final, ni changement de round possible.
        for engine in survivors.values():
            await engine.propose_if_leader()
            await engine.fire_timeout()
        assert all(engine.height == 0 for engine in survivors.values())
        assert all(engine.round == 0 for engine in survivors.values())
        # La surete avant la liveness : comportement BFT correct.

    run(scenario())


def test_catch_up_d_un_node_en_retard() -> None:
    async def scenario():
        cluster = make_cluster()
        late = cluster[VALIDATORS[3].address]
        del cluster[late.wallet.address]  # il rate 3 blocs

        for _ in range(3):
            await advance(cluster)  # si le mort est leader, timeout puis round suivant
        assert late.height == 0

        cluster[late.wallet.address] = late  # il revient et se synchronise
        await late.sync()
        assert late.height == 3
        reference = next(iter(cluster.values()))
        assert late.state.root() == reference.state.root()
        assert late.last_header == reference.last_header  # rejeu : memes hashes

    run(scenario())


def test_proposal_d_un_proposer_illegitime_ignoree() -> None:
    async def scenario():
        cluster = make_cluster()
        engines = list(cluster.values())
        impostor = next(e for e in engines if not e.is_proposer())
        # Il force une proposition alors que ce n'est pas son tour.
        from arena_chain.state import seal_block

        _, block = seal_block(
            impostor.state, impostor.last_header, [], impostor.wallet.address, 0
        )
        victim = next(e for e in engines if e is not impostor)
        await victim.handle_proposal(block)
        assert victim.height == 0
        assert not victim.votes  # personne ne vote pour un imposteur

    run(scenario())
