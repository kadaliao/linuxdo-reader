from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from .service import LinuxDoService
from .storage import Store

app = typer.Typer(help="Linux.do topic and comment reader with local cache.")


def default_db_path() -> Path:
    return Path.home() / ".local" / "share" / "linuxdo-reader" / "linuxdo.sqlite"


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
    with Store(ctx.obj["db"]) as store:
        service = LinuxDoService(store)
        topics = (
            service.refresh_latest(limit=limit)
            if source == "latest"
            else service.refresh_top(period=period, limit=limit)
        )
    typer.echo(f"Cached {len(topics)} topics.")


@app.command("hydrate")
def hydrate(
    ctx: typer.Context,
    topic: Annotated[str, typer.Argument(help="Topic id or linux.do topic URL.")],
    prefer: Annotated[str, typer.Option("--prefer", help="json or rss")] = "json",
) -> None:
    with Store(ctx.obj["db"]) as store:
        service = LinuxDoService(store)
        posts = service.hydrate_topic(topic, prefer=prefer)
    typer.echo(f"Cached {len(posts)} posts.")


@app.command("digest")
def digest(
    ctx: typer.Context,
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
    limit: Annotated[int, typer.Option("--limit", min=1, max=50)] = 10,
) -> None:
    with Store(ctx.obj["db"]) as store:
        service = LinuxDoService(store)
        rendered = service.render_daily_from_cache(limit=limit)
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

    text = fetch_topic_with_browser(topic, scroll_rounds=scroll_rounds)
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
