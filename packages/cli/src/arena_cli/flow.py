"""Le flux `arena` : bannière, création ou ré-attache du réseau, lancement, moniteur.

La commande unique (main.py) appelle run(). Les briques viennent des
tickets 11-13 — wizard, launch, monitor ;
ici on les branche et on porte les gardes : terminal interactif requis,
network.json corrompu, clé Mistral assurée avant tout démarrage.
"""

import json
import shutil
from pathlib import Path

import typer

from arena_cli import launch, monitor, wizard
from arena_cli import network as net
from arena_cli.theme import banner, console, status_note, status_ok, status_warn

ABSENT, OK, CORRUPT = "absent", "ok", "corrompu"


def read_network(directory: Path) -> tuple[str, dict | None]:
    """L'aiguillage du flux : "absent" | "ok" | "corrompu", et le réseau si lisible."""
    path = net.network_path(directory)
    if not path.exists():
        return ABSENT, None
    try:
        network = json.loads(path.read_text())
        usable = (
            isinstance(network, dict)
            and "agent" in network and "block_time" in network
            and bool(network.get("nodes"))
            and all({"name", "port", "url"} <= set(entry) for entry in network["nodes"])
        )
    except (json.JSONDecodeError, TypeError):
        return CORRUPT, None
    return (OK, network) if usable else (CORRUPT, None)


def run(directory: Path) -> None:
    """`arena` tout court : assistant si besoin, lancement, moniteur jusqu'à Ctrl+C."""
    if not console.is_terminal:
        console.print("arena est interactif et demande un vrai terminal")
        raise typer.Exit(code=1)
    banner()
    state, network = read_network(directory)
    _boot_status(directory, state, network)
    if state == CORRUPT:
        raise typer.Exit(code=1)
    try:
        if network is None:
            network = wizard.run(directory)
            if network is None:
                console.print("[muted]rien n'a été créé — relance[/] [bold]arena[/] "
                              "[muted]quand tu veux[/]")
                raise typer.Exit()
        elif network["agent"] == "mistral":
            wizard.ensure_mistral_key()
        url = launch.launch(directory, network)
    except KeyboardInterrupt:
        console.print()
        console.print("[muted]interrompu[/]")
        raise typer.Exit(code=130) from None
    monitor.run_monitor(directory, network, url)


def _boot_status(directory: Path, state: str, network: dict | None) -> None:
    """Les statuts du boot (prototype du ticket 10) : clé Mistral, bun, réseau."""
    if wizard.mistral_key_present():
        status_ok("clé Mistral (.env)")
    else:
        status_warn("clé Mistral absente — elle va être demandée")
    if shutil.which("bun"):
        status_ok("bun — dashboard")
    else:
        status_warn("bun introuvable — le réseau tournera sans dashboard")
    if state == ABSENT:
        status_note("aucun réseau — assistant de création")
    elif state == CORRUPT:
        status_warn(f"{net.network_path(directory)} illisible — répare-le "
                    f"ou repars à zéro : rm -rf {directory} puis arena")
    else:
        up = len(net.running_nodes(directory, network))
        status_note(f"réseau détecté · {len(network['nodes'])} nodes ({up} up) — ré-attache")
    console.print()
