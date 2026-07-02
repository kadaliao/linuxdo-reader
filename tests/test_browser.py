import pytest

from linuxdo_reader.browser import (
    build_topic_url,
    export_context_cookies,
    fetch_topic_with_browser,
    topics_from_browser_rows,
)


def test_build_topic_url_accepts_id_or_url() -> None:
    assert build_topic_url("2489984") == "https://linux.do/t/topic/2489984"
    assert build_topic_url("https://linux.do/t/topic/2489984") == "https://linux.do/t/topic/2489984"


def test_browser_mode_install_hint_mentions_uv_tool_extra(monkeypatch) -> None:
    def fake_import(name, *args, **kwargs):
        if name == "playwright.sync_api":
            raise ImportError("no playwright")
        return original_import(name, *args, **kwargs)

    original_import = __import__
    monkeypatch.setattr("builtins.__import__", fake_import)

    with pytest.raises(RuntimeError) as exc_info:
        fetch_topic_with_browser("2489984")

    assert "uv tool install git+https://github.com/kadaliao/linuxdo-reader --with playwright --force" in str(exc_info.value)


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
