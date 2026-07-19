from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Annotated, NoReturn, TypeVar

import httpx
import typer

from .cookies import default_cookies_file
from .service import CrawlReport, LinuxDoService
from .storage import Store

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}

app = typer.Typer(
    help="Helper CLI for the Linux.do Reader skill.",
    context_settings=CONTEXT_SETTINGS,
)
auth_app = typer.Typer(help="Manage Linux.do login cookies.", context_settings=CONTEXT_SETTINGS)
app.add_typer(auth_app, name="auth")

T = TypeVar("T")

PREFER_CHOICES = ("json", "rss", "browser")


def default_db_path() -> Path:
    return Path.home() / ".local" / "share" / "linuxdo-reader" / "linuxdo.sqlite"


def _fail(message: str) -> NoReturn:
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(1)


def _validate_prefer(prefer: str) -> None:
    if prefer not in PREFER_CHOICES:
        _fail(f"Unknown --prefer value {prefer!r}. Choose from: {', '.join(PREFER_CHOICES)}.")


def _run_cli(action: Callable[[], T]) -> T:
    try:
        return action()
    except (httpx.HTTPError, RuntimeError) as exc:
        _fail(str(exc))


@app.callback()
def main(
    ctx: typer.Context,
    db: Annotated[
        Path,
        typer.Option("--db", help="SQLite cache path."),
    ] = default_db_path(),
    cookies_file: Annotated[
        Path | None,
        typer.Option(
            "--cookies-file",
            envvar="LINUXDO_READER_COOKIES_FILE",
            help="Netscape cookies.txt file for linux.do.",
        ),
    ] = None,
    proxy: Annotated[
        str | None,
        typer.Option(
            "--proxy",
            envvar="LINUXDO_READER_PROXY",
            help="Proxy server for browser mode, for example http://127.0.0.1:7890.",
        ),
    ] = None,
) -> None:
    if cookies_file is None:
        default_cookies = default_cookies_file()
        if default_cookies.exists():
            cookies_file = default_cookies
    ctx.obj = {"db": db, "cookies_file": cookies_file, "proxy": proxy}


@app.command("refresh")
def refresh(
    ctx: typer.Context,
    source: Annotated[str, typer.Option("--source", help="top or latest")] = "top",
    period: Annotated[str, typer.Option("--period", help="Top period")] = "daily",
    limit: Annotated[int, typer.Option("--limit", min=1, max=100)] = 20,
) -> None:
    def action() -> list:
        with Store(ctx.obj["db"]) as store:
            service = LinuxDoService(
                store,
                cookies_file=ctx.obj["cookies_file"],
                proxy=ctx.obj["proxy"],
            )
            return (
                service.refresh_latest(limit=limit)
                if source == "latest"
                else service.refresh_top(period=period, limit=limit)
            )

    topics = _run_cli(action)
    typer.echo(f"Cached {len(topics)} topics.")


@app.command("hydrate")
def hydrate(
    ctx: typer.Context,
    topic: Annotated[str, typer.Argument(help="Topic id or linux.do topic URL.")],
    prefer: Annotated[str, typer.Option("--prefer", help="json, rss, or browser")] = "json",
) -> None:
    _validate_prefer(prefer)

    def action() -> list:
        with Store(ctx.obj["db"]) as store:
            service = LinuxDoService(
                store,
                cookies_file=ctx.obj["cookies_file"],
                proxy=ctx.obj["proxy"],
            )
            return service.hydrate_topic(topic, prefer=prefer)

    posts = _run_cli(action)
    typer.echo(f"Cached {len(posts)} posts.")
    if prefer == "json" and posts and all(post.source == "rss" for post in posts):
        typer.echo(
            "Note: JSON fetch failed, so this is the RSS window only "
            "(recent posts, not full history). Try --prefer browser for all floors.",
            err=True,
        )


@app.command("crawl")
def crawl(
    ctx: typer.Context,
    source: Annotated[str, typer.Option("--source", help="top or latest")] = "top",
    period: Annotated[str, typer.Option("--period", help="Top period")] = "daily",
    limit: Annotated[int, typer.Option("--limit", min=1, max=50)] = 10,
    prefer: Annotated[str, typer.Option("--prefer", help="json, rss, or browser")] = "json",
    delay: Annotated[
        float,
        typer.Option("--delay", min=0.0, max=30.0, help="Pause between topics in seconds."),
    ] = 0.5,
) -> None:
    _validate_prefer(prefer)

    def action() -> CrawlReport:
        with Store(ctx.obj["db"]) as store:
            service = LinuxDoService(
                store,
                cookies_file=ctx.obj["cookies_file"],
                proxy=ctx.obj["proxy"],
            )
            if source == "latest":
                return service.crawl_latest(limit=limit, prefer=prefer, delay=delay)
            return service.crawl_top(period=period, limit=limit, prefer=prefer, delay=delay)

    report = _run_cli(action)
    for topic_id, count in report.counts.items():
        typer.echo(f"{topic_id}: cached {count} posts")
    for topic_id, error in report.errors.items():
        typer.echo(f"{topic_id}: failed ({error})", err=True)
    if report.errors and not report.counts:
        _fail("All topics failed to hydrate.")


@app.command("digest")
def digest(
    ctx: typer.Context,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Write Markdown to a file. Omit to print to stdout."),
    ] = None,
    limit: Annotated[int, typer.Option("--limit", min=1, max=50)] = 10,
    comments_per_topic: Annotated[
        int,
        typer.Option(
            "--comments-per-topic",
            min=0,
            max=200,
            help="How many cached comments to show for each topic.",
        ),
    ] = 50,
) -> None:
    with Store(ctx.obj["db"]) as store:
        service = LinuxDoService(
            store,
            cookies_file=ctx.obj["cookies_file"],
            proxy=ctx.obj["proxy"],
        )
        rendered = service.render_daily_from_cache(
            limit=limit,
            comments_per_topic=comments_per_topic,
        )
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        typer.echo(str(output))
    else:
        typer.echo(rendered)


@app.command("topic")
def topic_digest(
    ctx: typer.Context,
    topic: Annotated[str, typer.Argument(help="Topic id or linux.do topic URL.")],
) -> None:
    with Store(ctx.obj["db"]) as store:
        service = LinuxDoService(
            store,
            cookies_file=ctx.obj["cookies_file"],
            proxy=ctx.obj["proxy"],
        )
        typer.echo(service.render_topic_from_cache(topic))


@app.command("search")
def search(
    ctx: typer.Context,
    query: Annotated[str, typer.Argument(help="Text to search in cached comments.")],
    limit: Annotated[int, typer.Option("--limit", min=1, max=100)] = 20,
) -> None:
    with Store(ctx.obj["db"]) as store:
        posts = store.search_posts(query, limit=limit)
    for post in posts:
        typer.echo(f"{post.url} #{post.post_number} {post.author}: {post.text}")


@app.command("browser-dump")
def browser_dump(
    topic: Annotated[str, typer.Argument(help="Topic id or linux.do topic URL.")],
    output: Annotated[Path, typer.Option("--output", "-o", help="Where to save rendered text.")],
    scroll_rounds: Annotated[int, typer.Option("--scroll-rounds", min=1, max=100)] = 12,
) -> None:
    from .browser import fetch_topic_with_browser

    text = _run_cli(lambda: fetch_topic_with_browser(topic, scroll_rounds=scroll_rounds))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    typer.echo(str(output))


@app.command("install-skill")
def install_skill(
    agent: Annotated[
        str | None,
        typer.Option(
            "--agent",
            help="Install into a known agent's skill dir: codex or claude. Defaults to codex. Ignored when --dest is set.",
        ),
    ] = None,
    local: Annotated[
        bool,
        typer.Option(
            "--local",
            help="Install into ./.<agent>/skills in the current directory instead of the home skills dir.",
        ),
    ] = False,
    dest: Annotated[
        Path | None,
        typer.Option("--dest", help="Explicit destination skill directory (overrides --agent/--local)."),
    ] = None,
    ref: Annotated[
        str | None,
        typer.Option("--ref", help="GitHub ref to install from. Defaults to this package version tag."),
    ] = None,
    source: Annotated[
        Path | None,
        typer.Option("--source", help="Install from a local skill directory instead of GitHub."),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", help="Replace an existing installed skill."),
    ] = False,
) -> None:
    """Install the bundled Skill without cloning the repository."""
    from .installer import (
        install_skill_from_directory,
        install_skill_from_github,
        resolve_skill_dest,
    )

    try:
        target = resolve_skill_dest(agent=agent, dest=dest, local=local)
    except ValueError as exc:
        _fail(str(exc))
    if source:
        installed = _run_cli(lambda: install_skill_from_directory(source, target, force=force))
    else:
        installed = _run_cli(lambda: install_skill_from_github(ref=ref, dest=target, force=force))
    typer.echo(f"Installed Skill to {installed}")
    typer.echo("Restart your agent to pick up the Skill.")


@auth_app.command("login")
def auth_login(
    cookies_file: Annotated[
        Path,
        typer.Option("--cookies-file", help="Where to write linux.do cookies."),
    ] = default_cookies_file(),
    proxy: Annotated[
        str | None,
        typer.Option(
            "--proxy",
            envvar="LINUXDO_READER_PROXY",
            help="Proxy server for browser mode, for example http://127.0.0.1:7890.",
        ),
    ] = None,
) -> None:
    from .browser import refresh_cookies_with_browser

    path = _run_cli(lambda: refresh_cookies_with_browser(cookies_file=cookies_file, proxy=proxy))
    typer.echo(f"Saved cookies to {path}")


@auth_app.command("refresh")
def auth_refresh(
    cookies_file: Annotated[
        Path,
        typer.Option("--cookies-file", help="Where to write linux.do cookies."),
    ] = default_cookies_file(),
    proxy: Annotated[
        str | None,
        typer.Option(
            "--proxy",
            envvar="LINUXDO_READER_PROXY",
            help="Proxy server for browser mode, for example http://127.0.0.1:7890.",
        ),
    ] = None,
) -> None:
    """Alias for `auth login`."""
    auth_login(cookies_file=cookies_file, proxy=proxy)


@app.command("seed-sample", hidden=True)
def seed_sample(ctx: typer.Context) -> None:
    from .sample_data import LATEST_RSS_SAMPLE

    with Store(ctx.obj["db"]) as store:
        service = LinuxDoService(store)
        store.upsert_topics(service.parse_topics_for_tests(LATEST_RSS_SAMPLE))
    typer.echo("Seeded sample topics.")
