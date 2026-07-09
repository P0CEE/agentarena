import os
import socket

from arena_cli import wizard


def test_validate_nodes_applique_le_minimum_du_consensus() -> None:
    assert wizard.validate_nodes("10") is True
    message = wizard.validate_nodes("9")
    assert "minimum" in message and "builders" in message
    assert wizard.validate_nodes("abc") is not True


def test_validate_block_time() -> None:
    assert wizard.validate_block_time("2.0") is True
    assert wizard.validate_block_time("0") is not True
    assert wizard.validate_block_time("abc") is not True


def test_validate_port_borne_la_plage() -> None:
    assert wizard.validate_port("8001") is True
    assert wizard.validate_port("80") is not True
    assert wizard.validate_port("70000") is not True
    assert wizard.validate_port("abc") is not True


def test_busy_ports_detecte_un_port_occupe() -> None:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        assert wizard.busy_ports(port, 1) == [port]
    assert wizard.busy_ports(port, 1) == []


def test_write_env_key_preserve_les_autres_lignes(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MISTRAL_API_KEY", "avant")  # restauré au teardown
    env = tmp_path / ".env"
    env.write_text("AUTRE=1\nMISTRAL_API_KEY=vieille\n")
    wizard.write_env_key("neuve", env)
    contenu = env.read_text()
    assert "AUTRE=1" in contenu
    assert "MISTRAL_API_KEY=neuve" in contenu
    assert "vieille" not in contenu
    assert os.environ["MISTRAL_API_KEY"] == "neuve"


def test_write_env_key_cree_le_fichier(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MISTRAL_API_KEY", "avant")
    env = tmp_path / ".env"
    wizard.write_env_key("k", env)
    assert env.read_text() == "MISTRAL_API_KEY=k\n"


def test_mistral_key_present_detecte_env_puis_dotenv(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    assert wizard.mistral_key_present(tmp_path / ".env") is False
    (tmp_path / ".env").write_text("MISTRAL_API_KEY=x\n")
    assert wizard.mistral_key_present(tmp_path / ".env") is True
