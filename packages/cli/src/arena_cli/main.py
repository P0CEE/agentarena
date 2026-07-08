"""CLI AgentArena : init, start, stop, status, task create, demo."""

import os
import secrets
import time
from pathlib import Path
from shutil import rmtree

import httpx
import typer

from arena_chain.params import JUDGE_RESERVE_PCT, K_BUILDERS, MIN_JUDGES, MIN_PRICE
from arena_chain.tx import make_tx

from arena_cli import network as net

app = typer.Typer(
    help="AgentArena : blockchain PoS BFT dont les comptes sont des agents IA.",
    no_args_is_help=True,
)
task_app = typer.Typer(help="Gestion des tasks.", no_args_is_help=True)
app.add_typer(task_app, name="task")

DIR = typer.Option(Path(".arena"), "--dir", help="Repertoire du reseau.")
DEFAULT_BRIEF = (
    "Ecris une fonction Python is_prime(n) documentee, avec la gestion des cas "
    "limites et trois exemples d'utilisation."
)


@app.command()
def init(
    directory: Path = DIR,
    nodes: int = typer.Option(10, help="Nombre de nodes/agents."),
    agent: str = typer.Option("auto", help="Agents: auto | stub | mistral."),
    block_time: float = typer.Option(2.0, help="Intervalle de production des blocs (s)."),
    base_port: int = typer.Option(8001, help="Premier port ; les suivants s'incrementent."),
    force: bool = typer.Option(False, help="Ecrase un reseau existant."),
) -> None:
    """Génère le genesis, les wallets et la config des nodes."""
    minimum = K_BUILDERS + MIN_JUDGES
    if nodes < minimum:
        raise typer.BadParameter(
            f"{nodes} nodes < {minimum} requis ({K_BUILDERS} builders + {MIN_JUDGES} juges)"
        )
    if net.network_path(directory).exists():
        if not force:
            typer.echo(f"{directory} existe deja (utilise --force pour ecraser)")
            raise typer.Exit(code=1)
        rmtree(directory)

    net.load_dotenv()
    if agent == "auto":
        agent = "mistral" if os.environ.get("MISTRAL_API_KEY") else "stub"
        if agent == "stub":
            typer.echo("pas de MISTRAL_API_KEY trouvee -> agents stub (deterministes)")
    if agent == "mistral" and not os.environ.get("MISTRAL_API_KEY"):
        typer.echo("MISTRAL_API_KEY manquante (mets-la dans .env) pour --agent mistral")
        raise typer.Exit(code=1)

    network = net.create_network(directory, nodes, agent, block_time, base_port)
    ports = [entry["port"] for entry in network["nodes"]]
    typer.echo(f"reseau initialise dans {directory}")
    typer.echo(f"  {nodes} nodes (ports {ports[0]}-{ports[-1]}), agents {agent}")
    typer.echo(f"  block time {block_time}s, sponsor {network['sponsor'][:12]}...")
    typer.echo("lance `arena start` puis `arena demo`")


@app.command()
def start(directory: Path = DIR) -> None:
    """Lance les process nodes (détachés, logs dans .arena/logs/)."""
    network = _network(directory)
    net.load_dotenv()
    if network["agent"] == "mistral" and not os.environ.get("MISTRAL_API_KEY"):
        typer.echo("MISTRAL_API_KEY manquante : les nodes mistral refuseraient de demarrer")
        raise typer.Exit(code=1)
    started = net.start_nodes(directory, network)
    if started:
        typer.echo(f"{len(started)} nodes lances: {', '.join(started)}")
    else:
        typer.echo("tous les nodes tournent deja")
    typer.echo("suis-les avec `arena status`")


@app.command()
def stop(directory: Path = DIR) -> None:
    """Arrête les process nodes."""
    stopped = net.stop_nodes(directory, _network(directory))
    typer.echo(f"{len(stopped)} nodes arretes" if stopped else "aucun node ne tournait")


@app.command()
def status(directory: Path = DIR) -> None:
    """État de chaque node : hauteur, round, mempool, proposer."""
    network = _network(directory)
    typer.echo(f"{'node':<8} {'port':<6} {'hauteur':<8} {'round':<6} {'mempool':<8} proposer")
    with httpx.Client(timeout=1.0) as client:
        for entry in network["nodes"]:
            try:
                data = client.get(f"{entry['url']}/status").json()
                proposer = "oui" if data["proposer_next"] else "-"
                typer.echo(
                    f"{entry['name']:<8} {entry['port']:<6} {data['height']:<8} "
                    f"{data['round']:<6} {data['mempool']:<8} {proposer}"
                )
            except httpx.HTTPError:
                typer.echo(f"{entry['name']:<8} {entry['port']:<6} {'down':<8}")


@task_app.command("create")
def task_create(
    brief: str = typer.Option(DEFAULT_BRIEF, help="Le brief de la task."),
    prize: int = typer.Option(5 * MIN_PRICE, help="Le prix en tokens."),
    directory: Path = DIR,
    watch: bool = typer.Option(False, help="Suit la manche jusqu'au reglement."),
) -> None:
    """Soumet une task signée par le sponsor."""
    network = _network(directory)
    task_id = _create_task(directory, network, brief, prize)
    task = _wait_task(network, task_id)
    typer.echo(f"task {task_id} creee (prix {prize})")
    typer.echo(f"  builders: {_names(network, task['builders'])}")
    typer.echo(f"  juges:    {_names(network, task['judges'])}")
    if watch:
        _watch(network, task_id)


@app.command()
def demo(
    directory: Path = DIR,
    brief: str = typer.Option(DEFAULT_BRIEF, help="Le brief de la manche de demo."),
    prize: int = typer.Option(5 * MIN_PRICE, help="Le prix en tokens."),
) -> None:
    """Une manche de bout en bout : create_task, suivi live, règlement."""
    network = _network(directory)
    task_id = _create_task(directory, network, brief, prize)
    typer.echo(f"manche {task_id} lancee (prix {prize}) — brief: {brief[:60]}...")
    task = _wait_task(network, task_id)
    typer.echo(f"builders designes: {_names(network, task['builders'])}")
    typer.echo(f"juges designes:    {_names(network, task['judges'])}")
    _watch(network, task_id)


# --- helpers ---


def _network(directory: Path) -> dict:
    try:
        return net.load_network(directory)
    except FileNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc


def _base_url(network: dict) -> str:
    return network["nodes"][0]["url"]


def _names(network: dict, addresses: list[str]) -> str:
    names = net.node_names(network)
    return ", ".join(names.get(addr, addr[:8]) for addr in addresses)


def _create_task(directory: Path, network: dict, brief: str, prize: int) -> str:
    sponsor = net.sponsor_wallet(directory)
    task_id = f"demo-{secrets.token_hex(3)}"
    base = _base_url(network)
    with httpx.Client(timeout=3.0) as client:
        try:
            nonce = client.get(f"{base}/accounts/{sponsor.address}").json()["nonce"]
        except httpx.HTTPError as exc:
            typer.echo(f"le reseau ne repond pas ({exc}) — lance `arena start`")
            raise typer.Exit(code=1) from exc
        tx = make_tx(
            sponsor, nonce, {"type": "create_task", "task": task_id, "prize": prize,
                             "brief": brief},
        )
        response = client.post(f"{base}/tx", json=tx)
        if response.status_code != 200:
            typer.echo(f"tx rejetee: {response.json().get('detail')}")
            raise typer.Exit(code=1)
    return task_id


def _wait_task(network: dict, task_id: str, timeout_s: float = 60.0) -> dict:
    """Attend que la task soit incluse dans un bloc et retourne sa fiche."""
    base = _base_url(network)
    deadline = time.monotonic() + timeout_s
    with httpx.Client(timeout=2.0) as client:
        while time.monotonic() < deadline:
            response = client.get(f"{base}/tasks/{task_id}")
            if response.status_code == 200:
                return response.json()["task"]
            time.sleep(0.5)
    typer.echo("la task n'apparait pas on-chain (reseau bloque ?)")
    raise typer.Exit(code=1)


def _watch(network: dict, task_id: str) -> None:
    """Suit la manche en direct puis affiche le règlement."""
    base = _base_url(network)
    poll = min(float(network["block_time"]), 2.0)
    last_line = ""
    with httpx.Client(timeout=2.0) as client:
        while True:
            detail = client.get(f"{base}/tasks/{task_id}").json()
            task = detail["task"]
            height = client.get(f"{base}/status").json()["height"]
            revealed = sum(1 for s in detail["submissions"].values()
                           if s["status"] == "REVEAL_OK")
            noted = sum(1 for s in detail["scores"].values() if s["status"] == "REVEAL_OK")
            line = (
                f"h={height:<4} {task['state']:<8} rendus {len(detail['submissions'])}"
                f"/{len(task['builders'])} (reveles {revealed}) | notes {noted}"
                f"/{len(task['judges'])}"
            )
            if line != last_line:
                typer.echo(line)
                last_line = line
            if task["state"] == "SETTLED":
                _print_settlement(network, task)
                return
            time.sleep(poll)


def _print_settlement(network: dict, task: dict) -> None:
    result = task["result"]
    if "aborted" in result:
        typer.echo(f"manche annulee ({result['aborted']}) : prix rembourse au sponsor")
        return
    names = net.node_names(network)
    reserve = task["prize"] * JUDGE_RESERVE_PCT // 100
    typer.echo(f"\nreglement Yuma — prix {task['prize']} "
               f"({task['prize'] - reserve} builders / {reserve} juges)")
    typer.echo("  builders:")
    payouts = result["payouts"]["builders"]
    for addr in sorted(result["builders"], key=lambda a: -payouts[a]):
        typer.echo(f"    {names.get(addr, addr[:8]):<8} {payouts[addr]:>8} tokens")
    typer.echo("  juges:")
    judge_payouts = result["payouts"]["judges"]
    for addr in sorted(result["judges"], key=lambda a: -judge_payouts[a]):
        typer.echo(f"    {names.get(addr, addr[:8]):<8} {judge_payouts[addr]:>8} tokens")


if __name__ == "__main__":
    app()
