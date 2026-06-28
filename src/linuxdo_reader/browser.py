from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .client import posts_from_json
from .feeds import canonical_topic_url, topic_id_from_url
from .models import Post


def build_topic_url(topic: str) -> str:
    if topic.startswith("https://linux.do/t/"):
        return topic.split("?")[0].rstrip("/")
    topic_id = int(topic)
    return canonical_topic_url(topic_id)


def fetch_topic_with_browser(topic: str, scroll_rounds: int = 12) -> str:
    """Fetch rendered topic text with Playwright when HTTP API is blocked.

    This is intentionally optional. Install Playwright separately with:
    `uv pip install playwright && uv run playwright install chromium`.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Browser mode requires Playwright. Install it with "
            "`uv pip install playwright && uv run playwright install chromium`."
        ) from exc

    url = build_topic_url(topic)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        for _ in range(scroll_rounds):
            page.mouse.wheel(0, 5000)
            page.wait_for_timeout(800)
        text = page.locator("body").inner_text()
        browser.close()
        return text


def fetch_topic_posts_with_browser(
    topic: int | str,
    chunk_size: int = 20,
    headless: bool = False,
    status_callback: Callable[[str], None] | None = None,
) -> list[Post]:
    """Fetch topic posts through a real browser session.

    This uses Playwright to let the site complete any browser checks, then runs
    same-origin fetch calls inside the page to read Discourse JSON endpoints.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Browser hydrate requires Playwright. Install it with "
            "`uv pip install playwright && uv run playwright install chromium`."
        ) from exc

    topic_id = topic_id_from_any(str(topic))
    url = build_topic_url(str(topic))
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        page = browser.new_page()
        _status(status_callback, f"Opening {url}")
        page.goto(url, wait_until="networkidle")
        topic_json = _page_fetch_json(page, f"/t/-/{topic_id}.json?print=true")
        post_stream = topic_json.get("post_stream", {})
        stream = [int(post_id) for post_id in post_stream.get("stream", [])]
        posts = posts_from_json(topic_id, post_stream.get("posts", []), source="browser")
        seen_ids = {post.post_id for post in posts}
        remaining = [post_id for post_id in stream if str(post_id) not in seen_ids]
        for index in range(0, len(remaining), chunk_size):
            chunk = remaining[index : index + chunk_size]
            query = "&".join(f"post_ids[]={post_id}" for post_id in chunk)
            _status(status_callback, f"Fetching posts {index + 1}-{index + len(chunk)}")
            payload = _page_fetch_json(page, f"/t/{topic_id}/posts.json?{query}")
            for post in posts_from_json(
                topic_id,
                payload.get("post_stream", {}).get("posts", []),
                source="browser",
            ):
                if post.post_id not in seen_ids:
                    posts.append(post)
                    seen_ids.add(post.post_id)
        browser.close()
    return sorted(posts, key=lambda post: post.post_number)


def topic_id_from_any(value: str) -> int:
    if value.isdigit():
        return int(value)
    topic_id = topic_id_from_url(value)
    if topic_id is None:
        raise ValueError(f"Cannot extract linux.do topic id from {value!r}")
    return topic_id


def _page_fetch_json(page: Any, path: str) -> dict[str, Any]:
    result = page.evaluate(
        """async (path) => {
            const response = await fetch(path, {
              credentials: "same-origin",
              headers: { "accept": "application/json" }
            });
            const text = await response.text();
            if (!response.ok) {
              throw new Error(`${response.status} ${response.statusText}: ${text.slice(0, 300)}`);
            }
            return JSON.parse(text);
        }""",
        path,
    )
    if not isinstance(result, dict):
        raise RuntimeError(f"Expected JSON object from {path}")
    return result


def _status(callback: Callable[[str], None] | None, message: str) -> None:
    if callback:
        callback(message)
