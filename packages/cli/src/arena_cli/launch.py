"""Lancement orchestré : nodes + health-check, dashboard vite, navigateur.

Appelé par le flux `arena` (ticket 14) après création ou détection du réseau.
Relançable : les nodes déjà vivants et un dashboard déjà lancé sont réutilisés,
donc le même appel sert au premier démarrage et au ré-attachement.
"""

import os
import shutil
import time
import webbrowser
from pathlib import Path

import httpx
from rich.text import Text

from arena_cli import network as net
from arena_cli.theme import VIOLET, console, section_close, section_open

READY_TIMEOUT = 20.0


def wait_nodes_ready(network: dict, timeout_s: float = READY_TIMEOUT) -> list[str]:
    """Attend que chaque node réponde sur /status ; retourne les noms des muets."""
    pending = {entry["name"]: entry["url"] for entry in network["nodes"]}
    deadline = time.monotonic() + timeout_s
    with httpx.Client(timeout=1.0) as client:
        while pending and time.monotonic() < deadline:
            for name, url in list(pending.items()):
                try:
                    client.get(f"{url}/status")
                    del pending[name]
                except httpx.HTTPError:
                    pass
            if pending:
                time.sleep(0.2)
    return sorted(pending)


def launch(directory: Path, network: dict, open_browser: bool = True) -> str | None:
    """Démarre nodes et dashboard, ouvre le navigateur. Retourne l'URL du dashboard."""
    net.load_dotenv()
    if network["agent"] == "mistral" and not os.environ.get("MISTRAL_API_KEY"):
        console.print("[warn]✗[/] MISTRAL_API_KEY manquante (.env) — les nodes refuseraient de démarrer")
        return None

    count = len(network["nodes"])
    label = f"démarrage des nodes ({count})"
    with console.status(f"[muted]{label}…", spinner="dots"):
        net.start_nodes(directory, network)
        down = wait_nodes_ready(network)
    if down:
        console.print(f"[warn]✗[/] {label} — muets : {', '.join(down)} (logs : {directory}/logs)")
    else:
        console.print(f"[accent]✓[/] {label}")

    url = None
    dashboard_dir = directory.resolve().parent / "apps" / "dashboard"
    if shutil.which("bun") is None:
        console.print("[warn]✗[/] bun introuvable — pas de dashboard (le réseau reste utilisable)")
    elif not dashboard_dir.is_dir():
        console.print(f"[warn]✗[/] {dashboard_dir} introuvable — pas de dashboard (le réseau reste utilisable)")
    else:
        with console.status("[muted]dashboard vite…", spinner="dots"):
            net.start_dashboard(directory, dashboard_dir)
            url = net.dashboard_url(directory)
        if url:
            console.print("[accent]✓[/] dashboard vite")
        else:
            console.print(f"[warn]✗[/] le dashboard n'annonce pas d'URL (log : {directory}/logs/dashboard.log)")
    if url and open_browser:
        webbrowser.open(url)

    ports = [entry["port"] for entry in network["nodes"]]
    up_label = f"{count - len(down)}/{count} nodes" if down else f"{count} nodes"
    console.print()
    section_open("EN LIGNE")
    console.print(Text.assemble(
        ("│ ", "accent"), (up_label, "bold"),
        (f" · ports {ports[0]}–{ports[-1]} · agents {network['agent']}", "muted"),
    ))
    if url:
        console.print(Text.assemble(
            ("│ ", "accent"), ("dashboard  ", "muted"), (url, f"underline {VIOLET}"),
        ))
    section_close()
    console.print()
    return url
