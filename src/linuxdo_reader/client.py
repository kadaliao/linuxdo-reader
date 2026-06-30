from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlencode

import httpx

from .feeds import canonical_topic_url, html_to_text, parse_topic_feed, parse_topic_list_feed
from .models import Post, Topic


class LinuxDoClient:
    def __init__(
        self,
        base_url: str = "https://linux.do",
        timeout: float = 20.0,
        user_agent: str = "Mozilla/5.0 linuxdo-reader/0.1",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers={"User-Agent": user_agent},
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "LinuxDoClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def fetch_latest(self, order: str | None = None) -> list[Topic]:
        path = "/latest.rss"
        params = {"order": order} if order else None
        response = self._client.get(path, params=params)
        response.raise_for_status()
        return parse_topic_list_feed(response.text, source="latest")

    def fetch_top(self, period: str = "daily") -> list[Topic]:
        response = self._get_with_fallbacks(
            ("/top.rss", {"period": period}),
            (f"/top/{period}.rss", None),
        )
        return parse_topic_list_feed(response.text, source=f"top:{period}")

    def fetch_topic_rss(self, topic_id: int) -> list[Post]:
        response = self._client.get(f"/t/topic/{topic_id}.rss")
        response.raise_for_status()
        return parse_topic_feed(response.text, topic_id=topic_id)

    def fetch_topic_json(self, topic_id: int, chunk_size: int = 20) -> list[Post]:
        topic_response = self._client.get(f"/t/-/{topic_id}.json", params={"print": "true"})
        topic_response.raise_for_status()
        topic_json = topic_response.json()
        post_stream = topic_json.get("post_stream", {})
        stream = [int(post_id) for post_id in post_stream.get("stream", [])]
        posts = posts_from_json(topic_id, post_stream.get("posts", []), source="json")
        seen_ids = {post.post_id for post in posts}
        remaining = [post_id for post_id in stream if str(post_id) not in seen_ids]
        for chunk in _chunks(remaining, chunk_size):
            params = [("post_ids[]", str(post_id)) for post_id in chunk]
            response = self._client.get(f"/t/{topic_id}/posts.json", params=params)
            response.raise_for_status()
            for item in response.json().get("post_stream", {}).get("posts", []):
                post = _post_from_json(topic_id, item, source="json")
                if post.post_id not in seen_ids:
                    posts.append(post)
                    seen_ids.add(post.post_id)
        return sorted(posts, key=lambda post: post.post_number)

    def _get_with_fallbacks(
        self,
        *requests: tuple[str, dict[str, str] | None],
        attempts: int = 2,
    ) -> httpx.Response:
        errors: list[tuple[str, httpx.HTTPError]] = []
        for path, params in requests:
            for _ in range(attempts):
                try:
                    response = self._client.get(path, params=params)
                    response.raise_for_status()
                    return response
                except httpx.HTTPError as exc:
                    errors.append((_format_path(path, params), exc))
        raise httpx.HTTPError(_format_fallback_errors(errors))


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


def _chunks(values: list[int], size: int) -> Iterable[list[int]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def _format_path(path: str, params: dict[str, str] | None) -> str:
    if not params:
        return path
    return f"{path}?{urlencode(params)}"


def _format_fallback_errors(errors: list[tuple[str, httpx.HTTPError]]) -> str:
    details = "; ".join(
        f"{path}: {type(error).__name__}: {error}" for path, error in errors
    )
    return f"All linux.do feed requests failed. Tried {details}"
