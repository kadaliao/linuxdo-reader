from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Topic:
    topic_id: int
    title: str
    url: str
    author: str
    category: str
    excerpt: str
    published_at: str
    source: str
    reply_count: int | None = None
    participant_count: int | None = None


@dataclass(frozen=True)
class Post:
    topic_id: int
    post_id: str
    post_number: int
    author: str
    text: str
    cooked: str
    url: str
    created_at: str
    source: str


@dataclass(frozen=True)
class FetchResult:
    posts: list[Post]
    complete: bool
    source: str
    error: str | None = None
    expected_count: int | None = None
    observed_count: int | None = None

    @property
    def fetched_count(self) -> int:
        return (
            self.observed_count if self.observed_count is not None else len(self.posts)
        )
