"""CLI AgentArena : `arena`, la commande unique — assistant, lancement, moniteur live."""

from pathlib import Path

import typer

from arena_cli import flow

app = typer.Typer()

DIR = typer.Option(Path(".arena"), "--dir", help="Repertoire du reseau.")


@app.command()
def main(directory: Path = DIR) -> None:
    """AgentArena : blockchain PoS BFT dont les comptes sont des agents IA.

    Assistant de création si aucun réseau, sinon ré-attache ; lance les nodes
    et le dashboard, puis moniteur live jusqu'à Ctrl+C.
    """
    flow.run(directory)


if __name__ == "__main__":
    app()
