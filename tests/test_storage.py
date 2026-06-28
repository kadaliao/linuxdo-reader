from linuxdo_reader.models import Post, Topic
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
