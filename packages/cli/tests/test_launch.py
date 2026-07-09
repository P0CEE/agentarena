"""Lancement orchestré (ticket 12) : parsing vite, cycle de vie dashboard, launch."""

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from arena_cli import launch
from arena_cli import network as net

VITE_LOG = """
  VITE v6.3.5  ready in 312 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
"""

# Vite colorise l'URL quand les couleurs sont forcées : codes ANSI au milieu du port.
VITE_LOG_ANSI = (
    "\x1b[32m➜\x1b[39m  \x1b[1mLocal\x1b[22m:   "
    "\x1b[36mhttp://localhost:\x1b[1m5174\x1b[22m/\x1b[39m\n"
)


def test_vite_url_extrait_l_url() -> None:
    assert net.vite_url(VITE_LOG) == "http://localhost:5173"


def test_vite_url_nettoie_les_codes_ansi() -> None:
    assert net.vite_url(VITE_LOG_ANSI) == "http://localhost:5174"


def test_vite_url_prend_la_derniere_annonce() -> None:
    # Un log qui contient deux runs : seul le port du dernier vite compte.
    assert net.vite_url(VITE_LOG + "\n  ➜  Local:   http://localhost:5180/\n") \
        == "http://localhost:5180"


def test_vite_url_sans_annonce() -> None:
    assert net.vite_url("") is None
    assert net.vite_url("error: vite introuvable") is None


def _sleeper(*, with_child: bool = False) -> subprocess.Popen:
    """Un process détaché qui dort, avec éventuellement un enfant dans son groupe."""
    code = "import time; time.sleep(60)"
    if with_child:
        code = (
            "import subprocess, sys, time; "
            "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
            "print(p.pid, flush=True); time.sleep(60)"
        )
    return subprocess.Popen(
        [sys.executable, "-c", code], stdout=subprocess.PIPE, start_new_session=True
    )


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


@pytest.fixture
def arena_dir(tmp_path: Path) -> Path:
    (tmp_path / "pids").mkdir()
    (tmp_path / "logs").mkdir()
    return tmp_path


def test_dashboard_pid_et_stop(arena_dir: Path) -> None:
    process = _sleeper()
    (arena_dir / "pids" / "dashboard.pid").write_text(str(process.pid))
    assert net.dashboard_pid(arena_dir) == process.pid
    assert net.stop_dashboard(arena_dir) is True
    assert net.dashboard_pid(arena_dir) is None
    assert not (arena_dir / "pids" / "dashboard.pid").exists()
    process.wait(timeout=5)


def test_stop_dashboard_tue_le_groupe_entier(arena_dir: Path) -> None:
    # bun run dev lance vite en enfant : l'arrêt doit tuer les deux.
    process = _sleeper(with_child=True)
    child_pid = int(process.stdout.readline())
    (arena_dir / "pids" / "dashboard.pid").write_text(str(process.pid))
    assert net.stop_dashboard(arena_dir) is True
    process.wait(timeout=5)
    # L'enfant orphelin reste zombie le temps que launchd le récolte.
    deadline = time.monotonic() + 5.0
    while _alive(child_pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not _alive(child_pid)


def test_stop_dashboard_sans_dashboard(arena_dir: Path) -> None:
    assert net.stop_dashboard(arena_dir) is False


def test_dashboard_pid_nettoie_un_pid_perime(arena_dir: Path) -> None:
    process = _sleeper()
    process.kill()
    process.wait(timeout=5)
    (arena_dir / "pids" / "dashboard.pid").write_text(str(process.pid))
    assert net.dashboard_pid(arena_dir) is None
    assert not (arena_dir / "pids" / "dashboard.pid").exists()


def test_wait_nodes_ready_signale_les_muets() -> None:
    network = {"nodes": [{"name": "node-0", "url": "http://127.0.0.1:19986"}]}
    assert launch.wait_nodes_ready(network, timeout_s=0.5) == ["node-0"]


def test_launch_ouvre_le_navigateur_sur_l_url_detectee(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    directory = tmp_path / ".arena"
    directory.mkdir()
    (tmp_path / "apps" / "dashboard").mkdir(parents=True)
    network = {
        "agent": "stub",
        "nodes": [{"name": "node-0", "port": 8001, "url": "http://127.0.0.1:8001"}],
    }
    opened: list[str] = []
    monkeypatch.setattr(net, "start_nodes", lambda *a: [])
    monkeypatch.setattr(launch, "wait_nodes_ready", lambda *a, **k: [])
    monkeypatch.setattr(launch.shutil, "which", lambda _: "/fake/bun")
    monkeypatch.setattr(net, "start_dashboard", lambda *a: 12345)
    monkeypatch.setattr(net, "dashboard_url", lambda *a, **k: "http://localhost:5174")
    monkeypatch.setattr(launch.webbrowser, "open", opened.append)

    url = launch.launch(directory, network)

    assert url == "http://localhost:5174"
    assert opened == ["http://localhost:5174"]


def test_launch_sans_bun_reste_utilisable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    directory = tmp_path / ".arena"
    directory.mkdir()
    network = {
        "agent": "stub",
        "nodes": [{"name": "node-0", "port": 8001, "url": "http://127.0.0.1:8001"}],
    }
    monkeypatch.setattr(net, "start_nodes", lambda *a: [])
    monkeypatch.setattr(launch, "wait_nodes_ready", lambda *a, **k: [])
    monkeypatch.setattr(launch.shutil, "which", lambda _: None)
    monkeypatch.setattr(launch.webbrowser, "open", lambda _: pytest.fail("pas de navigateur ici"))

    assert launch.launch(directory, network) is None
    assert "bun introuvable" in capsys.readouterr().out
