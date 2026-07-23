from __future__ import annotations

import re
from email.utils import parsedate_to_datetime
from typing import Any

from bs4 import BeautifulSoup
from defusedxml.ElementTree import fromstring

from .models import Post, Topic

DC_NS = "{http://purl.org/dc/elements/1.1/}"


def parse_topic_list_feed(xml_text: str, source: str) -> list[Topic]:
    root = fromstring(xml_text)
    topics: list[Topic] = []
    for item in root.findall("./channel/item"):
        link = _text(item, "link")
        topic_id = topic_id_from_url(link)
        if topic_id is None:
            continue
        description = _text(item, "description")
        reply_count, participant_count = _extract_counts(description)
        topics.append(
            Topic(
                topic_id=topic_id,
                title=_text(item, "title"),
                url=canonical_topic_url(topic_id),
                author=_text(item, f"{DC_NS}creator"),
                category=_text(item, "category"),
                excerpt=html_to_text(description),
                published_at=_normalize_date(_text(item, "pubDate")),
                source=source,
                reply_count=reply_count,
                participant_count=participant_count,
            )
        )
    return topics


def parse_topic_feed(xml_text: str, topic_id: int) -> list[Post]:
    root = fromstring(xml_text)
    posts: list[Post] = []
    for item in root.findall("./channel/item"):
        link = _text(item, "link")
        post_number = post_number_from_url(link)
        if post_number is None:
            continue
        posts.append(
            Post(
                topic_id=topic_id,
                post_id=f"{topic_id}-{post_number}",
                post_number=post_number,
                author=_text(item, f"{DC_NS}creator"),
                text=html_to_text(_text(item, "description")),
                cooked=_text(item, "description"),
                url=link,
                created_at=_normalize_date(_text(item, "pubDate")),
                source="rss",
            )
        )
    return sorted(posts, key=lambda post: post.post_number)


def topic_id_from_url(url: str) -> int | None:
    match = re.search(r"/t/(?:[^/]+/)?(\d+)(?:/|$)", url)
    return int(match.group(1)) if match else None


def post_number_from_url(url: str) -> int | None:
    match = re.search(r"/t/(?:[^/]+/)?\d+/(\d+)(?:\D|$)", url)
    return int(match.group(1)) if match else None


def canonical_topic_url(topic_id: int) -> str:
    return f"https://linux.do/t/topic/{topic_id}"


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    for link in soup.find_all("a"):
        if link.get_text(strip=True) == "阅读完整话题":
            link.decompose()
    for small in soup.find_all("small"):
        if re.search(
            r"\d+\s*个帖子\s*-\s*\d+\s*位参与者", small.get_text(" ", strip=True)
        ):
            small.decompose()
    text = soup.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_counts(html: str) -> tuple[int | None, int | None]:
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    match = re.search(r"(\d+)\s*个帖子\s*-\s*(\d+)\s*位参与者", text)
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def _text(item: Any, tag: str) -> str:
    found = item.find(tag)
    if found is None or found.text is None:
        return ""
    return found.text.strip()


def _normalize_date(value: str) -> str:
    if not value:
        return ""
    try:
        return parsedate_to_datetime(value).isoformat()
    except (TypeError, ValueError):
        return value
