from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from .client import posts_from_json
from .cookies import (
    default_browser_profile_dir,
    load_playwright_cookies,
    write_netscape_cookies,
)
from .feeds import canonical_topic_url, topic_id_from_url
from .models import Post, Topic

PLAYWRIGHT_INSTALL_HINT = (
    "Browser mode requires Playwright. "
    "If you installed linuxdo-reader as a uv tool, run "
    "`uv tool install git+https://github.com/kadaliao/linuxdo-reader --with playwright --force` "
    "and then `uv tool run playwright install chromium`. "
    "In a source checkout, run `uv pip install playwright && uv run playwright install chromium`."
)


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
        raise RuntimeError(PLAYWRIGHT_INSTALL_HINT) from exc

    url = build_topic_url(topic)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=False)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded")
            for _ in range(scroll_rounds):
                page.mouse.wheel(0, 5000)
                page.wait_for_timeout(800)
            text = page.locator("body").inner_text()
            browser.close()
            return text
    except Exception as exc:
        raise RuntimeError(_browser_error_message(exc)) from exc


def fetch_top_topics_with_browser(
    period: str = "daily",
    limit: int = 10,
    headless: bool = False,
    cookies_file: str | Path | None = None,
    status_callback: Callable[[str], None] | None = None,
) -> list[Topic]:
    """Fetch the top topic list from the rendered Discourse page."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(PLAYWRIGHT_INSTALL_HINT) from exc

    url = f"https://linux.do/top?period={period}"
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=headless)
            context = browser.new_context()
            _add_context_cookies(context, cookies_file)
            page = context.new_page()
            _status(status_callback, f"Opening {url}")
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_selector("tr.topic-list-item", timeout=20_000)
            rows = page.evaluate(
                """(limit) => {
                    const rows = Array.from(document.querySelectorAll("tr.topic-list-item"));
                    return rows.slice(0, limit).map((row) => {
                      const titleLink =
                        row.querySelector("a.title, a.raw-topic-link, .main-link a");
                      const excerpt = Array.from(row.querySelectorAll("a.discourse-tag"))
                        .map((tag) => tag.textContent.trim())
                        .filter(Boolean)
                        .join(" ");
                      const category =
                        row.querySelector(".category-name")?.textContent?.trim() || "";
                      const nums = Array.from(row.querySelectorAll("td.num, .num"))
                        .map((cell) => cell.textContent.trim())
                        .filter(Boolean);
                      return {
                        title: titleLink?.textContent?.trim() || "",
                        url: titleLink?.href || "",
                        category,
                        excerpt,
                        reply_count: nums[0] || "",
                        views: nums[1] || "",
                        activity: nums[2] || "",
                      };
                    }).filter((row) => row.title && row.url);
                }""",
                limit,
            )
            context.close()
            browser.close()
    except Exception as exc:
        raise RuntimeError(_browser_error_message(exc)) from exc
    return topics_from_browser_rows(rows, source=f"top:{period}:browser")[:limit]


def refresh_cookies_with_browser(
    cookies_file: str | Path,
    profile_dir: str | Path | None = None,
    headless: bool = False,
    status_callback: Callable[[str], None] | None = None,
) -> Path:
    """Open Linux.do with a persistent browser profile and export cookies."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(PLAYWRIGHT_INSTALL_HINT) from exc

    profile_path = Path(profile_dir).expanduser() if profile_dir else default_browser_profile_dir()
    profile_path.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                str(profile_path),
                headless=headless,
            )
            page = context.pages[0] if context.pages else context.new_page()
            _status(status_callback, "Opening https://linux.do/top?period=daily")
            page.goto("https://linux.do/top?period=daily", wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            path = export_context_cookies(context, cookies_file)
            context.close()
            return path
    except Exception as exc:
        raise RuntimeError(_browser_error_message(exc)) from exc


def fetch_topic_posts_with_browser(
    topic: int | str,
    chunk_size: int = 20,
    headless: bool = False,
    cookies_file: str | Path | None = None,
    status_callback: Callable[[str], None] | None = None,
) -> list[Post]:
    """Fetch topic posts through a real browser session.

    This uses Playwright to let the site complete any browser checks, then runs
    same-origin fetch calls inside the page to read Discourse JSON endpoints.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(PLAYWRIGHT_INSTALL_HINT) from exc

    topic_id = topic_id_from_any(str(topic))
    url = build_topic_url(str(topic))
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=headless)
            context = browser.new_context()
            _add_context_cookies(context, cookies_file)
            page = context.new_page()
            _status(status_callback, f"Opening {url}")
            page.goto(url, wait_until="domcontentloaded")
            try:
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
            except Exception:
                _status(status_callback, "Falling back to rendered page text")
                posts = _page_posts_from_rendered_topic(page, topic_id)
            context.close()
            browser.close()
    except Exception as exc:
        raise RuntimeError(_browser_error_message(exc)) from exc
    return sorted(posts, key=lambda post: post.post_number)


def topics_from_browser_rows(rows: list[object], source: str) -> list[Topic]:
    topics: list[Topic] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        url = str(row.get("url") or "")
        topic_id = topic_id_from_url(url)
        title = str(row.get("title") or "").strip()
        if topic_id is None or not title:
            continue
        topics.append(
            Topic(
                topic_id=topic_id,
                title=title,
                url=canonical_topic_url(topic_id),
                author="",
                category=str(row.get("category") or ""),
                excerpt=str(row.get("excerpt") or ""),
                published_at="",
                source=source,
                reply_count=_parse_count(row.get("reply_count")),
            )
        )
    return topics


def export_context_cookies(context: Any, cookies_file: str | Path) -> Path:
    cookies = context.cookies(["https://linux.do"])
    return write_netscape_cookies(cookies_file, cookies)


def _add_context_cookies(context: Any, cookies_file: str | Path | None) -> None:
    cookies = load_playwright_cookies(cookies_file)
    if cookies:
        context.add_cookies(cookies)


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


def _page_posts_from_rendered_topic(page: Any, topic_id: int) -> list[Post]:
    rows = page.evaluate(
        """() => {
            const selectors = [
              "article[data-post-id]",
              "article",
              ".topic-post",
              "[data-post-number]"
            ];
            const seen = new Set();
            const posts = [];
            for (const selector of selectors) {
              for (const node of Array.from(document.querySelectorAll(selector))) {
                const text = (node.innerText || "").replace(/\\s+/g, " ").trim();
                if (!text || seen.has(text)) continue;
                seen.add(text);
                const postNumber =
                  node.getAttribute("data-post-number") ||
                  node.querySelector("[data-post-number]")?.getAttribute("data-post-number") ||
                  "";
                const postId =
                  node.getAttribute("data-post-id") ||
                  node.querySelector("[data-post-id]")?.getAttribute("data-post-id") ||
                  "";
                const author =
                  node.querySelector("[data-user-card], .names a, .username")?.textContent?.trim() ||
                  "";
                posts.push({ postNumber, postId, author, text });
              }
            }
            return posts;
        }"""
    )
    posts: list[Post] = []
    for index, row in enumerate(rows if isinstance(rows, list) else [], start=1):
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        post_number = _parse_count(row.get("postNumber")) or index
        post_id = str(row.get("postId") or f"rendered-{post_number}")
        posts.append(
            Post(
                topic_id=topic_id,
                post_id=post_id,
                post_number=post_number,
                author=str(row.get("author") or ""),
                text=text,
                cooked=text,
                url=f"{canonical_topic_url(topic_id)}/{post_number}",
                created_at="",
                source="browser:page",
            )
        )
    return posts


def _status(callback: Callable[[str], None] | None, message: str) -> None:
    if callback:
        callback(message)


def _parse_count(value: object) -> int | None:
    text = str(value or "").strip().lower().replace(",", "")
    if not text:
        return None
    multiplier = 1
    if text.endswith("k"):
        multiplier = 1000
        text = text[:-1]
    try:
        return int(float(text) * multiplier)
    except ValueError:
        return None


def _browser_error_message(exc: Exception) -> str:
    message = str(exc)
    if "Executable doesn't exist" in message or "playwright install" in message:
        return PLAYWRIGHT_INSTALL_HINT
    return message
