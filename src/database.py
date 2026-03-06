import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "braindump.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS drops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            content_type TEXT NOT NULL DEFAULT 'text',
            dropped_at DATETIME NOT NULL DEFAULT (datetime('now')),
            processed BOOLEAN NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            summary TEXT,
            updated_at DATETIME NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS drop_topics (
            drop_id INTEGER NOT NULL REFERENCES drops(id) ON DELETE CASCADE,
            topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            relevance REAL NOT NULL DEFAULT 1.0,
            PRIMARY KEY (drop_id, topic_id)
        );
    """)
    conn.close()


def classify_content(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith(("http://", "https://", "www.")):
        return "link"
    return "text"


def insert_drop(content: str) -> dict:
    conn = get_connection()
    content_type = classify_content(content)
    cursor = conn.execute(
        "INSERT INTO drops (content, content_type) VALUES (?, ?)",
        (content, content_type),
    )
    drop_id = cursor.lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM drops WHERE id = ?", (drop_id,)).fetchone()
    conn.close()
    return dict(row)


def count_drops() -> int:
    conn = get_connection()
    row = conn.execute("SELECT COUNT(*) as cnt FROM drops").fetchone()
    conn.close()
    return row["cnt"]


def get_recent_drops(limit: int = 50) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM drops ORDER BY dropped_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_topics_with_summaries() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT t.*, COUNT(dt.drop_id) as drop_count
        FROM topics t
        LEFT JOIN drop_topics dt ON t.id = dt.topic_id
        GROUP BY t.id
        ORDER BY t.updated_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def merge_topics(source_topic_id: int, target_topic_id: int) -> dict:
    conn = get_connection()
    try:
        source = conn.execute(
            "SELECT * FROM topics WHERE id = ?", (source_topic_id,)
        ).fetchone()
        if not source:
            raise ValueError(f"Source topic {source_topic_id} not found")

        target = conn.execute(
            "SELECT * FROM topics WHERE id = ?", (target_topic_id,)
        ).fetchone()
        if not target:
            raise ValueError(f"Target topic {target_topic_id} not found")

        # Find drops already linked to target (to avoid duplicates)
        existing = conn.execute(
            "SELECT drop_id FROM drop_topics WHERE topic_id = ?", (target_topic_id,)
        ).fetchall()
        existing_drop_ids = {r["drop_id"] for r in existing}

        # Move non-duplicate drops from source to target
        source_links = conn.execute(
            "SELECT drop_id, relevance FROM drop_topics WHERE topic_id = ?",
            (source_topic_id,),
        ).fetchall()
        for link in source_links:
            if link["drop_id"] not in existing_drop_ids:
                conn.execute(
                    "UPDATE drop_topics SET topic_id = ? WHERE drop_id = ? AND topic_id = ?",
                    (target_topic_id, link["drop_id"], source_topic_id),
                )

        # Delete remaining source links (duplicates)
        conn.execute(
            "DELETE FROM drop_topics WHERE topic_id = ?", (source_topic_id,)
        )

        # Combine summaries
        source_summary = source["summary"]
        target_summary = target["summary"]
        if source_summary and target_summary:
            combined = f"{target_summary}\n\n{source_summary}"
        else:
            combined = target_summary or source_summary

        conn.execute(
            "UPDATE topics SET summary = ?, updated_at = datetime('now') WHERE id = ?",
            (combined, target_topic_id),
        )

        # Delete source topic
        conn.execute("DELETE FROM topics WHERE id = ?", (source_topic_id,))

        conn.commit()

        updated = conn.execute(
            "SELECT * FROM topics WHERE id = ?", (target_topic_id,)
        ).fetchone()
        return dict(updated)
    finally:
        conn.close()


def get_topic_with_drops(topic_id: int) -> dict | None:
    conn = get_connection()
    topic = conn.execute("SELECT * FROM topics WHERE id = ?", (topic_id,)).fetchone()
    if not topic:
        conn.close()
        return None
    drops = conn.execute("""
        SELECT d.*, dt.relevance
        FROM drops d
        JOIN drop_topics dt ON d.id = dt.drop_id
        WHERE dt.topic_id = ?
        ORDER BY dt.relevance DESC, d.dropped_at DESC
    """, (topic_id,)).fetchall()
    conn.close()
    return {"topic": dict(topic), "drops": [dict(d) for d in drops]}
