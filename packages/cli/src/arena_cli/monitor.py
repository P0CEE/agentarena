"""Moniteur live du réseau — la table des nodes, puis le menu Ctrl+C.

Appelé par le flux `arena` une fois le réseau en ligne (ticket 14) : affiche
le pouls du réseau (Rich Live, un tick par seconde) jusqu'à Ctrl+C, puis
propose d'arrêter le réseau ou de le laisser tourner en fond. La collecte et
la construction des frames sont des fonctions pures, testables sans TTY.
"""

import time
from pathlib import Path

import httpx
import questionary
from rich.console import Group
from rich.live import Live
from rich.text import Text

from arena_cli import network as net
from arena_cli.theme import DANGER, KEEL, POINTER, QMARK_MENU, console

STATUS_TIMEOUT = 0.8  # un node qui rame passe « down » sans figer le tick
TICK_SECONDS = 1.0

STOP = "Arrêter le réseau"
DETACH = "Laisser tourner en fond"


# --- logique pure ---


def poll_nodes(client: httpx.Client, network: dict) -> list[dict]:
    """Un instantané par node via /status ; un node muet est marqué down."""
    rows = []
    for entry in network["nodes"]:
        row = {"name": entry["name"], "port": entry["port"], "up": False,
               "height": 0, "round": 0, "mempool": 0, "proposer": False}
        try:
            data = client.get(f"{entry['url']}/status").json()
            row.update(up=True, height=data["height"], round=data["round"],
                       mempool=data["mempool"], proposer=data["proposer_next"])
        except httpx.HTTPError:
            pass
        rows.append(row)
    return rows


def build_frame(rows: list[dict], dashboard_url: str | None = None) -> Group:
    """La section RÉSEAU du prototype : entête, un node par ligne, pied Ctrl+C."""
    up_rows = [row for row in rows if row["up"]]
    if up_rows:
        head = max(up_rows, key=lambda row: row["height"])
        summary = (f" · h={head['height']} · round {head['round']}"
                   f" · {len(up_rows)}/{len(rows)} up")
    else:
        summary = f" · 0/{len(rows)} up"
    lines = [Text.assemble(("╭─ ", "accent.b"), ("RÉSEAU", "bold"), (summary, "muted"))]
    if dashboard_url:
        lines.append(Text.assemble(("│ ", "accent"), ("dashboard   ", "muted"),
                                   (dashboard_url, "alt underline")))
    lines.extend(_node_line(row) for row in rows)
    lines.append(Text.assemble(("╰─ ", "accent"),
                               ("ctrl+c détacher · le réseau continue", "faint")))
    return Group(*lines)


def _node_line(row: dict) -> Text:
    if not row["up"]:
        return Text.assemble(
            ("│ ", "accent"),
            (f"{row['name']:<8}", f"bold {DANGER}"),
            (f"{row['port']:<7}", "muted"),
            ("○  ", "danger"),
            ("down", "danger"),
        )
    return Text.assemble(
        ("│ ", "accent"),
        (f"{row['name']:<8}", "bold"),
        (f"{row['port']:<7}", "muted"),
        ("●  ", "accent"),
        (f"h={row['height']:<6}", ""),
        (f"round {row['round']:<4}", "muted"),
        (f"mp={row['mempool']:<4}", "muted"),
        ("  ▸ proposer" if row["proposer"] else "", "accent"),
    )


# --- la boucle attachée ---


def run_monitor(directory: Path, network: dict,
                dashboard_url: str | None = None) -> str:
    """Moniteur jusqu'à Ctrl+C, puis menu. Retourne "stopped" ou "detached"."""
    try:
        with httpx.Client(timeout=STATUS_TIMEOUT) as client:
            frame = build_frame(poll_nodes(client, network), dashboard_url)
            with Live(frame, refresh_per_second=4, console=console) as live:
                while True:
                    time.sleep(TICK_SECONDS)
                    live.update(build_frame(poll_nodes(client, network), dashboard_url))
    except KeyboardInterrupt:
        pass
    console.print()
    try:
        choice = questionary.select(
            "Le moniteur est détaché — le réseau ?",
            choices=[STOP, DETACH],
            pointer=POINTER, instruction="↑↓ naviguer · ↵ choisir",
            style=KEEL, qmark=QMARK_MENU,
        ).unsafe_ask()
    except KeyboardInterrupt:
        choice = DETACH  # second Ctrl+C : on ne détruit rien, le réseau continue
    if choice == STOP:
        return _stop(directory, network)
    _print_detached(dashboard_url)
    return "detached"


def _stop(directory: Path, network: dict) -> str:
    with console.status("[muted]arrêt du réseau…", spinner="dots"):
        stopped = net.stop_nodes(directory, network)
        dashboard = net.stop_dashboard(directory)
    detail = f"{len(stopped)} nodes" + (" · dashboard fermé" if dashboard else "")
    console.print(Text.assemble(("✓ ", "accent"), ("réseau arrêté ", "bold"),
                                (f"│ {detail}", "muted")))
    console.print(Text.assemble(("  relance ", "muted"), ("arena", "bold"),
                                (" pour repartir", "muted")))
    return "stopped"


def _print_detached(dashboard_url: str | None) -> None:
    parts: list[tuple[str, str]] = [("● ", "accent"), ("réseau actif en fond", "bold")]
    if dashboard_url:
        parts += [(" │ ", "muted"), (dashboard_url, "alt underline")]
    console.print(Text.assemble(*parts))
    console.print(Text.assemble(("  relance ", "muted"), ("arena", "bold"),
                                (" pour ré-attacher le moniteur", "muted")))
