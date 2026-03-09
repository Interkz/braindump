import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

_REPO_DB = Path(__file__).parent.parent / "braindump.db"

if os.environ.get("VERCEL"):
    DB_PATH = Path("/tmp/braindump.db")
    if not DB_PATH.exists() and _REPO_DB.exists():
        shutil.copy2(str(_REPO_DB), str(DB_PATH))
else:
    DB_PATH = _REPO_DB


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


def split_topic(source_topic_id: int, groups: list[dict]) -> list[dict]:
    """Split a topic into multiple new topics.

    Args:
        source_topic_id: The topic to split.
        groups: List of dicts, each with 'name', 'summary' (optional), and 'drop_ids'.

    Returns:
        List of newly created topic dicts.
    """
    conn = get_connection()

    # Verify source topic exists
    source = conn.execute("SELECT * FROM topics WHERE id = ?", (source_topic_id,)).fetchone()
    if not source:
        conn.close()
        raise ValueError(f"Topic {source_topic_id} not found")

    # Get all drop IDs currently in this topic
    current_drops = conn.execute(
        "SELECT drop_id FROM drop_topics WHERE topic_id = ?", (source_topic_id,)
    ).fetchall()
    current_drop_ids = {row["drop_id"] for row in current_drops}

    # Validate that all provided drop IDs belong to this topic
    all_specified_ids = set()
    for group in groups:
        for did in group["drop_ids"]:
            if did not in current_drop_ids:
                conn.close()
                raise ValueError(f"Drop {did} does not belong to topic {source_topic_id}")
            all_specified_ids.add(did)

    new_topics = []
    for group in groups:
        name = group["name"]
        summary = group.get("summary", "")
        drop_ids = group["drop_ids"]
        if not drop_ids:
            continue

        # Create new topic
        cursor = conn.execute(
            "INSERT INTO topics (name, summary) VALUES (?, ?)",
            (name, summary),
        )
        new_topic_id = cursor.lastrowid

        # Move drops from old topic to new topic
        for did in drop_ids:
            # Get existing relevance
            rel_row = conn.execute(
                "SELECT relevance FROM drop_topics WHERE drop_id = ? AND topic_id = ?",
                (did, source_topic_id),
            ).fetchone()
            relevance = rel_row["relevance"] if rel_row else 1.0

            # Remove from source topic
            conn.execute(
                "DELETE FROM drop_topics WHERE drop_id = ? AND topic_id = ?",
                (did, source_topic_id),
            )
            # Add to new topic
            conn.execute(
                "INSERT INTO drop_topics (drop_id, topic_id, relevance) VALUES (?, ?, ?)",
                (did, new_topic_id, relevance),
            )

        new_topics.append({"id": new_topic_id, "name": name, "summary": summary, "drop_count": len(drop_ids)})

    # Check if source topic has any remaining drops
    remaining = conn.execute(
        "SELECT COUNT(*) as cnt FROM drop_topics WHERE topic_id = ?", (source_topic_id,)
    ).fetchone()

    if remaining["cnt"] == 0:
        # Delete the now-empty source topic
        conn.execute("DELETE FROM topics WHERE id = ?", (source_topic_id,))
    else:
        # Update the source topic's timestamp
        conn.execute(
            "UPDATE topics SET updated_at = datetime('now') WHERE id = ?",
            (source_topic_id,),
        )

    conn.commit()
    conn.close()
    return new_topics
