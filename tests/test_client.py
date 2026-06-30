import httpx
import respx

from linuxdo_reader.client import LinuxDoClient

from .fixtures import LATEST_RSS, POSTS_JSON, TOPIC_JSON


@respx.mock
def test_fetch_top_falls_back_to_pretty_period_rss() -> None:
    respx.get("https://linux.do/top.rss").mock(side_effect=httpx.ConnectError("TLS EOF"))
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
    respx.get("https://linux.do/top/daily.rss").mock(side_effect=httpx.ConnectError("TLS EOF"))

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
    posts = client.fetch_topic_json(2489984, chunk_size=2)

    assert [post.post_number for post in posts] == [1, 2, 3]
    assert posts[0].source == "json"
    assert "偶尔才用" in posts[2].text
