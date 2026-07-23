import pytest

from linuxdo_reader.browser import (
    _fetch_topic_posts_from_page,
    build_topic_url,
    export_context_cookies,
    fetch_topic_with_browser,
    launch_proxy_options,
    merge_rendered_rows,
    navigate_for_cookie_refresh,
    rendered_rows_to_posts,
    topics_from_browser_rows,
)
from linuxdo_reader.models import Post


def test_build_topic_url_accepts_id_or_url() -> None:
    assert build_topic_url("2489984") == "https://linux.do/t/topic/2489984"
    assert (
        build_topic_url("https://linux.do/t/topic/2489984")
        == "https://linux.do/t/topic/2489984"
    )


def test_browser_mode_install_hint_mentions_uv_tool_extra(monkeypatch) -> None:
    def fake_import(name, *args, **kwargs):
        if name == "playwright.sync_api":
            raise ImportError("no playwright")
        return original_import(name, *args, **kwargs)

    original_import = __import__
    monkeypatch.setattr("builtins.__import__", fake_import)

    with pytest.raises(RuntimeError) as exc_info:
        fetch_topic_with_browser("2489984")

    assert (
        "uv tool install git+https://github.com/kadaliao/linuxdo-reader --with playwright --force"
        in str(exc_info.value)
    )


def test_topics_from_browser_rows_parses_rendered_top_rows() -> None:
    topics = topics_from_browser_rows(
        [
            {
                "title": "宝可梦机场之七月免费兑换码猜猜我是谁",
                "url": "https://linux.do/t/topic/2504318",
                "category": "福利羊毛",
                "excerpt": "树洞 机场 免费节点",
                "reply_count": "307",
            },
            {
                "title": "AI 中转站大起底",
                "url": "https://linux.do/t/topic/2504277",
                "reply_count": "2.0k",
            },
        ],
        source="top:daily:browser",
    )

    assert [topic.topic_id for topic in topics] == [2504318, 2504277]
    assert topics[0].category == "福利羊毛"
    assert topics[0].reply_count == 307
    assert topics[1].reply_count == 2000


def test_export_context_cookies_writes_linuxdo_cookies(tmp_path) -> None:
    class FakeContext:
        def cookies(self, urls):
            assert urls == ["https://linux.do"]
            return [
                {
                    "name": "_forum_session",
                    "value": "secret",
                    "domain": ".linux.do",
                    "path": "/",
                    "expires": 2147483647,
                    "secure": True,
                    "httpOnly": True,
                }
            ]

    cookies_file = export_context_cookies(FakeContext(), tmp_path / "cookies.txt")

    assert "_forum_session" in cookies_file.read_text(encoding="utf-8")


def test_navigate_for_cookie_refresh_falls_back_after_connection_closed() -> None:
    class FakePage:
        def __init__(self) -> None:
            self.urls = []

        def goto(self, url, wait_until):
            assert wait_until == "domcontentloaded"
            self.urls.append(url)
            if url.endswith("/top?period=daily"):
                raise RuntimeError("Page.goto: net::ERR_CONNECTION_CLOSED")

        def wait_for_timeout(self, timeout):
            assert timeout == 2000

    page = FakePage()

    navigate_for_cookie_refresh(page)

    assert page.urls == ["https://linux.do/top?period=daily", "https://linux.do/"]


def test_navigate_for_cookie_refresh_reports_all_failed_urls() -> None:
    class FakePage:
        def goto(self, url, wait_until):
            raise RuntimeError(f"Page.goto failed for {url}")

        def wait_for_timeout(self, timeout):
            raise AssertionError("should not wait after failed navigation")

    try:
        navigate_for_cookie_refresh(FakePage())
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected RuntimeError")

    assert "https://linux.do/top?period=daily" in message
    assert "https://linux.do/" in message
    assert "https://linux.do/latest" in message


def test_merge_rendered_rows_accumulates_across_scroll_rounds() -> None:
    collected: dict = {}

    merge_rendered_rows(
        collected,
        [
            {"postId": "1", "postNumber": "1", "author": "a", "text": "首帖"},
            {"postId": "2", "postNumber": "2", "author": "b", "text": "短"},
        ],
    )
    merge_rendered_rows(
        collected,
        [
            {
                "postId": "2",
                "postNumber": "2",
                "author": "b",
                "text": "更长的完整楼层文本",
            },
            {
                "postId": "3",
                "postNumber": "3",
                "author": "c",
                "text": "后来滚动加载的楼层",
            },
            "not-a-dict",
            {"postId": "4", "postNumber": "4", "author": "d", "text": ""},
        ],
    )

    assert set(collected) == {"id:1", "id:2", "id:3"}
    assert collected["id:2"]["text"] == "更长的完整楼层文本"


def test_rendered_rows_to_posts_orders_floors_and_avoids_number_collisions() -> None:
    posts = rendered_rows_to_posts(
        [
            {"postId": "20", "postNumber": "2", "author": "b", "text": "二楼"},
            {"postId": "10", "postNumber": "1", "author": "a", "text": "首帖"},
            {"postId": "", "postNumber": "", "author": "c", "text": "无楼号的可见样本"},
        ],
        topic_id=2489984,
    )

    assert [post.post_number for post in posts] == [1, 2, 3]
    assert posts[0].text == "首帖"
    assert posts[2].post_id == "rendered-3"
    assert all(post.source == "browser:page" for post in posts)


def test_browser_empty_post_stream_falls_back_to_rendered_page(monkeypatch) -> None:
    class FakePage:
        def evaluate(self, _script, _path=None):
            return {}

    rendered_post = Post(
        2489984,
        "rendered-1",
        1,
        "author",
        "visible sample",
        "visible sample",
        "https://linux.do/t/topic/2489984/1",
        "",
        "browser:page",
    )
    monkeypatch.setattr(
        "linuxdo_reader.browser._page_posts_from_rendered_topic",
        lambda *_args, **_kwargs: [rendered_post],
    )

    result = _fetch_topic_posts_from_page(FakePage(), 2489984)

    assert result.posts == [rendered_post]
    assert result.complete is False
    assert result.source == "browser:page"
    assert "post_stream" in (result.error or "")


def test_browser_json_pagination_failure_keeps_fetched_posts() -> None:
    class FakePage:
        def evaluate(self, _script, path=None):
            if path == "/t/-/2489984.json?print=true":
                return {
                    "post_stream": {
                        "stream": [10, 20, 30],
                        "posts": [
                            {
                                "id": 10,
                                "post_number": 1,
                                "username": "main",
                                "cooked": "<p>首帖</p>",
                            }
                        ],
                    }
                }
            if "post_ids[]=20" in path:
                return {
                    "post_stream": {
                        "posts": [
                            {
                                "id": 20,
                                "post_number": 2,
                                "username": "alice",
                                "cooked": "<p>已抓回复</p>",
                            }
                        ]
                    }
                }
            raise RuntimeError("429 rate limited")

    result = _fetch_topic_posts_from_page(FakePage(), 2489984, chunk_size=1)

    assert [post.post_number for post in result.posts] == [1, 2]
    assert result.complete is False
    assert result.expected_count == 3
    assert "429 rate limited" in (result.error or "")
    assert all(post.source == "browser" for post in result.posts)


def test_launch_proxy_options_builds_playwright_proxy() -> None:
    assert launch_proxy_options(None) == {}
    assert launch_proxy_options("http://127.0.0.1:7890") == {
        "proxy": {"server": "http://127.0.0.1:7890"}
    }
