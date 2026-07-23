from pathlib import Path

import httpx
import respx
from typer.testing import CliRunner

from linuxdo_reader.cli import app

from .fixtures import LATEST_RSS, POSTS_JSON, TOPIC_JSON, TOPIC_RSS


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
    assert (
        Path(output_path).read_text(encoding="utf-8").startswith("# Linux.do 热点摘要")
    )


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
    respx.get("https://linux.do/top/daily.rss").mock(
        side_effect=httpx.ConnectError("TLS EOF")
    )
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


@respx.mock
def test_cli_uses_default_cookies_file_when_present(tmp_path, monkeypatch) -> None:
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(
        "# Netscape HTTP Cookie File\n"
        ".linux.do\tTRUE\t/\tTRUE\t2147483647\t_forum_session\txyz\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("linuxdo_reader.cli.default_cookies_file", lambda: cookies_file)
    route = respx.get("https://linux.do/top.rss").mock(
        return_value=httpx.Response(200, text=LATEST_RSS)
    )
    runner = CliRunner()

    result = runner.invoke(app, ["--db", str(tmp_path / "linuxdo.sqlite"), "refresh"])

    assert result.exit_code == 0
    assert route.calls.last.request.headers["cookie"] == "_forum_session=xyz"


@respx.mock
def test_cli_crawl_reports_partial_failures_and_keeps_going(tmp_path) -> None:
    respx.get("https://linux.do/top.rss").mock(
        return_value=httpx.Response(200, text=LATEST_RSS)
    )
    respx.get("https://linux.do/t/-/2489984.json").mock(
        return_value=httpx.Response(200, json=TOPIC_JSON)
    )
    respx.get("https://linux.do/t/2489984/posts.json").mock(
        return_value=httpx.Response(200, json=POSTS_JSON)
    )
    respx.get("https://linux.do/t/-/2491173.json").mock(
        return_value=httpx.Response(403)
    )
    respx.get("https://linux.do/t/topic/2491173.rss").mock(
        return_value=httpx.Response(403)
    )
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "--db",
            str(tmp_path / "linuxdo.sqlite"),
            "crawl",
            "--limit",
            "2",
            "--delay",
            "0",
        ],
    )

    assert result.exit_code == 0
    assert "2489984: cached 3 posts" in result.output
    assert "2491173: failed" in result.output


def test_cli_rejects_unknown_prefer_value(tmp_path) -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "--db",
            str(tmp_path / "linuxdo.sqlite"),
            "hydrate",
            "123",
            "--prefer",
            "browsr",
        ],
    )

    assert result.exit_code == 2
    assert "Invalid value" in result.output
    assert "browsr" in result.output


@respx.mock
def test_cli_hydrate_notes_rss_window_after_json_failure(tmp_path) -> None:
    respx.get("https://linux.do/t/-/2489984.json").mock(
        return_value=httpx.Response(403)
    )
    respx.get("https://linux.do/t/topic/2489984.rss").mock(
        return_value=httpx.Response(200, text=TOPIC_RSS)
    )
    runner = CliRunner()

    result = runner.invoke(
        app, ["--db", str(tmp_path / "linuxdo.sqlite"), "hydrate", "2489984"]
    )

    assert result.exit_code == 0
    assert "Cached 2 posts." in result.output
    assert "incomplete fetch from rss" in result.output
    assert "RSS exposes a recent window" in result.output


def test_cli_rejects_unknown_source_and_period(tmp_path) -> None:
    runner = CliRunner()

    bad_source = runner.invoke(
        app,
        ["--db", str(tmp_path / "db.sqlite"), "refresh", "--source", "latesst"],
    )
    bad_period = runner.invoke(
        app,
        ["--db", str(tmp_path / "db.sqlite"), "refresh", "--period", "daliy"],
    )

    assert bad_source.exit_code == 2
    assert "Invalid value" in bad_source.output
    assert bad_period.exit_code == 2
    assert "Invalid value" in bad_period.output


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


def test_cli_install_skill_local_agent_dir(tmp_path, monkeypatch) -> None:
    source = tmp_path / "source" / "linuxdo-reader"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("# Linux.do Reader\n", encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["install-skill", "--source", str(source), "--agent", "claude", "--local"],
    )

    expected = project / ".claude" / "skills" / "linuxdo-reader"
    assert result.exit_code == 0
    assert (expected / "SKILL.md").exists()


def test_cli_install_skill_rejects_unknown_agent(tmp_path) -> None:
    source = tmp_path / "source" / "linuxdo-reader"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("# Linux.do Reader\n", encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["install-skill", "--source", str(source), "--agent", "gemini"],
    )

    assert result.exit_code == 1
    assert "Unknown agent" in result.output
