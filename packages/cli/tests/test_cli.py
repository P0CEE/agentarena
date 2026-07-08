import json
from pathlib import Path

from typer.testing import CliRunner

from arena_cli.main import app

runner = CliRunner()


def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "init" in result.output
    assert "demo" in result.output


def _init(tmp_path: Path, *extra: str):
    return runner.invoke(
        app, ["init", "--dir", str(tmp_path / "net"), "--agent", "stub", *extra]
    )


def test_init_cree_un_reseau_coherent(tmp_path: Path) -> None:
    result = _init(tmp_path)
    assert result.exit_code == 0, result.output

    network = json.loads((tmp_path / "net" / "network.json").read_text())
    assert len(network["nodes"]) == 10
    assert network["agent"] == "stub"
    ports = [entry["port"] for entry in network["nodes"]]
    assert len(set(ports)) == 10

    configs = [
        json.loads(path.read_text())
        for path in sorted((tmp_path / "net" / "nodes").glob("*.json"))
    ]
    # Le genesis est strictement identique pour tous les nodes.
    first_genesis = configs[0]["genesis"]
    assert all(config["genesis"] == first_genesis for config in configs)
    assert all(len(config["peers"]) == 9 for config in configs)
    # Le sponsor est finance dans le genesis mais n'est pas un agent.
    sponsor = json.loads((tmp_path / "net" / "sponsor.json").read_text())
    assert sponsor["address"] in first_genesis["allocations"]
    assert sponsor["address"] not in first_genesis["agents"]
    # Chaque node est un agent stake.
    for entry in network["nodes"]:
        assert first_genesis["agents"][entry["address"]] > 0
    # Seul le node de reference detient le wallet sponsor (endpoint dashboard).
    assert configs[0]["sponsor_seed"] == sponsor["seed"]
    assert all("sponsor_seed" not in config for config in configs[1:])


def test_init_refuse_un_pool_trop_petit(tmp_path: Path) -> None:
    result = _init(tmp_path, "--nodes", "5")
    assert result.exit_code != 0
    assert "builders" in result.output


def test_init_refuse_d_ecraser_sans_force(tmp_path: Path) -> None:
    assert _init(tmp_path).exit_code == 0
    again = _init(tmp_path)
    assert again.exit_code == 1
    assert "--force" in again.output
    forced = _init(tmp_path, "--force")
    assert forced.exit_code == 0


def test_status_sans_reseau(tmp_path: Path) -> None:
    result = runner.invoke(app, ["status", "--dir", str(tmp_path / "nulle-part")])
    assert result.exit_code == 1
    assert "arena init" in result.output


def test_status_reseau_eteint(tmp_path: Path) -> None:
    assert _init(tmp_path, "--base-port", "18500").exit_code == 0
    result = runner.invoke(app, ["status", "--dir", str(tmp_path / "net")])
    assert result.exit_code == 0
    assert result.output.count("down") == 10  # personne ne tourne, et ca ne crashe pas
