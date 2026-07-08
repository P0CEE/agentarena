"""Mini-réseau en mémoire pour piloter des manches complètes bloc par bloc."""

import arena_chain  # noqa: F401  — enregistre les handlers de manche et les hooks
from arena_chain.genesis import make_genesis
from arena_chain.state import seal_block
from arena_chain.tx import make_tx
from arena_chain.wallet import Wallet

# 12 wallets deterministes : sponsor + 10 agents + 1 denonciateur externe.
WALLETS = [Wallet.from_seed(bytes([i]) * 32) for i in range(12)]
SPONSOR = WALLETS[0]
AGENTS = WALLETS[1:11]
REPORTER = WALLETS[11]

FUNDING = 1_000_000


class Net:
    """Une chaîne en mémoire : seal_block successifs, nonces suivis par wallet."""

    def __init__(self) -> None:
        allocations = {w.address: FUNDING for w in WALLETS}
        self.state, genesis = make_genesis(allocations)
        self.header = genesis["header"]
        self.blocks = [genesis]
        self.nonces: dict[str, int] = {}

    def build(self, wallet: Wallet, payload: dict) -> dict:
        """Construit une tx au nonce courant SANS le consommer (pour les rejets)."""
        return make_tx(wallet, self.nonces.get(wallet.address, 0), payload)

    def send(self, wallet: Wallet, payload: dict) -> dict:
        tx = self.build(wallet, payload)
        self.nonces[wallet.address] = tx["nonce"] + 1
        return tx

    def tick(self, txs: list[dict] | None = None) -> dict:
        new_state, block = seal_block(
            self.state, self.header, txs or [], proposer="test", round_=0
        )
        self.state = new_state
        self.header = block["header"]
        self.blocks.append(block)
        return block

    def until(self, height: int) -> None:
        while self.header["height"] < height:
            self.tick()


def net_with_agents() -> Net:
    """Un réseau où les 10 agents sont enregistrés (stake débité)."""
    net = Net()
    net.tick([net.send(w, {"type": "register_agent", "stake": 10_000}) for w in AGENTS])
    return net


def supply(net: Net) -> int:
    """Masse monétaire totale : rien ne se crée, rien ne se perd."""
    data = net.state.data
    return (
        sum(account["balance"] for account in data["accounts"].values())
        + sum(stake["free"] + stake["locked"] for stake in data["stakes"].values())
        + sum(
            task["prize"] for task in data["tasks"].values() if task["state"] != "SETTLED"
        )
        + data["treasury"]
    )
