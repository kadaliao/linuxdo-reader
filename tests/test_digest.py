from linuxdo_reader.digest import render_topic_digest
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
