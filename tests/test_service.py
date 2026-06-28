import httpx
import respx

from linuxdo_agent.service import LinuxDoService
from linuxdo_agent.storage import Store

from .fixtures import LATEST_RSS, POSTS_JSON, TOPIC_JSON, TOPIC_RSS


@respx.mock
def test_service_refreshes_hot_topics_and_hydrates_topic_with_json(tmp_path) -> None:
    respx.get("https://linux.do/top.rss").mock(return_value=httpx.Response(200, text=LATEST_RSS))
    respx.get("https://linux.do/t/-/2489984.json").mock(
        return_value=httpx.Response(200, json=TOPIC_JSON)
    )
    respx.get("https://linux.do/t/2489984/posts.json").mock(
        return_value=httpx.Response(200, json=POSTS_JSON)
    )

    store = Store(tmp_path / "linuxdo.sqlite")
    service = LinuxDoService(store=store)

    topics = service.refresh_top(period="daily", limit=2)
    posts = service.hydrate_topic(2489984, prefer="json")

    assert [topic.topic_id for topic in topics] == [2491173, 2489984]
    assert len(posts) == 3
    assert len(store.list_posts(2489984)) == 3


@respx.mock
def test_service_hydrate_topic_falls_back_to_rss(tmp_path) -> None:
    respx.get("https://linux.do/t/-/2489984.json").mock(return_value=httpx.Response(403))
    respx.get("https://linux.do/t/topic/2489984.rss").mock(
        return_value=httpx.Response(200, text=TOPIC_RSS)
    )

    store = Store(tmp_path / "linuxdo.sqlite")
    service = LinuxDoService(store=store)

    posts = service.hydrate_topic(2489984, prefer="json")

    assert [post.source for post in posts] == ["rss", "rss"]
    assert len(store.list_posts(2489984)) == 2


def test_service_renders_digest_from_cache(tmp_path) -> None:
    store = Store(tmp_path / "linuxdo.sqlite")
    service = LinuxDoService(store=store)
    store.upsert_topics(service.parse_topics_for_tests(LATEST_RSS))

    digest = service.render_daily_from_cache(limit=2)

    assert "# Linux.do 热点摘要" in digest
    assert "mac mini m4" in digest
