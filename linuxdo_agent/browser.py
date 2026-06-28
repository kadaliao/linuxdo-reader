from __future__ import annotations

from .feeds import canonical_topic_url, topic_id_from_url


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


def topic_id_from_any(value: str) -> int:
    if value.isdigit():
        return int(value)
    topic_id = topic_id_from_url(value)
    if topic_id is None:
        raise ValueError(f"Cannot extract linux.do topic id from {value!r}")
    return topic_id
