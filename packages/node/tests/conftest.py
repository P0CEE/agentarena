"""Cluster d'engines en mémoire : le consensus sans sockets, déterministe."""

from arena_chain.errors import ChainError
from arena_chain.genesis import make_genesis
from arena_chain.wallet import Wallet

from arena_node.engine import Engine

VALIDATORS = [Wallet.from_seed(bytes([100 + i]) * 32) for i in range(4)]
CLIENT = Wallet.from_seed(bytes([99]) * 32)
STAKE = 10_000
FUNDING = 1_000_000


class DirectTransport:
    """Livre les messages en appelant directement les engines du registre.

    Un peer absent du registre est un node mort : le message est perdu,
    exactement comme en HTTP.
    """

    def __init__(self, registry: dict[str, Engine]) -> None:
        self.registry = registry

    async def send(self, peer: str, path: str, payload: dict) -> None:
        engine = self.registry.get(peer)
        if engine is None:
            return
        try:
            if path == "/consensus/proposal":
                await engine.handle_proposal(payload)
            elif path == "/consensus/vote":
                await engine.handle_vote(payload)
            elif path == "/consensus/timeout":
                await engine.handle_timeout(payload)
            elif path == "/tx":
                await engine.handle_tx(payload)
        except ChainError:
            pass  # un message invalide ne fait pas tomber l'emetteur

    async def fetch_blocks(self, peer: str, from_height: int) -> list[dict]:
        engine = self.registry.get(peer)
        if engine is None:
            raise ConnectionError(f"peer mort: {peer}")
        return engine.blocks[from_height:]

    async def probe(self, peer: str) -> dict:
        engine = self.registry.get(peer)
        if engine is None:
            raise ConnectionError(f"peer mort: {peer}")
        return {"address": engine.wallet.address}


def make_cluster(n: int = 4) -> dict[str, Engine]:
    """n engines partageant le même genesis, reliés par un DirectTransport."""
    wallets = VALIDATORS[:n]
    allocations = {w.address: FUNDING for w in [*wallets, CLIENT]}
    agents = {w.address: STAKE for w in wallets}
    registry: dict[str, Engine] = {}
    transport = DirectTransport(registry)
    for wallet in wallets:
        state, genesis_block = make_genesis(allocations, agents)
        registry[wallet.address] = Engine(
            wallet,
            state,
            genesis_block,
            peers=[w.address for w in wallets if w.address != wallet.address],
            transport=transport,
            block_time=0.0,  # tests : pas de cadence
            round_timeout=10_000.0,  # tests : timeouts declenches manuellement
        )
    return registry


def leader_of(cluster: dict[str, Engine]) -> Engine:
    any_engine = next(iter(cluster.values()))
    for engine in cluster.values():
        if engine.is_proposer():
            return engine
    raise AssertionError(f"aucun leader vivant pour h={any_engine.next_height}")


async def advance(cluster: dict[str, Engine]) -> None:
    """Finalise une hauteur ; si le leader est mort, les vivants passent le round."""
    reference = next(iter(cluster.values()))
    target = reference.next_height
    for _ in range(10):
        live_leader = next((e for e in cluster.values() if e.is_proposer()), None)
        if live_leader is not None:
            await live_leader.propose_if_leader()
            if reference.height >= target:
                return
        else:
            for engine in list(cluster.values()):
                await engine.fire_timeout()
    raise AssertionError("hauteur non finalisee apres 10 tentatives")
