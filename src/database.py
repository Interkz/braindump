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

        -- FTS5 virtual tables for full-text search
        CREATE VIRTUAL TABLE IF NOT EXISTS drops_fts USING fts5(
            content,
            content='drops',
            content_rowid='id'
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS topics_fts USING fts5(
            name,
            summary,
            content='topics',
            content_rowid='id'
        );

        -- Triggers to keep drops_fts in sync
        CREATE TRIGGER IF NOT EXISTS drops_fts_insert AFTER INSERT ON drops BEGIN
            INSERT INTO drops_fts(rowid, content) VALUES (new.id, new.content);
        END;

        CREATE TRIGGER IF NOT EXISTS drops_fts_delete AFTER DELETE ON drops BEGIN
            INSERT INTO drops_fts(drops_fts, rowid, content) VALUES('delete', old.id, old.content);
        END;

        CREATE TRIGGER IF NOT EXISTS drops_fts_update AFTER UPDATE ON drops BEGIN
            INSERT INTO drops_fts(drops_fts, rowid, content) VALUES('delete', old.id, old.content);
            INSERT INTO drops_fts(rowid, content) VALUES (new.id, new.content);
        END;

        -- Triggers to keep topics_fts in sync
        CREATE TRIGGER IF NOT EXISTS topics_fts_insert AFTER INSERT ON topics BEGIN
            INSERT INTO topics_fts(rowid, name, summary) VALUES (new.id, new.name, new.summary);
        END;

        CREATE TRIGGER IF NOT EXISTS topics_fts_delete AFTER DELETE ON topics BEGIN
            INSERT INTO topics_fts(topics_fts, rowid, name, summary) VALUES('delete', old.id, old.name, old.summary);
        END;

        CREATE TRIGGER IF NOT EXISTS topics_fts_update AFTER UPDATE ON topics BEGIN
            INSERT INTO topics_fts(topics_fts, rowid, name, summary) VALUES('delete', old.id, old.name, old.summary);
            INSERT INTO topics_fts(rowid, name, summary) VALUES (new.id, new.name, new.summary);
        END;
    """)
    # Rebuild FTS indexes to sync with any existing data
    conn.execute("INSERT INTO drops_fts(drops_fts) VALUES('rebuild')")
    conn.execute("INSERT INTO topics_fts(topics_fts) VALUES('rebuild')")
    conn.commit()
    conn.close()


def _sanitize_fts_query(query: str) -> str:
    """Quote each term to prevent FTS5 syntax injection."""
    terms = query.strip().split()
    if not terms:
        return ""
    return " ".join(f'"{term}"' for term in terms)


def search(query: str) -> dict:
    sanitized = _sanitize_fts_query(query)
    if not sanitized:
        return {"drops": [], "topics": []}
    conn = get_connection()
    drops = conn.execute("""
        SELECT d.id, d.content, d.content_type, d.dropped_at, d.processed, f.rank
        FROM drops_fts f
        JOIN drops d ON d.id = f.rowid
        WHERE drops_fts MATCH ?
        ORDER BY f.rank
    """, (sanitized,)).fetchall()
    topics = conn.execute("""
        SELECT t.id, t.name, t.summary, t.updated_at, f.rank
        FROM topics_fts f
        JOIN topics t ON t.id = f.rowid
        WHERE topics_fts MATCH ?
        ORDER BY f.rank
    """, (sanitized,)).fetchall()
    conn.close()
    return {
        "drops": [dict(r) for r in drops],
        "topics": [dict(r) for r in topics],
    }


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
    rows = conn.execute(
        "SELECT * FROM topics ORDER BY updated_at DESC"
    ).fetchall()
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
