from __future__ import annotations

import sqlite3
from pathlib import Path

from .models import FetchResult, Post, Topic


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

    def start_refresh_batch(self, source: str, period: str | None = None) -> int:
        with self._conn:
            cursor = self._conn.execute(
                """
                INSERT INTO refresh_batches (source, period, started_at, complete)
                VALUES (?, ?, CURRENT_TIMESTAMP, 0)
                """,
                (source, period),
            )
        return int(cursor.lastrowid)

    def finish_refresh_batch(
        self,
        batch_id: int,
        complete: bool,
        error: str | None = None,
    ) -> None:
        with self._conn:
            self._conn.execute(
                """
                UPDATE refresh_batches
                SET completed_at = CURRENT_TIMESTAMP, complete = ?, error = ?
                WHERE batch_id = ?
                """,
                (int(complete), error, batch_id),
            )

    def upsert_topics(self, topics: list[Topic], batch_id: int | None = None) -> None:
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
            if batch_id is not None:
                self._conn.executemany(
                    """
                    INSERT INTO refresh_batch_topics (batch_id, topic_id, position)
                    VALUES (?, ?, ?)
                    ON CONFLICT(batch_id, topic_id) DO UPDATE SET position=excluded.position
                    """,
                    [
                        (batch_id, topic.topic_id, position)
                        for position, topic in enumerate(topics)
                    ],
                )

    def upsert_posts(self, posts: list[Post]) -> None:
        with self._conn:
            self._upsert_posts(posts)

    def replace_posts(self, topic_id: int, posts: list[Post]) -> None:
        if any(post.topic_id != topic_id for post in posts):
            raise ValueError("Replacement posts must all belong to the requested topic")
        with self._conn:
            self._conn.execute("DELETE FROM posts WHERE topic_id = ?", (topic_id,))
            self._upsert_posts(posts)

    def _upsert_posts(self, posts: list[Post]) -> None:
        # RSS uses synthetic ids while JSON/browser uses Discourse ids. Drop a
        # stale row for the same floor so mixed sources never create duplicates.
        self._conn.executemany(
            "DELETE FROM posts WHERE topic_id = ? AND post_number = ? AND post_id <> ?",
            [(post.topic_id, post.post_number, post.post_id) for post in posts],
        )
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

    def record_fetch_result(self, topic_id: int, result: FetchResult) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO topic_fetches (
                    topic_id, complete, source, error, expected_count,
                    fetched_count, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(topic_id) DO UPDATE SET
                    complete=excluded.complete,
                    source=excluded.source,
                    error=excluded.error,
                    expected_count=excluded.expected_count,
                    fetched_count=excluded.fetched_count,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    topic_id,
                    int(result.complete),
                    result.source,
                    result.error,
                    result.expected_count,
                    result.fetched_count,
                ),
            )

    def get_fetch_result(self, topic_id: int) -> FetchResult | None:
        row = self._conn.execute(
            "SELECT * FROM topic_fetches WHERE topic_id = ?", (topic_id,)
        ).fetchone()
        if row is None:
            return None
        return FetchResult(
            posts=self.list_posts(topic_id),
            complete=bool(row["complete"]),
            source=str(row["source"]),
            error=str(row["error"]) if row["error"] is not None else None,
            expected_count=row["expected_count"],
            observed_count=int(row["fetched_count"]),
        )

    def list_topics(self, limit: int = 20) -> list[Topic]:
        batch = self._conn.execute(
            """
            SELECT batch_id FROM refresh_batches
            WHERE complete = 1
            ORDER BY batch_id DESC
            LIMIT 1
            """
        ).fetchone()
        if batch is not None:
            rows = self._conn.execute(
                """
                SELECT topics.* FROM refresh_batch_topics
                JOIN topics USING (topic_id)
                WHERE batch_id = ?
                ORDER BY position ASC
                LIMIT ?
                """,
                (batch["batch_id"], limit),
            ).fetchall()
        elif self._conn.execute("SELECT 1 FROM refresh_batches LIMIT 1").fetchone():
            rows = []
        else:
            rows = self._conn.execute(
                """
                SELECT * FROM topics
                ORDER BY updated_at DESC, COALESCE(reply_count, 0) DESC, published_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [_topic_from_row(row) for row in rows]

    def get_topic(self, topic_id: int) -> Topic | None:
        row = self._conn.execute(
            "SELECT * FROM topics WHERE topic_id = ?", (topic_id,)
        ).fetchone()
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
                CREATE TABLE IF NOT EXISTS refresh_batches (
                    batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    period TEXT,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    complete INTEGER NOT NULL,
                    error TEXT
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS refresh_batch_topics (
                    batch_id INTEGER NOT NULL,
                    topic_id INTEGER NOT NULL,
                    position INTEGER NOT NULL,
                    PRIMARY KEY (batch_id, topic_id),
                    FOREIGN KEY (batch_id) REFERENCES refresh_batches(batch_id)
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS topic_fetches (
                    topic_id INTEGER PRIMARY KEY,
                    complete INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    error TEXT,
                    expected_count INTEGER,
                    fetched_count INTEGER NOT NULL,
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
