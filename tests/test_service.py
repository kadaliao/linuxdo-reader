import httpx
import respx

from linuxdo_reader.service import LinuxDoService
from linuxdo_reader.storage import Store

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


def test_service_hydrate_topic_can_use_browser_fetcher(tmp_path) -> None:
    store = Store(tmp_path / "linuxdo.sqlite")
    service = LinuxDoService(
        store=store,
        browser_fetcher=lambda topic_id: [
            service.make_post_for_tests(topic_id, 1, "首帖"),
            service.make_post_for_tests(topic_id, 2, "第一条回复"),
        ],
    )

    posts = service.hydrate_topic(2489666, prefer="browser")

    assert [post.post_number for post in posts] == [1, 2]
    assert len(store.list_posts(2489666)) == 2


@respx.mock
def test_service_crawl_top_hydrates_each_refreshed_topic(tmp_path) -> None:
    respx.get("https://linux.do/top.rss").mock(return_value=httpx.Response(200, text=LATEST_RSS))
    store = Store(tmp_path / "linuxdo.sqlite")
    service = LinuxDoService(
        store=store,
        browser_fetcher=lambda topic_id: [service.make_post_for_tests(topic_id, 1, "楼层")],
    )

    report = service.crawl_top(period="daily", limit=2, prefer="browser", delay=0)

    assert report.counts == {2491173: 1, 2489984: 1}
    assert report.errors == {}
    assert len(store.list_posts(2491173)) == 1
    assert len(store.list_posts(2489984)) == 1


@respx.mock
def test_service_crawl_top_uses_browser_topic_list_when_feeds_fail(tmp_path) -> None:
    respx.get("https://linux.do/top.rss").mock(return_value=httpx.Response(403))
    respx.get("https://linux.do/top/daily.rss").mock(
        side_effect=httpx.ConnectError("TLS EOF")
    )
    store = Store(tmp_path / "linuxdo.sqlite")
    service = LinuxDoService(
        store=store,
        browser_top_fetcher=lambda period, limit: service.parse_topics_for_tests(
            LATEST_RSS
        )[:limit],
        browser_fetcher=lambda topic_id: [service.make_post_for_tests(topic_id, 1, "楼层")],
    )

    report = service.crawl_top(period="daily", limit=2, prefer="browser", delay=0)

    assert report.counts == {2491173: 1, 2489984: 1}
    assert {topic.topic_id for topic in store.list_topics(limit=2)} == {2491173, 2489984}


@respx.mock
def test_service_crawl_top_continues_past_failed_topics(tmp_path) -> None:
    respx.get("https://linux.do/top.rss").mock(return_value=httpx.Response(200, text=LATEST_RSS))

    def browser_fetcher(topic_id: int):
        if topic_id == 2491173:
            raise RuntimeError("Cloudflare blocked this one")
        return [service.make_post_for_tests(topic_id, 1, "楼层")]

    store = Store(tmp_path / "linuxdo.sqlite")
    service = LinuxDoService(store=store, browser_fetcher=browser_fetcher)

    report = service.crawl_top(period="daily", limit=2, prefer="browser", delay=0)

    assert report.counts == {2489984: 1}
    assert list(report.errors) == [2491173]
    assert "Cloudflare" in report.errors[2491173]
    assert len(store.list_posts(2489984)) == 1


@respx.mock
def test_service_crawl_latest_hydrates_each_topic(tmp_path) -> None:
    respx.get("https://linux.do/latest.rss").mock(
        return_value=httpx.Response(200, text=LATEST_RSS)
    )
    store = Store(tmp_path / "linuxdo.sqlite")
    service = LinuxDoService(
        store=store,
        browser_fetcher=lambda topic_id: [service.make_post_for_tests(topic_id, 1, "楼层")],
    )

    report = service.crawl_latest(limit=2, prefer="browser", delay=0)

    assert report.counts == {2491173: 1, 2489984: 1}
    assert report.errors == {}


def test_service_renders_digest_from_cache(tmp_path) -> None:
    store = Store(tmp_path / "linuxdo.sqlite")
    service = LinuxDoService(store=store)
    store.upsert_topics(service.parse_topics_for_tests(LATEST_RSS))

    digest = service.render_daily_from_cache(limit=2)

    assert "# Linux.do 热点摘要" in digest
    assert "mac mini m4" in digest
