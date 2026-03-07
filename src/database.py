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


def get_analytics() -> dict:
    conn = get_connection()

    total_drops = conn.execute("SELECT COUNT(*) as cnt FROM drops").fetchone()["cnt"]
    total_topics = conn.execute("SELECT COUNT(*) as cnt FROM topics").fetchone()["cnt"]

    # Drops per day for last 7 days
    rows = conn.execute("""
        SELECT date(dropped_at) as day, COUNT(*) as cnt
        FROM drops
        WHERE dropped_at >= date('now', '-6 days')
        GROUP BY date(dropped_at)
        ORDER BY day ASC
    """).fetchall()
    drops_per_day = [{"date": r["day"], "count": r["cnt"]} for r in rows]

    # Most active topic (most linked drops)
    most_active = conn.execute("""
        SELECT t.name, COUNT(dt.drop_id) as drop_count
        FROM topics t
        JOIN drop_topics dt ON t.id = dt.topic_id
        GROUP BY t.id
        ORDER BY drop_count DESC
        LIMIT 1
    """).fetchone()
    most_active_topic = (
        {"name": most_active["name"], "drop_count": most_active["drop_count"]}
        if most_active else None
    )

    # Content type breakdown
    type_rows = conn.execute("""
        SELECT content_type, COUNT(*) as cnt
        FROM drops
        GROUP BY content_type
    """).fetchall()
    content_types = {r["content_type"]: r["cnt"] for r in type_rows}

    # Average drops per day (across all days that have drops)
    avg_row = conn.execute("""
        SELECT AVG(daily_count) as avg_drops FROM (
            SELECT COUNT(*) as daily_count
            FROM drops
            GROUP BY date(dropped_at)
        )
    """).fetchone()
    avg_drops_per_day = round(avg_row["avg_drops"], 1) if avg_row["avg_drops"] else 0

    conn.close()
    return {
        "total_drops": total_drops,
        "total_topics": total_topics,
        "drops_per_day": drops_per_day,
        "most_active_topic": most_active_topic,
        "content_types": content_types,
        "avg_drops_per_day": avg_drops_per_day,
    }


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
