import sqlite3
from datetime import date, datetime, timedelta
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


def get_daily_streak() -> int:
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT date(dropped_at) as d FROM drops ORDER BY d DESC"
    ).fetchall()
    conn.close()

    if not rows:
        return 0

    dates = [date.fromisoformat(r["d"]) for r in rows]
    today = date.today()

    # Streak must include today or yesterday to be active
    if dates[0] != today and dates[0] != today - timedelta(days=1):
        return 0

    streak = 1
    for i in range(1, len(dates)):
        if dates[i - 1] - dates[i] == timedelta(days=1):
            streak += 1
        else:
            break
    return streak


def get_streak_history(days: int = 30) -> list[dict]:
    today = date.today()
    start = today - timedelta(days=days - 1)

    conn = get_connection()
    rows = conn.execute(
        """SELECT date(dropped_at) as d, COUNT(*) as count
           FROM drops
           WHERE date(dropped_at) >= ?
           GROUP BY date(dropped_at)""",
        (start.isoformat(),),
    ).fetchall()
    conn.close()

    counts = {r["d"]: r["count"] for r in rows}
    history = []
    for i in range(days):
        d = start + timedelta(days=i)
        history.append({"date": d.isoformat(), "count": counts.get(d.isoformat(), 0)})
    return history
