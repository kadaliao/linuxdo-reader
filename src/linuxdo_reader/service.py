from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path

import httpx

from .client import LinuxDoClient
from .digest import render_daily_digest, render_topic_digest
from .feeds import parse_topic_list_feed, topic_id_from_url
from .models import FetchResult, Post, Topic
from .storage import Store


@dataclass(frozen=True)
class CrawlReport:
    """Per-topic hydration outcome for a crawl run."""

    results: dict[int, FetchResult] = field(default_factory=dict)
    errors: dict[int, str] = field(default_factory=dict)

    @property
    def counts(self) -> dict[int, int]:
        return {
            topic_id: result.fetched_count for topic_id, result in self.results.items()
        }


class LinuxDoService:
    def __init__(
        self,
        store: Store,
        client: LinuxDoClient | None = None,
        browser_fetcher: Callable[[int], FetchResult] | None = None,
        browser_top_fetcher: Callable[[str, int], list[Topic]] | None = None,
        cookies_file: str | None = None,
        proxy: str | None = None,
    ) -> None:
        self.store = store
        self.client = client or LinuxDoClient(cookies_file=cookies_file)
        self.browser_fetcher = browser_fetcher
        self.browser_top_fetcher = browser_top_fetcher
        self.cookies_file = cookies_file
        self.proxy = proxy

    def refresh_top(self, period: str = "daily", limit: int = 20) -> list[Topic]:
        return self._refresh_topics(
            source="top",
            period=period,
            fetch=lambda: self.client.fetch_top(period=period)[:limit],
        )

    def refresh_latest(self, limit: int = 20, order: str | None = None) -> list[Topic]:
        return self._refresh_topics(
            source="latest",
            period=None,
            fetch=lambda: self.client.fetch_latest(order=order)[:limit],
        )

    def hydrate_topic(self, topic: int | str, prefer: str = "json") -> FetchResult:
        topic_id = _coerce_topic_id(topic)
        if prefer == "browser":
            result = self._fetch_topic_browser(topic_id)
        elif prefer == "rss":
            result = self.client.fetch_topic_rss(topic_id)
        else:
            try:
                result = self.client.fetch_topic_json(topic_id)
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                rss_result = self.client.fetch_topic_rss(topic_id)
                result = replace(
                    rss_result,
                    error=f"JSON fetch failed ({exc}); {rss_result.error}",
                )
        if result.complete:
            self.store.replace_posts(topic_id, result.posts)
        else:
            self.store.upsert_posts(result.posts)
        self.store.record_fetch_result(topic_id, result)
        return result

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
        return render_topic_digest(
            cached_topic,
            self.store.list_posts(topic_id),
            fetch_result=self.store.get_fetch_result(topic_id),
        )

    def render_daily_from_cache(
        self, limit: int = 10, comments_per_topic: int = 50
    ) -> str:
        topics = self.store.list_topics(limit=limit)
        posts_by_topic = {
            topic.topic_id: self.store.list_posts(topic.topic_id) for topic in topics
        }
        fetch_results = {
            topic.topic_id: self.store.get_fetch_result(topic.topic_id)
            for topic in topics
        }
        return render_daily_digest(
            topics,
            posts_by_topic,
            comments_per_topic=comments_per_topic,
            fetch_results=fetch_results,
        )

    def write_daily_digest(
        self,
        output: str | Path,
        limit: int = 10,
        comments_per_topic: int = 50,
    ) -> Path:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            self.render_daily_from_cache(
                limit=limit, comments_per_topic=comments_per_topic
            ),
            encoding="utf-8",
        )
        return path

    def parse_topics_for_tests(self, rss_text: str) -> list[Topic]:
        return parse_topic_list_feed(rss_text, source="sample")

    def crawl_top(
        self,
        period: str = "daily",
        limit: int = 10,
        prefer: str = "json",
        delay: float = 0.5,
    ) -> CrawlReport:
        try:
            topics = self.refresh_top(period=period, limit=limit)
        except httpx.HTTPError:
            if prefer != "browser":
                raise
            topics = self._refresh_topics(
                source="top:browser",
                period=period,
                fetch=lambda: self._fetch_top_browser(period=period, limit=limit),
            )
        return self._hydrate_topics(topics, prefer=prefer, delay=delay)

    def crawl_latest(
        self,
        limit: int = 20,
        prefer: str = "json",
        delay: float = 0.5,
        order: str | None = None,
    ) -> CrawlReport:
        topics = self.refresh_latest(limit=limit, order=order)
        return self._hydrate_topics(topics, prefer=prefer, delay=delay)

    def _hydrate_topics(
        self, topics: list[Topic], prefer: str, delay: float
    ) -> CrawlReport:
        results: dict[int, FetchResult] = {}
        errors: dict[int, str] = {}
        for index, topic in enumerate(topics):
            if index and delay > 0:
                time.sleep(delay)
            try:
                results[topic.topic_id] = self.hydrate_topic(
                    topic.topic_id, prefer=prefer
                )
            except (httpx.HTTPError, RuntimeError) as exc:
                # One rate-limited or blocked topic must not abort the crawl;
                # keep hydrating the rest and report the failure.
                errors[topic.topic_id] = str(exc)
        return CrawlReport(results=results, errors=errors)

    def make_post_for_tests(self, topic_id: int, post_number: int, text: str) -> Post:
        return Post(
            topic_id=topic_id,
            post_id=f"{topic_id}-{post_number}",
            post_number=post_number,
            author="test",
            text=text,
            cooked=text,
            url=f"https://linux.do/t/topic/{topic_id}/{post_number}",
            created_at="",
            source="test",
        )

    def _refresh_topics(
        self,
        source: str,
        period: str | None,
        fetch: Callable[[], list[Topic]],
    ) -> list[Topic]:
        batch_id = self.store.start_refresh_batch(source, period)
        try:
            topics = fetch()
            if not topics:
                raise RuntimeError(f"{source} refresh returned no topics")
            self.store.upsert_topics(topics, batch_id=batch_id)
            self.store.finish_refresh_batch(batch_id, complete=True)
            return topics
        except Exception as exc:
            self.store.finish_refresh_batch(batch_id, complete=False, error=str(exc))
            raise

    def _fetch_topic_browser(self, topic_id: int) -> FetchResult:
        if self.browser_fetcher:
            return self.browser_fetcher(topic_id)
        from .browser import fetch_topic_posts_with_browser

        return fetch_topic_posts_with_browser(
            topic_id,
            cookies_file=self.cookies_file,
            proxy=self.proxy,
        )

    def _fetch_top_browser(self, period: str, limit: int) -> list[Topic]:
        if self.browser_top_fetcher:
            return self.browser_top_fetcher(period, limit)
        from .browser import fetch_top_topics_with_browser

        return fetch_top_topics_with_browser(
            period=period,
            limit=limit,
            cookies_file=self.cookies_file,
            proxy=self.proxy,
        )


def _coerce_topic_id(topic: int | str) -> int:
    if isinstance(topic, int):
        return topic
    if topic.isdigit():
        return int(topic)
    topic_id = topic_id_from_url(topic)
    if topic_id is None:
        raise ValueError(f"Cannot extract linux.do topic id from {topic!r}")
    return topic_id
