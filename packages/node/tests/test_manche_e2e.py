"""E2E : 10 nodes + 10 runners d'agents stub jouent une manche entière seuls.

Le sponsor poste create_task ; la sortition désigne 3 builders et 7 juges ;
chaque runner observe la chaîne et joue son rôle (build, commit, reveal,
judge, notes) sans aucune intervention — jusqu'au règlement Yuma.
"""

import asyncio

from conftest import CLIENT, FUNDING, STAKE, DirectTransport, advance

from arena_agents.runner import AgentRunner
from arena_agents.stub import StubAgent
from arena_chain.genesis import make_genesis
from arena_chain.params import JUDGE_RESERVE_PCT
from arena_chain.tx import make_tx
from arena_chain.wallet import Wallet

from arena_node.engine import Engine

AGENTS10 = [Wallet.from_seed(bytes([150 + i]) * 32) for i in range(10)]
PRIZE = 50_000


class FailingBuilder(StubAgent):
    async def build(self, task_id: str, brief: str) -> str:
        raise RuntimeError("LLM en panne")


def make_manche_cluster() -> tuple[dict[str, Engine], dict[str, AgentRunner]]:
    allocations = {w.address: FUNDING for w in [*AGENTS10, CLIENT]}
    agents = {w.address: STAKE for w in AGENTS10}
    registry: dict[str, Engine] = {}
    transport = DirectTransport(registry)
    runners: dict[str, AgentRunner] = {}
    for wallet in AGENTS10:
        state, genesis_block = make_genesis(allocations, agents)
        engine = Engine(
            wallet,
            state,
            genesis_block,
            peers=[w.address for w in AGENTS10 if w.address != wallet.address],
            transport=transport,
            block_time=0.0,
            round_timeout=10_000.0,
        )
        registry[wallet.address] = engine
        runners[wallet.address] = AgentRunner(engine, wallet, StubAgent(wallet.address))
    return registry, runners


async def play(cluster: dict[str, Engine], runners: dict[str, AgentRunner]) -> dict:
    """Avance la chaîne, les runners jouent, jusqu'au règlement de task-1."""
    reference = next(iter(cluster.values()))
    for _ in range(70):
        for runner in runners.values():
            await runner.step()
            await runner.drain()  # les agents stub sont instantanes
        await advance(cluster)
        task = reference.state.data["tasks"].get("task-1")
        if task is not None and task["state"] == "SETTLED":
            return task
    raise AssertionError("manche non reglee apres 70 blocs")


def test_manche_autonome_de_bout_en_bout() -> None:
    async def scenario():
        cluster, runners = make_manche_cluster()
        reference = next(iter(cluster.values()))
        create = make_tx(
            CLIENT, 0, {"type": "create_task", "task": "task-1", "prize": PRIZE,
                        "brief": "ecris une fonction is_prime en python"},
        )
        await reference.handle_tx(create)

        task = await play(cluster, runners)

        result = task["result"]
        assert "aborted" not in result
        assert len(result["builders"]) == 3  # les 3 builders ont produit et revele
        assert len(result["judges"]) == 7  # les 7 juges ont note
        reserve = PRIZE * JUDGE_RESERVE_PCT // 100
        assert sum(result["payouts"]["builders"].values()) == PRIZE - reserve
        assert sum(result["payouts"]["judges"].values()) == reserve
        # Tous les nodes ont exactement le meme state final.
        assert len({engine.state.root() for engine in cluster.values()}) == 1

    asyncio.run(scenario())


def test_builder_en_panne_manche_aboutit_quand_meme() -> None:
    async def scenario():
        cluster, runners = make_manche_cluster()
        reference = next(iter(cluster.values()))
        create = make_tx(
            CLIENT, 0, {"type": "create_task", "task": "task-1", "prize": PRIZE,
                        "brief": "ecris une fonction fibonacci"},
        )
        await reference.handle_tx(create)
        await advance(cluster)  # la task est creee, la sortition est connue

        failed = reference.state.data["tasks"]["task-1"]["builders"][0]
        runners[failed].agent = FailingBuilder(failed)  # son LLM tombe en panne

        task = await play(cluster, runners)

        result = task["result"]
        assert "aborted" not in result
        assert failed not in result["builders"]  # il n'a rien rendu
        assert len(result["builders"]) == 2  # la manche aboutit avec les 2 autres
        # Le no-show a coute une offense (grace au 1er incident), pas de jail.
        agent = reference.state.data["agents"][failed]
        assert agent["offenses"] == 1
        assert agent["jailed_until"] == 0

    asyncio.run(scenario())
