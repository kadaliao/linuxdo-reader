from __future__ import annotations

from .models import Post, Topic


def render_topic_digest(topic: Topic, posts: list[Post], limit: int | None = None) -> str:
    shown_posts = posts if limit is None else posts[:limit]
    hidden_count = len(posts) - len(shown_posts)
    lines = [
        f"## {topic.title}",
        "",
        f"- 链接：{topic.url}",
        f"- 分类：{topic.category or '未知'}",
        f"- 作者：{topic.author or '未知'}",
        f"- 热度：{topic.reply_count or 0} 楼（含主贴），{topic.participant_count or 0} 位参与者",
        f"- 讨论区样本：{len(posts)} 条",
        "",
        "### 首帖",
        _clip(topic.excerpt, 500),
        "",
        "### 讨论区摘录",
    ]
    for post in shown_posts:
        lines.append(f"- #{post.post_number} {post.author}: {_clip(post.text, 180)}")
    if hidden_count > 0:
        lines.append(f"- 还有 {hidden_count} 条已缓存楼层未展示。")
    return "\n".join(lines).strip() + "\n"


def render_daily_digest(
    topics: list[Topic],
    posts_by_topic: dict[int, list[Post]],
    comments_per_topic: int = 50,
) -> str:
    lines = ["# Linux.do 热点摘要", ""]
    for index, topic in enumerate(topics, start=1):
        posts = posts_by_topic.get(topic.topic_id, [])
        shown_posts = posts[:comments_per_topic]
        hidden_count = max(len(posts) - len(shown_posts), 0)
        lines.extend(
            [
                f"## {index}. {topic.title}",
                "",
                f"- 链接：{topic.url}",
                f"- 分类：{topic.category or '未知'}",
                f"- 热度：{topic.reply_count or 0} 楼（含主贴），{topic.participant_count or 0} 位参与者",
                f"- 已缓存楼层：{len(posts)} 条，展示 {len(shown_posts)} 条",
                f"- 首帖：{_clip(topic.excerpt, 240)}",
            ]
        )
        if shown_posts:
            lines.append("- 讨论区：")
            for post in shown_posts:
                lines.append(f"  - #{post.post_number} {post.author}: {_clip(post.text, 120)}")
            if hidden_count:
                lines.append(f"  - 还有 {hidden_count} 条已缓存楼层未展示。")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _clip(text: str, max_chars: int) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 1].rstrip() + "..."
