from pathlib import Path

from typer.testing import CliRunner

from linuxdo_agent.cli import app


def test_cli_digest_reads_cache(tmp_path) -> None:
    db_path = tmp_path / "linuxdo.sqlite"
    output_path = tmp_path / "digest.md"
    runner = CliRunner()

    seed_result = runner.invoke(
        app,
        [
            "--db",
            str(db_path),
            "seed-sample",
        ],
    )
    assert seed_result.exit_code == 0

    result = runner.invoke(
        app,
        [
            "--db",
            str(db_path),
            "digest",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert Path(output_path).read_text(encoding="utf-8").startswith("# Linux.do 热点摘要")
