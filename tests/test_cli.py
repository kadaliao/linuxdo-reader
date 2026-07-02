from pathlib import Path

import httpx
import respx
from typer.testing import CliRunner

from linuxdo_reader.cli import app

from .fixtures import LATEST_RSS


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


def test_cli_accepts_short_help_flag() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["-h"])

    assert result.exit_code == 0
    assert "Helper CLI for the Linux.do Reader skill" in result.output


def test_cli_digest_prints_to_stdout_by_default(tmp_path) -> None:
    db_path = tmp_path / "linuxdo.sqlite"
    runner = CliRunner()
    runner.invoke(app, ["--db", str(db_path), "seed-sample"])

    result = runner.invoke(app, ["--db", str(db_path), "digest"])

    assert result.exit_code == 0
    assert result.output.startswith("# Linux.do 热点摘要")


def test_cli_has_crawl_command() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["crawl", "-h"], env={"NO_COLOR": "1"})

    assert result.exit_code == 0
    assert "prefer" in result.output
    assert "limit" in result.output


@respx.mock
def test_cli_refresh_reports_feed_errors_without_traceback(tmp_path) -> None:
    respx.get("https://linux.do/top.rss").mock(return_value=httpx.Response(403))
    respx.get("https://linux.do/top/daily.rss").mock(side_effect=httpx.ConnectError("TLS EOF"))
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "--db",
            str(tmp_path / "linuxdo.sqlite"),
            "refresh",
            "--source",
            "top",
            "--period",
            "daily",
        ],
    )

    assert result.exit_code == 1
    assert "All linux.do feed requests failed" in result.output
    assert "Traceback" not in result.output


@respx.mock
def test_cli_refresh_uses_configured_cookies_file(tmp_path) -> None:
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(
        "# Netscape HTTP Cookie File\n"
        ".linux.do\tTRUE\t/\tTRUE\t2147483647\t_cf_bm\tabc\n",
        encoding="utf-8",
    )
    route = respx.get("https://linux.do/top.rss").mock(
        return_value=httpx.Response(200, text=LATEST_RSS)
    )
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "--db",
            str(tmp_path / "linuxdo.sqlite"),
            "--cookies-file",
            str(cookies_file),
            "refresh",
            "--source",
            "top",
            "--period",
            "daily",
        ],
    )

    assert result.exit_code == 0
    assert route.calls.last.request.headers["cookie"] == "_cf_bm=abc"


def test_cli_has_auth_commands() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["auth", "-h"], env={"NO_COLOR": "1"})

    assert result.exit_code == 0
    assert "login" in result.output
    assert "refresh" in result.output


def test_cli_has_install_skill_command() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["install-skill", "-h"], env={"NO_COLOR": "1"})

    assert result.exit_code == 0
    assert "Install the bundled Skill" in result.output


def test_cli_install_skill_from_local_source(tmp_path) -> None:
    source = tmp_path / "source" / "linuxdo-reader"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("# Linux.do Reader\n", encoding="utf-8")
    dest = tmp_path / "codex" / "skills" / "linuxdo-reader"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "install-skill",
            "--source",
            str(source),
            "--dest",
            str(dest),
        ],
    )

    assert result.exit_code == 0
    assert f"Installed Skill to {dest}" in result.output
    assert (dest / "SKILL.md").exists()
