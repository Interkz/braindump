import sqlite3

import pytest
from fastapi.testclient import TestClient

from src import database as db
from src.main import app


@pytest.fixture(autouse=True)
def _use_temp_db(tmp_path, monkeypatch):
    """Use a temporary database for each test."""
    test_db = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.init_db()
    yield


@pytest.fixture
def client():
    return TestClient(app)


def _create_topic(name: str, summary: str | None = None) -> int:
    conn = db.get_connection()
    cursor = conn.execute(
        "INSERT INTO topics (name, summary) VALUES (?, ?)", (name, summary)
    )
    topic_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return topic_id


def _create_drop(content: str) -> int:
    conn = db.get_connection()
    cursor = conn.execute(
        "INSERT INTO drops (content, content_type) VALUES (?, 'text')", (content,)
    )
    drop_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return drop_id


def _link_drop_topic(drop_id: int, topic_id: int, relevance: float = 1.0):
    conn = db.get_connection()
    conn.execute(
        "INSERT INTO drop_topics (drop_id, topic_id, relevance) VALUES (?, ?, ?)",
        (drop_id, topic_id, relevance),
    )
    conn.commit()
    conn.close()


# --- database.merge_topics tests ---


class TestMergeTopicsDB:
    def test_moves_drops_from_source_to_target(self):
        source = _create_topic("python", "Python stuff")
        target = _create_topic("programming", "Programming stuff")
        drop1 = _create_drop("learn python")
        drop2 = _create_drop("python decorators")
        _link_drop_topic(drop1, source)
        _link_drop_topic(drop2, source)

        db.merge_topics(source, target)

        conn = db.get_connection()
        rows = conn.execute(
            "SELECT drop_id FROM drop_topics WHERE topic_id = ? ORDER BY drop_id",
            (target,),
        ).fetchall()
        conn.close()
        assert [r["drop_id"] for r in rows] == [drop1, drop2]

    def test_deletes_source_topic(self):
        source = _create_topic("python")
        target = _create_topic("programming")

        db.merge_topics(source, target)

        conn = db.get_connection()
        row = conn.execute("SELECT * FROM topics WHERE id = ?", (source,)).fetchone()
        conn.close()
        assert row is None

    def test_combines_summaries(self):
        source = _create_topic("python", "Python language notes")
        target = _create_topic("programming", "General programming")

        db.merge_topics(source, target)

        conn = db.get_connection()
        row = conn.execute("SELECT summary FROM topics WHERE id = ?", (target,)).fetchone()
        conn.close()
        assert "General programming" in row["summary"]
        assert "Python language notes" in row["summary"]

    def test_handles_none_summaries(self):
        source = _create_topic("python", None)
        target = _create_topic("programming", "General programming")

        db.merge_topics(source, target)

        conn = db.get_connection()
        row = conn.execute("SELECT summary FROM topics WHERE id = ?", (target,)).fetchone()
        conn.close()
        assert row["summary"] == "General programming"

    def test_handles_both_none_summaries(self):
        source = _create_topic("python", None)
        target = _create_topic("programming", None)

        db.merge_topics(source, target)

        conn = db.get_connection()
        row = conn.execute("SELECT summary FROM topics WHERE id = ?", (target,)).fetchone()
        conn.close()
        assert row["summary"] is None

    def test_handles_duplicate_drop_assignments(self):
        """If a drop is linked to both source and target, keep target's link."""
        source = _create_topic("python", "Python stuff")
        target = _create_topic("programming", "Programming stuff")
        drop = _create_drop("learn python")
        _link_drop_topic(drop, source, relevance=0.5)
        _link_drop_topic(drop, target, relevance=0.9)

        db.merge_topics(source, target)

        conn = db.get_connection()
        rows = conn.execute(
            "SELECT * FROM drop_topics WHERE drop_id = ?", (drop,)
        ).fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0]["topic_id"] == target
        assert rows[0]["relevance"] == 0.9

    def test_raises_on_missing_source(self):
        target = _create_topic("programming")
        with pytest.raises(ValueError, match="Source topic 9999 not found"):
            db.merge_topics(9999, target)

    def test_raises_on_missing_target(self):
        source = _create_topic("python")
        with pytest.raises(ValueError, match="Target topic 9999 not found"):
            db.merge_topics(source, 9999)

    def test_preserves_existing_target_drops(self):
        source = _create_topic("python")
        target = _create_topic("programming")
        drop1 = _create_drop("existing target drop")
        drop2 = _create_drop("source drop")
        _link_drop_topic(drop1, target)
        _link_drop_topic(drop2, source)

        db.merge_topics(source, target)

        conn = db.get_connection()
        rows = conn.execute(
            "SELECT drop_id FROM drop_topics WHERE topic_id = ? ORDER BY drop_id",
            (target,),
        ).fetchall()
        conn.close()
        assert [r["drop_id"] for r in rows] == sorted([drop1, drop2])


# --- API endpoint tests ---


class TestMergeTopicsAPI:
    def test_merge_returns_success(self, client):
        source = _create_topic("python", "Python stuff")
        target = _create_topic("programming", "Programming stuff")
        drop = _create_drop("learn python")
        _link_drop_topic(drop, source)

        resp = client.post(
            "/api/topics/merge",
            json={"source_topic_id": source, "target_topic_id": target},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["target_topic"]["id"] == target

    def test_merge_404_missing_source(self, client):
        target = _create_topic("programming")
        resp = client.post(
            "/api/topics/merge",
            json={"source_topic_id": 9999, "target_topic_id": target},
        )
        assert resp.status_code == 404

    def test_merge_404_missing_target(self, client):
        source = _create_topic("python")
        resp = client.post(
            "/api/topics/merge",
            json={"source_topic_id": source, "target_topic_id": 9999},
        )
        assert resp.status_code == 404
