from typer.testing import CliRunner

from arena_cli.main import app

runner = CliRunner()


def test_status() -> None:
    result = runner.invoke(app, [])
    assert result.exit_code == 0
