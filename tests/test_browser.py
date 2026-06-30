import pytest

from linuxdo_reader.browser import build_topic_url, fetch_topic_with_browser


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
