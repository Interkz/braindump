"""Tests for time-based filtering of drops."""

import sqlite3
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src import database as db
from src.main import app


@pytest.fixture(autouse=True)
def temp_db(tmp_path):
    """Use a temporary database for each test."""
    test_db = tmp_path / "test.db"
    with patch.object(db, "DB_PATH", test_db):
        db.init_db()
        yield test_db


def _insert_drop_at(content: str, dropped_at: datetime):
    """Insert a drop with a specific timestamp."""
    conn = db.get_connection()
    conn.execute(
        "INSERT INTO drops (content, content_type, dropped_at) VALUES (?, 'text', ?)",
        (content, dropped_at.strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    conn.close()


class TestGetRecentDropsTimeRange:
    def test_default_returns_all(self):
        now = datetime.utcnow()
        _insert_drop_at("today", now)
        _insert_drop_at("old", now - timedelta(days=60))
        result = db.get_recent_drops()
        assert len(result) == 2

    def test_today_filter(self):
        now = datetime.utcnow()
        _insert_drop_at("today", now)
        _insert_drop_at("yesterday", now - timedelta(days=1, hours=1))
        result = db.get_recent_drops(time_range="today")
        assert len(result) == 1
        assert result[0]["content"] == "today"

    def test_week_filter(self):
        now = datetime.utcnow()
        _insert_drop_at("recent", now - timedelta(days=2))
        _insert_drop_at("old", now - timedelta(days=10))
        result = db.get_recent_drops(time_range="week")
        assert len(result) == 1
        assert result[0]["content"] == "recent"

    def test_month_filter(self):
        now = datetime.utcnow()
        _insert_drop_at("recent", now - timedelta(days=15))
        _insert_drop_at("old", now - timedelta(days=45))
        result = db.get_recent_drops(time_range="month")
        assert len(result) == 1
        assert result[0]["content"] == "recent"

    def test_all_filter_returns_everything(self):
        now = datetime.utcnow()
        _insert_drop_at("new", now)
        _insert_drop_at("old", now - timedelta(days=365))
        result = db.get_recent_drops(time_range="all")
        assert len(result) == 2

    def test_invalid_range_returns_all(self):
        now = datetime.utcnow()
        _insert_drop_at("a", now)
        _insert_drop_at("b", now - timedelta(days=365))
        result = db.get_recent_drops(time_range="garbage")
        assert len(result) == 2


class TestCountDropsTimeRange:
    def test_count_default_all(self):
        now = datetime.utcnow()
        _insert_drop_at("a", now)
        _insert_drop_at("b", now - timedelta(days=60))
        assert db.count_drops() == 2

    def test_count_today(self):
        now = datetime.utcnow()
        _insert_drop_at("a", now)
        _insert_drop_at("b", now - timedelta(days=2))
        assert db.count_drops(time_range="today") == 1

    def test_count_week(self):
        now = datetime.utcnow()
        _insert_drop_at("a", now)
        _insert_drop_at("b", now - timedelta(days=10))
        assert db.count_drops(time_range="week") == 1


class TestAPIDropsRange:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_drops_with_range_param(self, client):
        now = datetime.utcnow()
        _insert_drop_at("today", now)
        _insert_drop_at("old", now - timedelta(days=60))
        resp = client.get("/api/drops?range=today")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["drops"]) == 1

    def test_drops_count_with_range(self, client):
        now = datetime.utcnow()
        _insert_drop_at("today", now)
        _insert_drop_at("old", now - timedelta(days=60))
        resp = client.get("/api/drops?count_only=true&range=today")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1

    def test_drops_default_no_range(self, client):
        now = datetime.utcnow()
        _insert_drop_at("a", now)
        _insert_drop_at("b", now - timedelta(days=60))
        resp = client.get("/api/drops")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["drops"]) == 2
