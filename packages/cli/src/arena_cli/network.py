"""Répertoire réseau (.arena) : genesis partagé, configs des nodes, process.

Les seeds des wallets sont stockées en clair dans ce répertoire : c'est un
réseau de démo locale, jamais un déploiement réel.
"""

import json
import os
import secrets
import signal
import subprocess
import sys
import time
from pathlib import Path

from arena_chain.wallet import Wallet

FUNDING_AGENT = 1_000_000
FUNDING_SPONSOR = 10_000_000
STAKE = 10_000


def load_dotenv(path: Path = Path(".env")) -> None:
    """Charge un .env minimal (KEY=VALUE) sans écraser l'environnement."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def network_path(directory: Path) -> Path:
    return directory / "network.json"


def load_network(directory: Path) -> dict:
    path = network_path(directory)
    if not path.exists():
        raise FileNotFoundError(f"pas de reseau dans {directory} (lance `arena init`)")
    return json.loads(path.read_text())


def create_network(
    directory: Path, nodes: int, agent_kind: str, block_time: float, base_port: int
) -> dict:
    """Génère wallets, genesis commun et une config par node."""
    seeds = [secrets.token_bytes(32) for _ in range(nodes)]
    wallets = [Wallet.from_seed(seed) for seed in seeds]
    sponsor_seed = secrets.token_bytes(32)
    sponsor = Wallet.from_seed(sponsor_seed)

    allocations = {w.address: FUNDING_AGENT for w in wallets}
    allocations[sponsor.address] = FUNDING_SPONSOR
    agents = {w.address: STAKE for w in wallets}
    ports = [base_port + i for i in range(nodes)]
    urls = [f"http://127.0.0.1:{port}" for port in ports]

    (directory / "nodes").mkdir(parents=True)
    (directory / "logs").mkdir()
    (directory / "pids").mkdir()
    for i, (wallet, seed, port) in enumerate(zip(wallets, seeds, ports)):
        config = {
            "seed": seed.hex(),
            "port": port,
            "peers": [url for j, url in enumerate(urls) if j != i],
            "genesis": {"allocations": allocations, "agents": agents},
            "agent": {"kind": agent_kind},
            "block_time": block_time,
        }
        (directory / "nodes" / f"node-{i}.json").write_text(json.dumps(config, indent=2))

    network = {
        "agent": agent_kind,
        "block_time": block_time,
        "sponsor": sponsor.address,
        "nodes": [
            {"name": f"node-{i}", "port": port, "url": url, "address": wallet.address}
            for i, (wallet, port, url) in enumerate(zip(wallets, ports, urls))
        ],
    }
    network_path(directory).write_text(json.dumps(network, indent=2))
    (directory / "sponsor.json").write_text(
        json.dumps({"seed": sponsor_seed.hex(), "address": sponsor.address})
    )
    return network


def sponsor_wallet(directory: Path) -> Wallet:
    data = json.loads((directory / "sponsor.json").read_text())
    return Wallet.from_seed(bytes.fromhex(data["seed"]))


def node_names(network: dict) -> dict[str, str]:
    return {entry["address"]: entry["name"] for entry in network["nodes"]}


# --- controle des process ---


def _pid_path(directory: Path, name: str) -> Path:
    return directory / "pids" / f"{name}.pid"


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def running_nodes(directory: Path, network: dict) -> dict[str, int]:
    """name -> pid des nodes effectivement vivants."""
    result = {}
    for entry in network["nodes"]:
        path = _pid_path(directory, entry["name"])
        if path.exists():
            pid = int(path.read_text())
            if _alive(pid):
                result[entry["name"]] = pid
            else:
                path.unlink()  # pid perime
    return result

def start_nodes(directory: Path, network: dict) -> list[str]:
    """Lance les nodes manquants en process detaches. Retourne les noms lances."""
    already = running_nodes(directory, network)
    started = []
    for entry in network["nodes"]:
        name = entry["name"]
        if name in already:
            continue
        config = directory / "nodes" / f"{name}.json"
        log = open(directory / "logs" / f"{name}.log", "ab")
        process = subprocess.Popen(
            [sys.executable, "-m", "arena_node", str(config)],
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        _pid_path(directory, name).write_text(str(process.pid))
        started.append(name)
    return started


def stop_nodes(directory: Path, network: dict) -> list[str]:
    """Arrête les nodes vivants (SIGTERM puis SIGKILL). Retourne les noms arrêtés."""
    stopped = []
    alive = running_nodes(directory, network)
    for name, pid in alive.items():
        os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + 3.0
    for name, pid in alive.items():
        while _alive(pid) and time.monotonic() < deadline:
            time.sleep(0.1)
        if _alive(pid):
            os.kill(pid, signal.SIGKILL)
        _pid_path(directory, name).unlink(missing_ok=True)
        stopped.append(name)
    return stopped
