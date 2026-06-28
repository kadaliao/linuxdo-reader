from __future__ import annotations

from .models import Post, Topic


def render_topic_digest(topic: Topic, posts: list[Post]) -> str:
    lines = [
        f"## {topic.title}",
        "",
        f"- 链接：{topic.url}",
        f"- 分类：{topic.category or '未知'}",
        f"- 作者：{topic.author or '未知'}",
        f"- 热度：{topic.reply_count or 0} 个帖子，{topic.participant_count or 0} 位参与者",
        f"- 讨论区样本：{len(posts)} 条",
        "",
        "### 首帖",
        _clip(topic.excerpt, 500),
        "",
        "### 讨论区摘录",
    ]
    for post in posts[:12]:
        lines.append(f"- #{post.post_number} {post.author}: {_clip(post.text, 180)}")
    if len(posts) > 12:
        lines.append(f"- 还有 {len(posts) - 12} 条已缓存回复未展示。")
    return "\n".join(lines).strip() + "\n"


def render_daily_digest(topics: list[Topic], posts_by_topic: dict[int, list[Post]]) -> str:
    lines = ["# Linux.do 热点摘要", ""]
    for index, topic in enumerate(topics, start=1):
        posts = posts_by_topic.get(topic.topic_id, [])
        lines.extend(
            [
                f"## {index}. {topic.title}",
                "",
                f"- 链接：{topic.url}",
                f"- 分类：{topic.category or '未知'}",
                f"- 热度：{topic.reply_count or 0} 个帖子，{topic.participant_count or 0} 位参与者",
                f"- 已缓存评论：{len(posts)} 条",
                f"- 首帖：{_clip(topic.excerpt, 240)}",
            ]
        )
        if posts:
            lines.append("- 讨论区：")
            for post in posts[:5]:
                lines.append(f"  - #{post.post_number} {post.author}: {_clip(post.text, 120)}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _clip(text: str, max_chars: int) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 1].rstrip() + "..."
