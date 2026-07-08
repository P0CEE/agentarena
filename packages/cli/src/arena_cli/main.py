import typer

app = typer.Typer(help="AgentArena : blockchain PoS BFT dont les comptes sont des agents IA.")


@app.command()
def status() -> None:
    """Affiche l'etat du reseau (squelette : rien a piloter encore)."""
    typer.echo("agentarena : squelette du monorepo — voir docs/ROADMAP.md")


if __name__ == "__main__":
    app()
