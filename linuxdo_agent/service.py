from __future__ import annotations

from pathlib import Path

import httpx

from .client import LinuxDoClient
from .digest import render_daily_digest, render_topic_digest
from .feeds import parse_topic_list_feed, topic_id_from_url
from .models import Post, Topic
from .storage import Store


class LinuxDoService:
    def __init__(self, store: Store, client: LinuxDoClient | None = None) -> None:
        self.store = store
        self.client = client or LinuxDoClient()

    def refresh_top(self, period: str = "daily", limit: int = 20) -> list[Topic]:
        topics = self.client.fetch_top(period=period)[:limit]
        self.store.upsert_topics(topics)
        return topics

    def refresh_latest(self, limit: int = 20, order: str | None = None) -> list[Topic]:
        topics = self.client.fetch_latest(order=order)[:limit]
        self.store.upsert_topics(topics)
        return topics

    def hydrate_topic(self, topic: int | str, prefer: str = "json") -> list[Post]:
        topic_id = _coerce_topic_id(topic)
        posts: list[Post]
        if prefer == "rss":
            posts = self.client.fetch_topic_rss(topic_id)
        else:
            try:
                posts = self.client.fetch_topic_json(topic_id)
            except (httpx.HTTPError, ValueError, KeyError):
                posts = self.client.fetch_topic_rss(topic_id)
        self.store.upsert_posts(posts)
        return posts

    def render_topic_from_cache(self, topic: int | str) -> str:
        topic_id = _coerce_topic_id(topic)
        cached_topic = self.store.get_topic(topic_id)
        if cached_topic is None:
            cached_topic = Topic(
                topic_id=topic_id,
                title=f"Topic {topic_id}",
                url=f"https://linux.do/t/topic/{topic_id}",
                author="",
                category="",
                excerpt="",
                published_at="",
                source="manual",
            )
        return render_topic_digest(cached_topic, self.store.list_posts(topic_id))

    def render_daily_from_cache(self, limit: int = 10) -> str:
        topics = self.store.list_topics(limit=limit)
        posts_by_topic = {topic.topic_id: self.store.list_posts(topic.topic_id) for topic in topics}
        return render_daily_digest(topics, posts_by_topic)

    def write_daily_digest(self, output: str | Path, limit: int = 10) -> Path:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.render_daily_from_cache(limit=limit), encoding="utf-8")
        return path

    def parse_topics_for_tests(self, rss_text: str) -> list[Topic]:
        return parse_topic_list_feed(rss_text, source="sample")


def _coerce_topic_id(topic: int | str) -> int:
    if isinstance(topic, int):
        return topic
    if topic.isdigit():
        return int(topic)
    topic_id = topic_id_from_url(topic)
    if topic_id is None:
        raise ValueError(f"Cannot extract linux.do topic id from {topic!r}")
    return topic_id
