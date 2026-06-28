from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .cli import default_db_path
from .service import LinuxDoService
from .storage import Store

mcp = FastMCP("linuxdo-agent")


def _db_path() -> Path:
    return Path(os.environ.get("LINUXDO_AGENT_DB", default_db_path()))


@mcp.tool()
def refresh_hot_topics(period: str = "daily", limit: int = 20) -> str:
    """Fetch Linux.do daily top topics from RSS and cache them locally."""
    with Store(_db_path()) as store:
        service = LinuxDoService(store)
        topics = service.refresh_top(period=period, limit=limit)
    return "\n".join(f"{topic.topic_id} {topic.title} {topic.url}" for topic in topics)


@mcp.tool()
def refresh_latest_topics(limit: int = 20) -> str:
    """Fetch Linux.do latest topics from RSS and cache them locally."""
    with Store(_db_path()) as store:
        service = LinuxDoService(store)
        topics = service.refresh_latest(limit=limit)
    return "\n".join(f"{topic.topic_id} {topic.title} {topic.url}" for topic in topics)


@mcp.tool()
def hydrate_topic(topic: str, prefer: str = "json") -> str:
    """Fetch and cache comments for a Linux.do topic by URL or topic id."""
    with Store(_db_path()) as store:
        service = LinuxDoService(store)
        posts = service.hydrate_topic(topic, prefer=prefer)
    return f"Cached {len(posts)} posts for {topic}."


@mcp.tool()
def summarize_topic(topic: str) -> str:
    """Render a cached topic discussion digest."""
    with Store(_db_path()) as store:
        service = LinuxDoService(store)
        return service.render_topic_from_cache(topic)


@mcp.tool()
def daily_digest(limit: int = 10) -> str:
    """Render a cached Linux.do daily hot topic digest."""
    with Store(_db_path()) as store:
        service = LinuxDoService(store)
        return service.render_daily_from_cache(limit=limit)


@mcp.tool()
def search_cache(query: str, limit: int = 20) -> str:
    """Search cached Linux.do comments locally."""
    with Store(_db_path()) as store:
        posts = store.search_posts(query, limit=limit)
    return "\n".join(f"{post.url} #{post.post_number} {post.author}: {post.text}" for post in posts)


def main() -> None:
    mcp.run()
