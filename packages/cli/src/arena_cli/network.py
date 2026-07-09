"""Répertoire réseau (.arena) : genesis partagé, configs des nodes, process.

Les seeds des wallets sont stockées en clair dans ce répertoire : c'est un
réseau de démo locale, jamais un déploiement réel.
"""

import json
import os
import re
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
    # Timestamp du genesis fixe ici, une fois : chaque node le reconstruit depuis
    # sa config, une valeur differente forkerait le reseau au bloc 0.
    genesis_timestamp = int(time.time() * 1000)
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
            "genesis": {
                "allocations": allocations,
                "agents": agents,
                "timestamp": genesis_timestamp,
            },
            "agent": {"kind": agent_kind},
            "block_time": block_time,
        }
        if i == 0:  # le node de reference signe les create_task du dashboard
            config["sponsor_seed"] = sponsor_seed.hex()
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
            stdin=subprocess.DEVNULL,
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
        # Flux mono-process (`arena` racine) : les nodes sont nos enfants, un node
        # mort reste zombie et _alive le verrait vivant jusqu'au timeout.
        _reap(pid)
        while _alive(pid) and time.monotonic() < deadline:
            time.sleep(0.1)
            _reap(pid)
        if _alive(pid):
            os.kill(pid, signal.SIGKILL)
        _pid_path(directory, name).unlink(missing_ok=True)
        stopped.append(name)
    return stopped


# --- dashboard vite ---


_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def dashboard_pid(directory: Path) -> int | None:
    """pid du dashboard s'il tourne (nettoie un pid périmé)."""
    path = _pid_path(directory, "dashboard")
    if not path.exists():
        return None
    pid = int(path.read_text())
    if _alive(pid):
        return pid
    path.unlink()
    return None


def start_dashboard(directory: Path, dashboard_dir: Path) -> int:
    """Lance `bun run dev` détaché (pid + log comme un node). Réutilise un dashboard vivant."""
    existing = dashboard_pid(directory)
    if existing is not None:
        return existing
    # Log tronqué (pas append) : l'URL lue par dashboard_url doit venir de ce
    # vite-ci, pas d'un run précédent qui aurait servi un autre port.
    log = open(directory / "logs" / "dashboard.log", "wb")
    # stdin DEVNULL : vite est interactif et volerait les touches du terminal
    # (le menu Ctrl+C du moniteur) s'il héritait du tty.
    process = subprocess.Popen(
        ["bun", "run", "dev"],
        cwd=dashboard_dir,
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    _pid_path(directory, "dashboard").write_text(str(process.pid))
    return process.pid


def stop_dashboard(directory: Path) -> bool:
    """Arrête le dashboard — le groupe entier (bun + vite). True si arrêté."""
    pid = dashboard_pid(directory)
    if pid is None:
        return False
    _signal_group(pid, signal.SIGTERM)
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        _reap(pid)
        if not _alive(pid):
            break
        time.sleep(0.1)
    else:
        _signal_group(pid, signal.SIGKILL)
    _pid_path(directory, "dashboard").unlink(missing_ok=True)
    return True


def _signal_group(pid: int, sig: int) -> None:
    """`bun run dev` a des enfants (vite) : viser le groupe, pas juste le pid.

    start_new_session=True fait du pid le leader de son groupe. killpg lève
    EPERM sur macOS quand le groupe est réduit à un zombie (dashboard spawné
    puis arrêté par le même process) : on retombe alors sur le pid seul.
    """
    try:
        os.killpg(pid, sig)
    except ProcessLookupError:
        pass
    except PermissionError:
        try:
            os.kill(pid, sig)
        except (ProcessLookupError, PermissionError):
            pass


def _reap(pid: int) -> None:
    """Récolte un zombie enfant du process courant (flux mono-process).

    Sans ça, _alive resterait vrai sur le zombie jusqu'au timeout. Pour un pid
    qui n'est pas notre enfant (session `arena` précédente), waitpid échoue sans bruit.
    """
    try:
        os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        pass


def vite_url(log_text: str) -> str | None:
    """Dernière URL locale annoncée par vite (« Local: http://localhost:5173/ »).

    Vite colore parfois l'URL (codes ANSI au milieu du port) : on nettoie avant.
    """
    plain = _ANSI.sub("", log_text)
    matches = re.findall(r"Local:\s+(http://\S+)", plain)
    return matches[-1].rstrip("/") if matches else None


def dashboard_url(directory: Path, timeout_s: float = 15.0) -> str | None:
    """URL du dashboard, lue dans son log vite. None si rien d'annoncé à temps."""
    log = directory / "logs" / "dashboard.log"
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if log.exists():
            url = vite_url(log.read_text(errors="replace"))
            if url:
                return url
        time.sleep(0.2)
    return None
