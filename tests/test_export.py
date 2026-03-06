import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# Point DB to a temp file before importing app
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["BRAINDUMP_DB_PATH"] = _tmp.name

from src import database as db  # noqa: E402
from src.main import app  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_db():
    """Re-initialise the DB for every test."""
    db.init_db()
    conn = db.get_connection()
    conn.execute("DELETE FROM drop_topics")
    conn.execute("DELETE FROM topics")
    conn.execute("DELETE FROM drops")
    conn.commit()
    conn.close()
    yield


def _seed_data():
    """Insert a few drops and topics with associations."""
    conn = db.get_connection()
    conn.execute(
        "INSERT INTO drops (id, content, content_type) VALUES (1, 'learn rust', 'text')"
    )
    conn.execute(
        "INSERT INTO drops (id, content, content_type) VALUES (2, 'read SICP', 'text')"
    )
    conn.execute(
        "INSERT INTO drops (id, content, content_type) VALUES (3, 'buy milk', 'text')"
    )
    conn.execute(
        "INSERT INTO topics (id, name, summary) VALUES (1, 'Programming', 'Programming-related notes')"
    )
    conn.execute(
        "INSERT INTO topics (id, name, summary) VALUES (2, 'Errands', 'Daily errands')"
    )
    conn.execute("INSERT INTO drop_topics (drop_id, topic_id) VALUES (1, 1)")
    conn.execute("INSERT INTO drop_topics (drop_id, topic_id) VALUES (2, 1)")
    conn.execute("INSERT INTO drop_topics (drop_id, topic_id) VALUES (3, 2)")
    conn.commit()
    conn.close()


# ── JSON export ──────────────────────────────────────────────


class TestExportJSON:
    def test_returns_json_attachment(self):
        _seed_data()
        resp = client.get("/api/export")
        assert resp.status_code == 200
        assert "application/json" in resp.headers["content-type"]
        assert "attachment" in resp.headers["content-disposition"]
        assert "braindump" in resp.headers["content-disposition"]

    def test_json_contains_all_drops(self):
        _seed_data()
        resp = client.get("/api/export")
        data = resp.json()
        assert len(data["drops"]) == 3

    def test_json_empty_db(self):
        resp = client.get("/api/export")
        data = resp.json()
        assert data["drops"] == []


# ── Markdown export ──────────────────────────────────────────


class TestExportMarkdown:
    def test_returns_markdown_attachment(self):
        _seed_data()
        resp = client.get("/api/export?format=markdown")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/markdown")
        assert "attachment" in resp.headers["content-disposition"]

    def test_markdown_has_topic_headers(self):
        _seed_data()
        resp = client.get("/api/export?format=markdown")
        text = resp.text
        assert "# Programming" in text
        assert "# Errands" in text

    def test_markdown_has_drops_as_bullets(self):
        _seed_data()
        resp = client.get("/api/export?format=markdown")
        text = resp.text
        assert "- learn rust" in text
        assert "- read SICP" in text
        assert "- buy milk" in text

    def test_markdown_uncategorised_drops(self):
        """Drops without a topic should appear under an Uncategorised heading."""
        conn = db.get_connection()
        conn.execute(
            "INSERT INTO drops (id, content, content_type) VALUES (1, 'random thought', 'text')"
        )
        conn.commit()
        conn.close()

        resp = client.get("/api/export?format=markdown")
        text = resp.text
        assert "# Uncategorised" in text
        assert "- random thought" in text

    def test_markdown_empty_db(self):
        resp = client.get("/api/export?format=markdown")
        assert resp.status_code == 200
        # Should still be valid (possibly empty) markdown
        assert resp.text is not None
