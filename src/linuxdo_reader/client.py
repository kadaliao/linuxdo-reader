from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from typing import TypeVar
from urllib.parse import urlencode

import httpx
from defusedxml.ElementTree import ParseError
from defusedxml.common import DefusedXmlException

from .cookies import load_cookie_jar
from .feeds import (
    canonical_topic_url,
    html_to_text,
    parse_topic_feed,
    parse_topic_list_feed,
)
from .models import FetchResult, Post, Topic

T = TypeVar("T")

RATE_LIMIT_MAX_WAIT = 10.0
RATE_LIMIT_ATTEMPTS = 3
MAX_FEED_BYTES = 2 * 1024 * 1024


class FeedTooLargeError(RuntimeError):
    pass


class LinuxDoClient:
    def __init__(
        self,
        base_url: str = "https://linux.do",
        timeout: float = 20.0,
        user_agent: str = "Mozilla/5.0 linuxdo-reader/0.1",
        cookies_file: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers={"User-Agent": user_agent},
            follow_redirects=True,
            cookies=load_cookie_jar(cookies_file),
        )
        self._sleep: Callable[[float], None] = time.sleep

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "LinuxDoClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def fetch_latest(self, order: str | None = None) -> list[Topic]:
        params = {"order": order} if order else None
        return self._fetch_feed_with_fallbacks(
            lambda text: parse_topic_list_feed(text, source="latest"),
            ("/latest.rss", params),
        )

    def fetch_top(self, period: str = "daily") -> list[Topic]:
        return self._fetch_feed_with_fallbacks(
            lambda text: parse_topic_list_feed(text, source=f"top:{period}"),
            ("/top.rss", {"period": period}),
            (f"/top/{period}.rss", None),
        )

    def fetch_topic_rss(self, topic_id: int) -> FetchResult:
        try:
            text = self._fetch_feed_text(f"/t/topic/{topic_id}.rss")
            posts = parse_topic_feed(text, topic_id=topic_id)
        except (ParseError, DefusedXmlException) as exc:
            raise RuntimeError(
                f"linux.do returned non-RSS content for topic {topic_id} "
                "(Cloudflare challenge or rate limit?)"
            ) from exc
        return FetchResult(
            posts=posts,
            complete=False,
            source="rss",
            error="RSS exposes a recent window, not guaranteed full history",
        )

    def fetch_topic_json(self, topic_id: int, chunk_size: int = 20) -> FetchResult:
        topic_json = self._fetch_topic_json_payload(topic_id)
        post_stream, stream = validated_post_stream(topic_json, topic_id)
        posts = posts_from_json(topic_id, post_stream["posts"], source="json")
        seen_ids = {post.post_id for post in posts}
        remaining = [post_id for post_id in stream if str(post_id) not in seen_ids]
        error: str | None = None
        for chunk in _chunks(remaining, chunk_size):
            params = [("post_ids[]", str(post_id)) for post_id in chunk]
            try:
                response = self._get_json_with_retry(
                    f"/t/{topic_id}/posts.json", params=params
                )
                page_posts = posts_from_pagination_payload(
                    response.json(), topic_id, source="json"
                )
            except (httpx.HTTPError, TypeError, ValueError) as exc:
                error = f"JSON pagination stopped after {len(posts)} posts: {exc}"
                break
            for post in page_posts:
                if post.post_id not in seen_ids:
                    posts.append(post)
                    seen_ids.add(post.post_id)
        posts = sorted(posts, key=lambda post: post.post_number)
        expected_count = len(stream) if stream else len(posts)
        complete = error is None and all(str(post_id) in seen_ids for post_id in stream)
        if not complete and error is None:
            missing_count = sum(str(post_id) not in seen_ids for post_id in stream)
            error = f"JSON responses omitted {missing_count} expected posts"
        return FetchResult(
            posts=posts,
            complete=complete,
            source="json",
            error=error,
            expected_count=expected_count,
        )

    def _fetch_topic_json_payload(self, topic_id: int) -> dict[str, object]:
        # print=true returns up to 1000 posts in one response but Discourse
        # rate-limits it aggressively; the plain topic JSON still exposes the
        # full post id stream for chunked pagination.
        try:
            response = self._get_json_with_retry(
                f"/t/-/{topic_id}.json", params={"print": "true"}
            )
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            response = self._get_json_with_retry(f"/t/-/{topic_id}.json")
            payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError(f"Unexpected JSON payload for topic {topic_id}")
        return payload

    def _get_json_with_retry(
        self,
        path: str,
        params: object = None,
        attempts: int = RATE_LIMIT_ATTEMPTS,
    ) -> httpx.Response:
        for attempt in range(attempts):
            response = self._client.get(path, params=params)
            if response.status_code == 429 and attempt < attempts - 1:
                self._sleep(_retry_after_seconds(response, attempt))
                continue
            response.raise_for_status()
            return response
        raise httpx.HTTPError(f"Exhausted retries for {path}")

    def _fetch_feed_with_fallbacks(
        self,
        parser: Callable[[str], list[T]],
        *requests: tuple[str, dict[str, str] | None],
        attempts: int = 2,
    ) -> list[T]:
        errors: list[tuple[str, Exception]] = []
        for path, params in requests:
            for _ in range(attempts):
                try:
                    parsed = parser(self._fetch_feed_text(path, params=params))
                except httpx.HTTPError as exc:
                    errors.append((_format_path(path, params), exc))
                    continue
                except FeedTooLargeError as exc:
                    errors.append((_format_path(path, params), exc))
                    break
                except (ParseError, DefusedXmlException) as exc:
                    errors.append(
                        (
                            _format_path(path, params),
                            RuntimeError(
                                "non-RSS response, likely a Cloudflare challenge "
                                f"or rate limit ({exc})"
                            ),
                        )
                    )
                    break
                if parsed:
                    return parsed
                # An XHTML challenge page can parse as XML yet carry no items.
                errors.append(
                    (
                        _format_path(path, params),
                        RuntimeError(
                            "feed parsed but contained no items (challenge page?)"
                        ),
                    )
                )
                break
        raise httpx.HTTPError(_format_fallback_errors(errors))

    def _fetch_feed_text(
        self,
        path: str,
        params: dict[str, str] | None = None,
        max_bytes: int = MAX_FEED_BYTES,
    ) -> str:
        chunks: list[bytes] = []
        size = 0
        with self._client.stream("GET", path, params=params) as response:
            response.raise_for_status()
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > max_bytes:
                    raise FeedTooLargeError(
                        f"Feed exceeded the {max_bytes}-byte response limit"
                    )
                chunks.append(chunk)
            encoding = response.encoding or "utf-8"
        return b"".join(chunks).decode(encoding, errors="replace")


def validated_post_stream(
    payload: dict[str, object], topic_id: int
) -> tuple[dict[str, list[object]], list[int]]:
    raw_post_stream = payload.get("post_stream")
    if not isinstance(raw_post_stream, dict):
        raise ValueError(f"Topic {topic_id} JSON has no post_stream object")
    raw_stream = raw_post_stream.get("stream")
    raw_posts = raw_post_stream.get("posts", [])
    if not isinstance(raw_stream, list) or not raw_stream:
        raise ValueError(f"Topic {topic_id} JSON has an empty post stream")
    if not isinstance(raw_posts, list):
        raise ValueError(f"Topic {topic_id} JSON has invalid embedded posts")
    try:
        stream = [int(post_id) for post_id in raw_stream]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Topic {topic_id} JSON has invalid post ids") from exc
    return {"stream": raw_stream, "posts": raw_posts}, stream


def posts_from_pagination_payload(
    payload: object, topic_id: int, source: str
) -> list[Post]:
    if not isinstance(payload, dict):
        raise ValueError(f"Topic {topic_id} pagination JSON is not an object")
    post_stream = payload.get("post_stream")
    if not isinstance(post_stream, dict):
        raise ValueError(f"Topic {topic_id} pagination JSON has no post_stream object")
    items = post_stream.get("posts")
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        raise ValueError(f"Topic {topic_id} pagination JSON has invalid posts")
    return posts_from_json(topic_id, items, source=source)


def posts_from_json(topic_id: int, items: list[object], source: str) -> list[Post]:
    return [
        _post_from_json(topic_id, item, source=source)
        for item in items
        if isinstance(item, dict)
    ]


def _post_from_json(topic_id: int, item: dict[str, object], source: str) -> Post:
    post_id = str(item.get("id", ""))
    post_number = int(item.get("post_number", 0))
    post_url = str(item.get("post_url") or "")
    url = post_url if post_url.startswith("http") else f"https://linux.do{post_url}"
    if not post_url:
        url = f"{canonical_topic_url(topic_id)}/{post_number}"
    cooked = str(item.get("cooked") or "")
    return Post(
        topic_id=topic_id,
        post_id=post_id,
        post_number=post_number,
        author=str(item.get("username") or ""),
        text=html_to_text(cooked),
        cooked=cooked,
        url=url,
        created_at=str(item.get("created_at") or ""),
        source=source,
    )


def _retry_after_seconds(response: httpx.Response, attempt: int) -> float:
    header = response.headers.get("Retry-After", "")
    try:
        seconds = float(header)
    except ValueError:
        seconds = 2.0 * (attempt + 1)
    return max(0.5, min(seconds, RATE_LIMIT_MAX_WAIT))


def _chunks(values: list[int], size: int) -> Iterable[list[int]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def _format_path(path: str, params: dict[str, str] | None) -> str:
    if not params:
        return path
    return f"{path}?{urlencode(params)}"


def _format_fallback_errors(errors: list[tuple[str, Exception]]) -> str:
    details = "; ".join(
        f"{path}: {type(error).__name__}: {error}" for path, error in errors
    )
    return f"All linux.do feed requests failed. Tried {details}"
