import httpx
import pytest
import respx

from linuxdo_reader.client import FeedTooLargeError, LinuxDoClient

from .fixtures import LATEST_RSS, POSTS_JSON, TOPIC_JSON


@respx.mock
def test_fetch_top_falls_back_to_pretty_period_rss() -> None:
    respx.get("https://linux.do/top.rss").mock(
        side_effect=httpx.ConnectError("TLS EOF")
    )
    respx.get("https://linux.do/top/daily.rss").mock(
        return_value=httpx.Response(200, text=LATEST_RSS)
    )

    client = LinuxDoClient()
    topics = client.fetch_top("daily")

    assert [topic.topic_id for topic in topics] == [2491173, 2489984]


@respx.mock
def test_fetch_top_retries_transient_errors_before_fallback() -> None:
    route = respx.get("https://linux.do/top.rss").mock(
        side_effect=[
            httpx.ConnectError("TLS EOF"),
            httpx.Response(200, text=LATEST_RSS),
        ]
    )

    client = LinuxDoClient()
    topics = client.fetch_top("daily")

    assert route.call_count == 2
    assert [topic.topic_id for topic in topics] == [2491173, 2489984]


@respx.mock
def test_fetch_top_reports_all_failed_fallbacks() -> None:
    respx.get("https://linux.do/top.rss").mock(return_value=httpx.Response(403))
    respx.get("https://linux.do/top/daily.rss").mock(
        side_effect=httpx.ConnectError("TLS EOF")
    )

    client = LinuxDoClient()

    try:
        client.fetch_top("daily")
    except httpx.HTTPError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected HTTPError")

    assert "/top.rss?period=daily" in message
    assert "/top/daily.rss" in message


@respx.mock
def test_fetch_topic_full_uses_print_json_then_post_ids() -> None:
    respx.get("https://linux.do/t/-/2489984.json").mock(
        return_value=httpx.Response(200, json=TOPIC_JSON)
    )
    respx.get("https://linux.do/t/2489984/posts.json").mock(
        return_value=httpx.Response(200, json=POSTS_JSON)
    )

    client = LinuxDoClient()
    result = client.fetch_topic_json(2489984, chunk_size=2)

    assert [post.post_number for post in result.posts] == [1, 2, 3]
    assert result.complete is True
    assert result.expected_count == 3
    assert result.posts[0].source == "json"
    assert "偶尔才用" in result.posts[2].text


@respx.mock
def test_fetch_topic_json_falls_back_from_print_to_plain_json() -> None:
    def topic_json_handler(request):
        if "print" in str(request.url):
            return httpx.Response(429, headers={"Retry-After": "1"})
        return httpx.Response(200, json=TOPIC_JSON)

    respx.get("https://linux.do/t/-/2489984.json").mock(side_effect=topic_json_handler)
    respx.get("https://linux.do/t/2489984/posts.json").mock(
        return_value=httpx.Response(200, json=POSTS_JSON)
    )

    client = LinuxDoClient()
    sleeps: list[float] = []
    client._sleep = sleeps.append

    result = client.fetch_topic_json(2489984)

    assert [post.post_number for post in result.posts] == [1, 2, 3]
    assert result.complete is True
    # 429 on print mode is retried with Retry-After before switching to plain JSON.
    assert sleeps == [1.0, 1.0]


@pytest.mark.parametrize("payload", [{}, {"post_stream": {}}])
@respx.mock
def test_fetch_topic_json_rejects_empty_post_stream(payload) -> None:
    respx.get("https://linux.do/t/-/2489984.json").mock(
        return_value=httpx.Response(200, json=payload)
    )
    client = LinuxDoClient()

    with pytest.raises(ValueError, match="post.stream|post stream"):
        client.fetch_topic_json(2489984)


@respx.mock
def test_fetch_topic_json_keeps_partial_posts_when_pagination_fails() -> None:
    respx.get("https://linux.do/t/-/2489984.json").mock(
        return_value=httpx.Response(200, json=TOPIC_JSON)
    )
    respx.get("https://linux.do/t/2489984/posts.json").mock(
        return_value=httpx.Response(500)
    )

    client = LinuxDoClient()
    result = client.fetch_topic_json(2489984)

    assert [post.post_number for post in result.posts] == [1]
    assert result.complete is False
    assert result.expected_count == 3
    assert "pagination stopped" in (result.error or "")
    assert result.posts[0].source == "json"


@respx.mock
def test_fetch_top_treats_cloudflare_html_as_feed_failure() -> None:
    respx.get("https://linux.do/top.rss").mock(
        return_value=httpx.Response(
            200, text="<html><body>Just a moment...</body></html>"
        )
    )
    respx.get("https://linux.do/top/daily.rss").mock(
        return_value=httpx.Response(200, text=LATEST_RSS)
    )

    client = LinuxDoClient()
    topics = client.fetch_top("daily")

    assert [topic.topic_id for topic in topics] == [2491173, 2489984]


@respx.mock
def test_feed_response_size_is_limited() -> None:
    respx.get("https://linux.do/latest.rss").mock(
        return_value=httpx.Response(200, content=b"x" * 11)
    )
    client = LinuxDoClient()

    with pytest.raises(FeedTooLargeError):
        client._fetch_feed_text("/latest.rss", max_bytes=10)


@respx.mock
def test_client_sends_configured_cookies_file(tmp_path) -> None:
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(
        "# Netscape HTTP Cookie File\n"
        ".linux.do\tTRUE\t/\tTRUE\t2147483647\t_cf_bm\tabc\n",
        encoding="utf-8",
    )
    route = respx.get("https://linux.do/top.rss").mock(
        return_value=httpx.Response(200, text=LATEST_RSS)
    )

    client = LinuxDoClient(cookies_file=cookies_file)
    client.fetch_top("daily")

    assert route.calls.last.request.headers["cookie"] == "_cf_bm=abc"
