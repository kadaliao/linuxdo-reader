from linuxdo_reader.models import FetchResult, Post, Topic
from linuxdo_reader.storage import Store


def test_store_upserts_topics_and_posts_without_duplicates(tmp_path) -> None:
    store = Store(tmp_path / "linuxdo.sqlite")
    topic = Topic(
        topic_id=2489984,
        title="囤囤鼠的末日",
        url="https://linux.do/t/topic/2489984",
        author="qq124415",
        category="搞七捻三",
        excerpt="感谢公益站",
        published_at="Sun, 28 Jun 2026 09:45:15 +0000",
        source="top",
        reply_count=102,
        participant_count=95,
    )
    post = Post(
        topic_id=2489984,
        post_id="2489984-105",
        post_number=105,
        author="欣欣",
        text="哈哈哈",
        cooked="<p>哈哈哈</p>",
        url="https://linux.do/t/topic/2489984/105",
        created_at="Sun, 28 Jun 2026 15:29:18 +0000",
        source="rss",
    )

    store.upsert_topics([topic])
    store.upsert_topics([topic])
    store.upsert_posts([post])
    store.upsert_posts([post])

    assert len(store.list_topics(limit=10)) == 1
    assert len(store.list_posts(2489984)) == 1
    assert store.list_topics(limit=10)[0].topic_id == 2489984


def _make_post(post_id: str, post_number: int, source: str) -> Post:
    return Post(
        topic_id=2489984,
        post_id=post_id,
        post_number=post_number,
        author="a",
        text=f"楼层 {post_number} via {source}",
        cooked="",
        url=f"https://linux.do/t/topic/2489984/{post_number}",
        created_at="",
        source=source,
    )


def test_store_replaces_rss_floor_when_json_fetches_same_floor(tmp_path) -> None:
    store = Store(tmp_path / "linuxdo.sqlite")

    store.upsert_posts([_make_post("2489984-105", 105, "rss")])
    store.upsert_posts([_make_post("19684601", 105, "json")])

    posts = store.list_posts(2489984)
    assert len(posts) == 1
    assert posts[0].post_id == "19684601"
    assert posts[0].source == "json"


def _make_topic(topic_id: int, reply_count: int) -> Topic:
    return Topic(
        topic_id=topic_id,
        title=f"话题 {topic_id}",
        url=f"https://linux.do/t/topic/{topic_id}",
        author="a",
        category="c",
        excerpt="e",
        published_at="2026-06-28T09:45:15+00:00",
        source="top:daily",
        reply_count=reply_count,
        participant_count=1,
    )


def test_list_topics_uses_only_most_recent_successful_refresh_batch(tmp_path) -> None:
    store = Store(tmp_path / "linuxdo.sqlite")

    old_batch = store.start_refresh_batch("top", "daily")
    store.upsert_topics([_make_topic(1111, reply_count=500)], batch_id=old_batch)
    store.finish_refresh_batch(old_batch, complete=True)

    failed_batch = store.start_refresh_batch("top", "daily")
    store.upsert_topics([_make_topic(4444, reply_count=900)], batch_id=failed_batch)
    store.finish_refresh_batch(failed_batch, complete=False, error="blocked")

    new_batch = store.start_refresh_batch("top", "daily")
    store.upsert_topics(
        [_make_topic(2222, reply_count=3), _make_topic(3333, reply_count=80)],
        batch_id=new_batch,
    )
    store.finish_refresh_batch(new_batch, complete=True)

    topics = store.list_topics(limit=3)
    assert [topic.topic_id for topic in topics] == [2222, 3333]


def test_failed_refresh_does_not_expose_legacy_stale_topics(tmp_path) -> None:
    store = Store(tmp_path / "linuxdo.sqlite")
    store.upsert_topics([_make_topic(1111, reply_count=500)])
    failed_batch = store.start_refresh_batch("top", "daily")
    store.finish_refresh_batch(failed_batch, complete=False, error="blocked")

    assert store.list_topics(limit=10) == []


def test_store_persists_fetch_completeness(tmp_path) -> None:
    store = Store(tmp_path / "linuxdo.sqlite")
    post = _make_post("19684601", 1, "json")
    result = FetchResult(
        [post],
        complete=False,
        source="json",
        error="pagination failed",
        expected_count=3,
    )

    stale_post = _make_post("19684602", 2, "json")
    store.upsert_posts([stale_post])
    store.upsert_posts(result.posts)
    store.record_fetch_result(2489984, result)

    cached = store.get_fetch_result(2489984)
    assert cached is not None
    assert cached.posts == [post, stale_post]
    assert cached.fetched_count == 1
    assert cached.complete is False
    assert cached.expected_count == 3
    assert cached.error == "pagination failed"
