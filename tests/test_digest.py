from linuxdo_reader.digest import render_daily_digest, render_topic_digest
from linuxdo_reader.models import Post, Topic


def test_render_topic_digest_groups_discussion_signals() -> None:
    topic = Topic(
        topic_id=2489984,
        title="囤囤鼠的末日",
        url="https://linux.do/t/topic/2489984",
        author="qq124415",
        category="福利羊毛",
        excerpt="公益站会回收囤而不用的额度。",
        published_at="Sun, 28 Jun 2026 09:45:15 +0000",
        source="top",
        reply_count=102,
        participant_count=95,
    )
    posts = [
        Post(2489984, "1", 1, "a", "支持回收，不用就是浪费。", "", "", "", "json"),
        Post(2489984, "2", 2, "b", "反对一刀切，偶尔用的人也需要额度。", "", "", "", "json"),
        Post(2489984, "3", 3, "c", "可以按活跃度和最近使用时间来判断。", "", "", "", "json"),
    ]

    rendered = render_topic_digest(topic, posts)

    assert "囤囤鼠的末日" in rendered
    assert "讨论区样本：3 条" in rendered
    assert "支持回收" in rendered
    assert "反对一刀切" in rendered


def test_render_topic_digest_describes_hidden_cached_floors() -> None:
    topic = Topic(
        topic_id=2489984,
        title="囤囤鼠的末日",
        url="https://linux.do/t/topic/2489984",
        author="qq124415",
        category="福利羊毛",
        excerpt="公益站会回收囤而不用的额度。",
        published_at="Sun, 28 Jun 2026 09:45:15 +0000",
        source="top",
        reply_count=102,
        participant_count=95,
    )
    posts = [
        Post(2489984, str(number), number, f"user{number}", f"评论 {number}", "", "", "", "json")
        for number in range(1, 14)
    ]

    rendered = render_topic_digest(topic, posts, limit=12)

    assert "还有 1 条已缓存楼层未展示" in rendered


def test_render_topic_digest_shows_all_cached_floors_by_default() -> None:
    topic = Topic(
        topic_id=2489984,
        title="囤囤鼠的末日",
        url="https://linux.do/t/topic/2489984",
        author="qq124415",
        category="福利羊毛",
        excerpt="公益站会回收囤而不用的额度。",
        published_at="Sun, 28 Jun 2026 09:45:15 +0000",
        source="top",
        reply_count=102,
        participant_count=95,
    )
    posts = [
        Post(2489984, str(number), number, f"user{number}", f"评论 {number}", "", "", "", "json")
        for number in range(1, 41)
    ]

    rendered = render_topic_digest(topic, posts)

    assert "#40 user40: 评论 40" in rendered
    assert "未展示" not in rendered


def test_render_topic_digest_falls_back_to_cached_floor_count() -> None:
    topic = Topic(
        topic_id=2489984,
        title="囤囤鼠的末日",
        url="https://linux.do/t/topic/2489984",
        author="",
        category="",
        excerpt="",
        published_at="",
        source="manual",
    )
    posts = [
        Post(2489984, str(number), number, f"user{number}", f"评论 {number}", "", "", "", "json")
        for number in range(1, 6)
    ]

    rendered = render_topic_digest(topic, posts)

    assert "热度：5 楼（含主贴）" in rendered


def test_render_daily_digest_shows_configurable_cached_comments() -> None:
    topic = Topic(
        topic_id=2489984,
        title="囤囤鼠的末日",
        url="https://linux.do/t/topic/2489984",
        author="qq124415",
        category="福利羊毛",
        excerpt="公益站会回收囤而不用的额度。",
        published_at="Sun, 28 Jun 2026 09:45:15 +0000",
        source="top",
        reply_count=102,
        participant_count=95,
    )
    posts = [
        Post(2489984, str(number), number, f"user{number}", f"评论 {number}", "", "", "", "json")
        for number in range(1, 9)
    ]

    rendered = render_daily_digest([topic], {2489984: posts}, comments_per_topic=7)

    assert "热度：102 楼（含主贴），95 位参与者" in rendered
    assert "已缓存楼层：8 条，展示 7 条" in rendered
    assert "#7 user7: 评论 7" in rendered
    assert "#8 user8: 评论 8" not in rendered
    assert "还有 1 条已缓存楼层未展示" in rendered
