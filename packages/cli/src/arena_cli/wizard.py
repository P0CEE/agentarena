"""Assistant de création du réseau — les questions, le récap, create_network.

Appelé par le flux `arena` quand aucun réseau n'existe (le flux fait ce garde).
Expérience 100 % Mistral : la clé est détectée (env puis .env), sinon demandée
et écrite dans .env. La logique est en fonctions pures, testables sans TTY.
"""

import os
import socket
from pathlib import Path

import questionary

from arena_chain.params import K_BUILDERS, MIN_JUDGES

from arena_cli import network as net
from arena_cli.theme import (
    KEEL,
    QMARK_SECTION,
    console,
    section_close,
    section_field,
    section_open,
)

MIN_NODES = K_BUILDERS + MIN_JUDGES
DEFAULT_NODES = "10"
DEFAULT_BLOCK_TIME = "2.0"
DEFAULT_PORT = "8001"


# --- logique pure ---


def validate_nodes(value: str) -> bool | str:
    if not value.isdigit() or int(value) < MIN_NODES:
        return f"{MIN_NODES} nodes minimum ({K_BUILDERS} builders + {MIN_JUDGES} juges)"
    return True


def validate_block_time(value: str) -> bool | str:
    try:
        return float(value) > 0 or "un nombre positif, ex. 2.0"
    except ValueError:
        return "un nombre, ex. 2.0"


def validate_port(value: str) -> bool | str:
    if not value.isdigit() or not (1024 < int(value) < 65000):
        return "un port entre 1025 et 64999"
    return True


def busy_ports(base: int, count: int) -> list[int]:
    """Les ports déjà occupés dans la plage [base, base+count).

    SO_REUSEADDR comme uvicorn : un port en TIME_WAIT (réseau tout juste
    arrêté) est re-liable par les nodes, il ne doit pas être compté occupé.
    """
    busy = []
    for port in range(base, base + count):
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                busy.append(port)
    return busy


def mistral_key_present(env_path: Path = Path(".env")) -> bool:
    """Vraie détection : environnement, puis .env (chargé comme au start)."""
    net.load_dotenv(env_path)
    return bool(os.environ.get("MISTRAL_API_KEY"))


def write_env_key(key: str, env_path: Path = Path(".env")) -> None:
    """Écrit MISTRAL_API_KEY dans .env sans toucher aux autres lignes."""
    lines = env_path.read_text().splitlines() if env_path.exists() else []
    lines = [line for line in lines if not line.startswith("MISTRAL_API_KEY=")]
    lines.append(f"MISTRAL_API_KEY={key}")
    env_path.write_text("\n".join(lines) + "\n")
    os.environ["MISTRAL_API_KEY"] = key


# --- prompts ---


def ensure_mistral_key() -> None:
    """Clé détectée (env puis .env), sinon demandée en saisie masquée et écrite dans .env."""
    if mistral_key_present():
        return
    key = questionary.password(
        "Clé Mistral (écrite dans .env)",
        validate=lambda v: bool(v.strip()) or "la clé est requise (console.mistral.ai)",
        style=KEEL, qmark=QMARK_SECTION,
    ).unsafe_ask()
    write_env_key(key.strip())


def run(directory: Path = Path(".arena")) -> dict | None:
    """Déroule l'assistant et crée le réseau. None si l'utilisateur renonce."""
    ask = {"style": KEEL, "qmark": QMARK_SECTION}
    section_open("NOUVEAU RÉSEAU")
    nodes = int(questionary.text(
        "Nombre de nodes", default=DEFAULT_NODES, validate=validate_nodes, **ask,
    ).unsafe_ask())
    block_time = float(questionary.text(
        "Block time (secondes)", default=DEFAULT_BLOCK_TIME,
        validate=validate_block_time, **ask,
    ).unsafe_ask())
    port = _ask_free_port(nodes, ask)
    ensure_mistral_key()
    section_field("nodes", str(nodes))
    section_field("block time", f"{block_time}s")
    section_field("ports", f"{port}–{port + nodes - 1}")
    section_field("agents", "mistral")
    confirmed = questionary.confirm("Créer le réseau ?", default=True, **ask).unsafe_ask()
    section_close()
    if not confirmed:
        return None
    with console.status("[muted]génération des wallets et du genesis…", spinner="dots"):
        network = net.create_network(directory, nodes, "mistral", block_time, port)
    console.print(f"[accent]✓[/] wallets et genesis · [bold]{directory}[/]")
    return network


def _ask_free_port(nodes: int, ask: dict) -> int:
    """Demande le premier port jusqu'à obtenir une plage entièrement libre."""
    while True:
        port = int(questionary.text(
            "Premier port", default=DEFAULT_PORT, validate=validate_port, **ask,
        ).unsafe_ask())
        busy = busy_ports(port, nodes)
        if not busy:
            return port
        occupied = ", ".join(str(p) for p in busy[:4]) + ("…" if len(busy) > 4 else "")
        console.print(f"[warn]✗[/] [muted]ports occupés : {occupied} — choisis une autre plage[/]")
