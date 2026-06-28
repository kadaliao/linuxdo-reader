from __future__ import annotations

import sqlite3
from pathlib import Path

from .models import Post, Topic


class Store:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def upsert_topics(self, topics: list[Topic]) -> None:
        with self._conn:
            self._conn.executemany(
                """
                INSERT INTO topics (
                    topic_id, title, url, author, category, excerpt, published_at,
                    source, reply_count, participant_count, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(topic_id) DO UPDATE SET
                    title=excluded.title,
                    url=excluded.url,
                    author=excluded.author,
                    category=excluded.category,
                    excerpt=excluded.excerpt,
                    published_at=excluded.published_at,
                    source=excluded.source,
                    reply_count=excluded.reply_count,
                    participant_count=excluded.participant_count,
                    updated_at=CURRENT_TIMESTAMP
                """,
                [
                    (
                        topic.topic_id,
                        topic.title,
                        topic.url,
                        topic.author,
                        topic.category,
                        topic.excerpt,
                        topic.published_at,
                        topic.source,
                        topic.reply_count,
                        topic.participant_count,
                    )
                    for topic in topics
                ],
            )

    def upsert_posts(self, posts: list[Post]) -> None:
        with self._conn:
            self._conn.executemany(
                """
                INSERT INTO posts (
                    topic_id, post_id, post_number, author, text, cooked, url,
                    created_at, source, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(topic_id, post_id) DO UPDATE SET
                    post_number=excluded.post_number,
                    author=excluded.author,
                    text=excluded.text,
                    cooked=excluded.cooked,
                    url=excluded.url,
                    created_at=excluded.created_at,
                    source=excluded.source,
                    updated_at=CURRENT_TIMESTAMP
                """,
                [
                    (
                        post.topic_id,
                        post.post_id,
                        post.post_number,
                        post.author,
                        post.text,
                        post.cooked,
                        post.url,
                        post.created_at,
                        post.source,
                    )
                    for post in posts
                ],
            )

    def list_topics(self, limit: int = 20) -> list[Topic]:
        rows = self._conn.execute(
            """
            SELECT * FROM topics
            ORDER BY COALESCE(reply_count, 0) DESC, published_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [_topic_from_row(row) for row in rows]

    def get_topic(self, topic_id: int) -> Topic | None:
        row = self._conn.execute("SELECT * FROM topics WHERE topic_id = ?", (topic_id,)).fetchone()
        return _topic_from_row(row) if row else None

    def list_posts(self, topic_id: int, limit: int | None = None) -> list[Post]:
        sql = "SELECT * FROM posts WHERE topic_id = ? ORDER BY post_number ASC"
        params: tuple[int, ...] | tuple[int, int] = (topic_id,)
        if limit is not None:
            sql += " LIMIT ?"
            params = (topic_id, limit)
        rows = self._conn.execute(sql, params).fetchall()
        return [_post_from_row(row) for row in rows]

    def search_posts(self, query: str, limit: int = 20) -> list[Post]:
        pattern = f"%{query}%"
        rows = self._conn.execute(
            """
            SELECT * FROM posts
            WHERE text LIKE ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (pattern, limit),
        ).fetchall()
        return [_post_from_row(row) for row in rows]

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS topics (
                    topic_id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    author TEXT NOT NULL,
                    category TEXT NOT NULL,
                    excerpt TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    reply_count INTEGER,
                    participant_count INTEGER,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS posts (
                    topic_id INTEGER NOT NULL,
                    post_id TEXT NOT NULL,
                    post_number INTEGER NOT NULL,
                    author TEXT NOT NULL,
                    text TEXT NOT NULL,
                    cooked TEXT NOT NULL,
                    url TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (topic_id, post_id)
                )
                """
            )


def _topic_from_row(row: sqlite3.Row) -> Topic:
    return Topic(
        topic_id=int(row["topic_id"]),
        title=str(row["title"]),
        url=str(row["url"]),
        author=str(row["author"]),
        category=str(row["category"]),
        excerpt=str(row["excerpt"]),
        published_at=str(row["published_at"]),
        source=str(row["source"]),
        reply_count=row["reply_count"],
        participant_count=row["participant_count"],
    )


def _post_from_row(row: sqlite3.Row) -> Post:
    return Post(
        topic_id=int(row["topic_id"]),
        post_id=str(row["post_id"]),
        post_number=int(row["post_number"]),
        author=str(row["author"]),
        text=str(row["text"]),
        cooked=str(row["cooked"]),
        url=str(row["url"]),
        created_at=str(row["created_at"]),
        source=str(row["source"]),
    )
