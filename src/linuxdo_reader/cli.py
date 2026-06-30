from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Annotated, NoReturn, TypeVar

import httpx
import typer

from .service import LinuxDoService
from .storage import Store

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}

app = typer.Typer(
    help="Helper CLI for the Linux.do Reader skill.",
    context_settings=CONTEXT_SETTINGS,
)

T = TypeVar("T")


def default_db_path() -> Path:
    return Path.home() / ".local" / "share" / "linuxdo-reader" / "linuxdo.sqlite"


def _fail(message: str) -> NoReturn:
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(1)


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
) -> None:
    ctx.obj = {"db": db}


@app.command("refresh")
def refresh(
    ctx: typer.Context,
    source: Annotated[str, typer.Option("--source", help="top or latest")] = "top",
    period: Annotated[str, typer.Option("--period", help="Top period")] = "daily",
    limit: Annotated[int, typer.Option("--limit", min=1, max=100)] = 20,
) -> None:
    def action() -> list:
        with Store(ctx.obj["db"]) as store:
            service = LinuxDoService(store)
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
    def action() -> list:
        with Store(ctx.obj["db"]) as store:
            service = LinuxDoService(store)
            return service.hydrate_topic(topic, prefer=prefer)

    posts = _run_cli(action)
    typer.echo(f"Cached {len(posts)} posts.")


@app.command("crawl")
def crawl(
    ctx: typer.Context,
    source: Annotated[str, typer.Option("--source", help="top or latest")] = "top",
    period: Annotated[str, typer.Option("--period", help="Top period")] = "daily",
    limit: Annotated[int, typer.Option("--limit", min=1, max=50)] = 10,
    prefer: Annotated[str, typer.Option("--prefer", help="json, rss, or browser")] = "json",
) -> None:
    def action() -> dict[int, int]:
        with Store(ctx.obj["db"]) as store:
            service = LinuxDoService(store)
            if source == "latest":
                topics = service.refresh_latest(limit=limit)
                return {
                    topic.topic_id: len(service.hydrate_topic(topic.topic_id, prefer=prefer))
                    for topic in topics
                }
            return service.crawl_top(period=period, limit=limit, prefer=prefer)

    report = _run_cli(action)
    for topic_id, count in report.items():
        typer.echo(f"{topic_id}: cached {count} posts")


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
            max=100,
            help="How many cached comments to show for each topic.",
        ),
    ] = 12,
) -> None:
    with Store(ctx.obj["db"]) as store:
        service = LinuxDoService(store)
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
        service = LinuxDoService(store)
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


@app.command("seed-sample", hidden=True)
def seed_sample(ctx: typer.Context) -> None:
    from .sample_data import LATEST_RSS_SAMPLE

    with Store(ctx.obj["db"]) as store:
        service = LinuxDoService(store)
        store.upsert_topics(service.parse_topics_for_tests(LATEST_RSS_SAMPLE))
    typer.echo("Seeded sample topics.")
