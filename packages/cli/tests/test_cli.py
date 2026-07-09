"""La surface unique (`arena --help`) et le réseau écrit par create_network."""

import json
from pathlib import Path

from typer.testing import CliRunner

from arena_cli import network as net
from arena_cli.main import app

runner = CliRunner()


def test_help_ne_montre_que_la_commande_unique() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "--dir" in result.output
    for gone in ("init", "start", "stop", "status", "task", "demo"):
        assert gone not in result.output


def test_create_network_coherent(tmp_path: Path) -> None:
    directory = tmp_path / "net"
    network = net.create_network(directory, 10, "mistral", 2.0, 18500)

    assert network["agent"] == "mistral"
    assert len(network["nodes"]) == 10
    assert [entry["port"] for entry in network["nodes"]] == list(range(18500, 18510))

    configs = [
        json.loads(path.read_text())
        for path in sorted((directory / "nodes").glob("*.json"))
    ]
    # Le genesis est strictement identique pour tous les nodes.
    first_genesis = configs[0]["genesis"]
    assert all(config["genesis"] == first_genesis for config in configs)
    assert all(len(config["peers"]) == 9 for config in configs)
    # Le sponsor est finance dans le genesis mais n'est pas un agent.
    sponsor = json.loads((directory / "sponsor.json").read_text())
    assert sponsor["address"] in first_genesis["allocations"]
    assert sponsor["address"] not in first_genesis["agents"]
    # Chaque node est un agent stake.
    for entry in network["nodes"]:
        assert first_genesis["agents"][entry["address"]] > 0
    # Seul le node de reference detient le wallet sponsor (endpoint dashboard).
    assert configs[0]["sponsor_seed"] == sponsor["seed"]
    assert all("sponsor_seed" not in config for config in configs[1:])
