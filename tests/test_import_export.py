import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src import database as db


@pytest.fixture(autouse=True)
def temp_db(tmp_path):
    """Use a temporary database for each test."""
    test_db = tmp_path / "test.db"
    with patch.object(db, "DB_PATH", test_db):
        db.init_db()
        yield test_db


@pytest.fixture
def client(temp_db):
    from src.main import app
    return TestClient(app)


# --- Database layer tests ---


class TestExportAll:
    def test_export_empty_db(self):
        result = db.export_all()
        assert result == {"drops": [], "topics": []}

    def test_export_with_drops(self):
        db.insert_drop("hello world")
        db.insert_drop("https://example.com")
        result = db.export_all()
        assert len(result["drops"]) == 2
        assert result["drops"][0]["content"] == "hello world"
        assert result["drops"][1]["content"] == "https://example.com"

    def test_export_includes_topics(self):
        conn = db.get_connection()
        conn.execute("INSERT INTO topics (name, summary) VALUES (?, ?)", ("Tech", "A summary"))
        conn.commit()
        conn.close()
        result = db.export_all()
        assert len(result["topics"]) == 1
        assert result["topics"][0]["name"] == "Tech"


class TestImportDrops:
    def test_import_new_drops(self):
        drops = [
            {"content": "first drop", "content_type": "text"},
            {"content": "second drop", "content_type": "text"},
        ]
        result = db.import_drops(drops)
        assert result["imported"] == 2
        assert result["skipped"] == 0
        assert db.count_drops() == 2

    def test_import_skips_duplicates(self):
        db.insert_drop("already exists")
        drops = [
            {"content": "already exists", "content_type": "text"},
            {"content": "new one", "content_type": "text"},
        ]
        result = db.import_drops(drops)
        assert result["imported"] == 1
        assert result["skipped"] == 1
        assert db.count_drops() == 2

    def test_import_skips_duplicates_within_batch(self):
        drops = [
            {"content": "same", "content_type": "text"},
            {"content": "same", "content_type": "text"},
        ]
        result = db.import_drops(drops)
        assert result["imported"] == 1
        assert result["skipped"] == 1

    def test_import_empty_list(self):
        result = db.import_drops([])
        assert result["imported"] == 0
        assert result["skipped"] == 0

    def test_import_auto_classifies_content_type(self):
        drops = [
            {"content": "https://example.com"},
            {"content": "just text"},
        ]
        result = db.import_drops(drops)
        assert result["imported"] == 2
        all_drops = db.get_recent_drops()
        contents = {d["content"]: d["content_type"] for d in all_drops}
        assert contents["https://example.com"] == "link"
        assert contents["just text"] == "text"


# --- API route tests ---


class TestExportRoute:
    def test_export_returns_json_download(self, client):
        response = client.get("/api/export")
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]
        assert "attachment" in response.headers.get("content-disposition", "")
        assert "braindump" in response.headers.get("content-disposition", "")
        data = response.json()
        assert "drops" in data
        assert "topics" in data

    def test_export_with_data(self, client):
        client.post("/api/drop", json={"content": "test drop"})
        response = client.get("/api/export")
        data = response.json()
        assert len(data["drops"]) == 1
        assert data["drops"][0]["content"] == "test drop"


class TestImportRoute:
    def test_import_returns_count(self, client):
        response = client.post("/api/import", json={
            "drops": [
                {"content": "imported drop", "content_type": "text"},
            ]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["imported"] == 1
        assert data["skipped"] == 0

    def test_import_skips_duplicates(self, client):
        client.post("/api/drop", json={"content": "existing"})
        response = client.post("/api/import", json={
            "drops": [
                {"content": "existing", "content_type": "text"},
                {"content": "brand new", "content_type": "text"},
            ]
        })
        data = response.json()
        assert data["imported"] == 1
        assert data["skipped"] == 1

    def test_import_empty_drops(self, client):
        response = client.post("/api/import", json={"drops": []})
        assert response.status_code == 200
        data = response.json()
        assert data["imported"] == 0
