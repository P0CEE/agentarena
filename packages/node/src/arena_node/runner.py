"""Lance un node depuis un fichier de config JSON (généré par le CLI, étape 7).

Config attendue :
{
  "seed": "<64 hex>", "port": 8001, "peers": ["http://127.0.0.1:8002", ...],
  "genesis": {"allocations": {addr: int}, "agents": {addr: int}},
  "agent": {"kind": "stub" | "mistral", "model": "...", "timeout_s": 30},
  "block_time": 2.0, "round_timeout": 8.0
}
L'agent mistral lit MISTRAL_API_KEY dans l'environnement (jamais dans la config).
"""

import os

import uvicorn

from arena_agents.base import Agent
from arena_agents.mistral import MistralAgent
from arena_agents.runner import AgentRunner
from arena_agents.stub import StubAgent
from arena_chain.genesis import make_genesis
from arena_chain.params import BLOCK_TIME_S
from arena_chain.wallet import Wallet

from arena_node.engine import Engine
from arena_node.server import create_app
from arena_node.transport import HttpTransport


def build_node(config: dict, transport=None) -> tuple[Engine, AgentRunner, Wallet | None]:
    wallet = Wallet.from_seed(bytes.fromhex(config["seed"]))
    genesis = config["genesis"]
    state, genesis_block = make_genesis(
        {addr: int(v) for addr, v in genesis["allocations"].items()},
        {addr: int(v) for addr, v in genesis.get("agents", {}).items()},
    )
    engine = Engine(
        wallet,
        state,
        genesis_block,
        peers=list(config.get("peers", [])),
        transport=transport or HttpTransport(),
        block_time=float(config.get("block_time", BLOCK_TIME_S)),
        round_timeout=float(config.get("round_timeout", 8.0)),
    )
    agent = _build_agent(config.get("agent", {}), wallet.address)
    sponsor = config.get("sponsor_seed")
    sponsor_wallet = Wallet.from_seed(bytes.fromhex(sponsor)) if sponsor else None
    return engine, AgentRunner(engine, wallet, agent), sponsor_wallet


def _build_agent(config: dict, address: str) -> Agent:
    kind = config.get("kind", "stub")
    if kind == "mistral":
        api_key = os.environ.get("MISTRAL_API_KEY", "")
        if not api_key:
            raise RuntimeError("MISTRAL_API_KEY manquante pour un agent mistral (ADR-0001)")
        return MistralAgent(
            api_key,
            model=config.get("model", "mistral-small-latest"),
            timeout_s=float(config.get("timeout_s", 30)),
        )
    if kind != "stub":
        raise RuntimeError(f"kind d'agent inconnu: {kind}")
    return StubAgent(address)


def run_node(config: dict) -> None:
    engine, agent_runner, sponsor_wallet = build_node(config)
    app = create_app(
        engine, run_engine=True, agent_runner=agent_runner, sponsor_wallet=sponsor_wallet
    )
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(config["port"]),
        log_level=config.get("log_level", "warning"),
    )
