"""Lance un node depuis un fichier de config JSON (généré par le CLI, étape 7).

Config attendue :
{
  "seed": "<64 hex>", "port": 8001, "peers": ["http://127.0.0.1:8002", ...],
  "genesis": {"allocations": {addr: int}, "agents": {addr: int}},
  "block_time": 2.0, "round_timeout": 8.0
}
"""

import uvicorn

from arena_chain.genesis import make_genesis
from arena_chain.params import BLOCK_TIME_S
from arena_chain.wallet import Wallet

from arena_node.engine import Engine
from arena_node.server import create_app
from arena_node.transport import HttpTransport


def build_engine(config: dict, transport=None) -> Engine:
    wallet = Wallet.from_seed(bytes.fromhex(config["seed"]))
    genesis = config["genesis"]
    state, genesis_block = make_genesis(
        {addr: int(v) for addr, v in genesis["allocations"].items()},
        {addr: int(v) for addr, v in genesis.get("agents", {}).items()},
    )
    return Engine(
        wallet,
        state,
        genesis_block,
        peers=list(config.get("peers", [])),
        transport=transport or HttpTransport(),
        block_time=float(config.get("block_time", BLOCK_TIME_S)),
        round_timeout=float(config.get("round_timeout", 8.0)),
    )


def run_node(config: dict) -> None:
    engine = build_engine(config)
    app = create_app(engine, run_engine=True)
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(config["port"]),
        log_level=config.get("log_level", "warning"),
    )
