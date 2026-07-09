"""Le flux `arena` (ticket 14) : aiguillage réseau, gardes, branchement des briques."""

import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from arena_cli import flow
from arena_cli.main import app

runner = CliRunner()


def _network_dict(agent: str = "stub") -> dict:
    return {
        "agent": agent, "block_time": 2.0, "sponsor": "spx",
        "nodes": [{"name": "node-0", "port": 18700, "url": "http://127.0.0.1:18700",
                   "address": "a0"}],
    }


def _write_network(directory: Path, data: dict | None = None) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "network.json").write_text(json.dumps(data or _network_dict()))


@pytest.fixture
def tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Le flux exige un terminal ; on force la détection Rich pour les tests."""
    monkeypatch.setattr(flow.console, "_force_terminal", True)
    monkeypatch.setattr(flow.wizard, "mistral_key_present", lambda: True)


# --- read_network : l'aiguillage ---


def test_read_network_absent(tmp_path: Path) -> None:
    assert flow.read_network(tmp_path) == (flow.ABSENT, None)


def test_read_network_lisible(tmp_path: Path) -> None:
    _write_network(tmp_path)
    state, network = flow.read_network(tmp_path)
    assert state == flow.OK
    assert network["agent"] == "stub"


def test_read_network_json_invalide(tmp_path: Path) -> None:
    _write_network(tmp_path)
    (tmp_path / "network.json").write_text("{pas du json")
    assert flow.read_network(tmp_path) == (flow.CORRUPT, None)


def test_read_network_tronque(tmp_path: Path) -> None:
    _write_network(tmp_path, {"agent": "stub", "block_time": 2.0, "nodes": [{"name": "n"}]})
    assert flow.read_network(tmp_path) == (flow.CORRUPT, None)
    _write_network(tmp_path, {"agent": "stub", "block_time": 2.0, "nodes": []})
    assert flow.read_network(tmp_path) == (flow.CORRUPT, None)


# --- run : le branchement des briques ---


def test_flux_sans_reseau_wizard_launch_monitor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tty: None
) -> None:
    calls: list = []
    network = _network_dict()
    monkeypatch.setattr(flow.wizard, "run", lambda d: calls.append("wizard") or network)
    monkeypatch.setattr(flow.launch, "launch",
                        lambda d, n: calls.append("launch") or "http://localhost:5173")
    monkeypatch.setattr(flow.monitor, "run_monitor",
                        lambda d, n, url: calls.append(("monitor", url)) or "detached")
    flow.run(tmp_path)
    assert calls == ["wizard", "launch", ("monitor", "http://localhost:5173")]


def test_flux_reseau_existant_saute_le_wizard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tty: None
) -> None:
    _write_network(tmp_path)
    monkeypatch.setattr(flow.wizard, "run", lambda d: pytest.fail("pas de wizard ici"))
    monkeypatch.setattr(flow.launch, "launch", lambda d, n: None)
    seen: dict = {}
    monkeypatch.setattr(flow.monitor, "run_monitor",
                        lambda d, n, url: seen.update(url=url) or "stopped")
    flow.run(tmp_path)
    assert seen == {"url": None}  # pas de dashboard : le moniteur tourne sans URL


def test_flux_reseau_mistral_assure_la_cle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tty: None
) -> None:
    _write_network(tmp_path, _network_dict(agent="mistral"))
    asked: list = []
    monkeypatch.setattr(flow.wizard, "ensure_mistral_key", lambda: asked.append(True))
    monkeypatch.setattr(flow.launch, "launch", lambda d, n: None)
    monkeypatch.setattr(flow.monitor, "run_monitor", lambda d, n, url: "detached")
    flow.run(tmp_path)
    assert asked == [True]


def test_flux_wizard_refuse_sort_sans_lancer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tty: None
) -> None:
    monkeypatch.setattr(flow.wizard, "run", lambda d: None)
    monkeypatch.setattr(flow.launch, "launch", lambda d, n: pytest.fail("rien à lancer"))
    with pytest.raises(typer.Exit) as exc:
        flow.run(tmp_path)
    assert exc.value.exit_code == 0


def test_flux_reseau_corrompu_sort_avec_la_porte_de_sortie(
    tmp_path: Path, tty: None, capsys: pytest.CaptureFixture
) -> None:
    _write_network(tmp_path)
    (tmp_path / "network.json").write_text("{")
    with pytest.raises(typer.Exit) as exc:
        flow.run(tmp_path)
    assert exc.value.exit_code == 1
    out = capsys.readouterr().out
    assert "illisible" in out
    assert "repars" in out


def test_flux_ctrl_c_sort_proprement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tty: None
) -> None:
    def interrupt(_: Path) -> dict:
        raise KeyboardInterrupt

    monkeypatch.setattr(flow.wizard, "run", interrupt)
    with pytest.raises(typer.Exit) as exc:
        flow.run(tmp_path)
    assert exc.value.exit_code == 130


# --- la commande racine ---


def test_arena_nu_sans_terminal_refuse(tmp_path: Path) -> None:
    # CliRunner n'a pas de TTY : le garde du flux doit refuser avec un mode d'emploi.
    result = runner.invoke(app, ["--dir", str(tmp_path / "net")])
    assert result.exit_code == 1
    assert "terminal" in result.output
