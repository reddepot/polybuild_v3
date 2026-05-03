"""Tests unitaires pour validate_fts5 — golden query gate."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from polybuild.domain_gates.validate_fts5 import validate_fts5_golden


class TestFTS5MissingInputs:
    def test_db_not_found(self, tmp_path: Path) -> None:
        result = validate_fts5_golden(
            db_path="/nonexistent/db.sqlite",
            fts_table="articles_fts",
            golden_path="/nonexistent/golden.json",
        )
        assert result.passed is False
        assert any("db_not_found" in e for e in result.errors)

    def test_golden_missing_required(self, tmp_path: Path) -> None:
        db = tmp_path / "db.sqlite"
        sqlite3.connect(str(db)).execute("CREATE TABLE t (id INTEGER PRIMARY KEY)").connection.close()
        result = validate_fts5_golden(
            db_path=db,
            fts_table="t",
            golden_path="/nonexistent/golden.json",
            require_golden_file=True,
        )
        assert result.passed is False
        assert any("golden_file_not_found" in e for e in result.errors)

    def test_golden_missing_optional_skips(self, tmp_path: Path) -> None:
        """Round 6 fix [fts5-skipped] : skipped=True quand golden manquant en mode optional."""
        db = tmp_path / "db.sqlite"
        sqlite3.connect(str(db)).close()
        result = validate_fts5_golden(
            db_path=db,
            fts_table="t",
            golden_path="/nonexistent/golden.json",
            require_golden_file=False,
        )
        assert result.passed is True
        assert result.skipped is True
        assert any("GOLDEN_SKIPPED_DEV_MODE" in f for f in result.failures)


class TestFTS5GoldenParsing:
    def test_golden_not_a_list_fails(self, tmp_path: Path) -> None:
        db = tmp_path / "db.sqlite"
        sqlite3.connect(str(db)).close()
        golden = tmp_path / "golden.json"
        golden.write_text(json.dumps({"query": "foo", "min_hits": 1}))
        result = validate_fts5_golden(db, "t", golden)
        assert result.passed is False
        assert any("not_a_list" in e for e in result.errors)

    def test_golden_below_minimum_fails(self, tmp_path: Path) -> None:
        db = tmp_path / "db.sqlite"
        sqlite3.connect(str(db)).close()
        golden = tmp_path / "golden.json"
        golden.write_text(json.dumps([{"query": "a", "min_hits": 1}]))
        result = validate_fts5_golden(db, "t", golden)
        assert result.passed is False
        assert any("below_minimum" in e for e in result.errors)

    def test_golden_parse_error(self, tmp_path: Path) -> None:
        db = tmp_path / "db.sqlite"
        sqlite3.connect(str(db)).close()
        golden = tmp_path / "golden.json"
        golden.write_text("not json")
        result = validate_fts5_golden(db, "t", golden)
        assert result.passed is False
        assert any("parse_error" in e for e in result.errors)


class TestFTS5Functional:
    def _create_fts_db(self, db_path: Path) -> None:
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE articles (id INTEGER PRIMARY KEY, title TEXT, body TEXT)")
        conn.execute(
            "CREATE VIRTUAL TABLE articles_fts USING fts5(title, body, content=articles, content_rowid=id)"
        )
        # Insert into both base table and fts5 virtual table for immediate indexing
        rows = [
            (1, 'amiante', 'risque pro'),
            (2, 'amiante', 'maladie'),
            (3, 'burnout', 'RPS'),
            (4, 'amiante', 'prévention'),
            (5, 'amiante', 'désamiantage'),
            (6, 'amiante', 'tableau MP'),
        ]
        for rowid, title, body in rows:
            conn.execute("INSERT INTO articles (id, title, body) VALUES (?, ?, ?)", (rowid, title, body))
            conn.execute("INSERT INTO articles_fts (rowid, title, body) VALUES (?, ?, ?)", (rowid, title, body))
        conn.commit()
        conn.close()

    def test_all_queries_pass(self, tmp_path: Path) -> None:
        db = tmp_path / "db.sqlite"
        self._create_fts_db(db)
        golden = tmp_path / "golden.json"
        golden.write_text(json.dumps([
            {"query": "amiante", "min_hits": 5},
            {"query": "burnout", "min_hits": 1},
            {"query": "prévention", "min_hits": 1},
        ]))
        result = validate_fts5_golden(db, "articles_fts", golden)
        assert result.passed is True
        assert result.n_passed == 3
        assert result.n_queries == 3

    def test_min_hits_failure(self, tmp_path: Path) -> None:
        db = tmp_path / "db.sqlite"
        self._create_fts_db(db)
        golden = tmp_path / "golden.json"
        golden.write_text(json.dumps([
            {"query": "amiante", "min_hits": 10},  # il y en a 5
        ]))
        result = validate_fts5_golden(db, "articles_fts", golden)
        assert result.passed is False
        assert result.n_passed == 0
        assert any("hits=5 < min=10" in f for f in result.failures)

    def test_max_hits_failure(self, tmp_path: Path) -> None:
        db = tmp_path / "db.sqlite"
        self._create_fts_db(db)
        golden = tmp_path / "golden.json"
        golden.write_text(json.dumps([
            {"query": "amiante", "min_hits": 1, "max_hits": 2},
        ]))
        result = validate_fts5_golden(db, "articles_fts", golden)
        assert result.passed is False
        assert any("hits=5 > max=2" in f for f in result.failures)

    def test_empty_query_skipped(self, tmp_path: Path) -> None:
        db = tmp_path / "db.sqlite"
        self._create_fts_db(db)
        golden = tmp_path / "golden.json"
        golden.write_text(json.dumps([
            {"query": "", "min_hits": 1},
            {"query": "burnout", "min_hits": 1},
        ]))
        result = validate_fts5_golden(db, "articles_fts", golden)
        assert result.passed is True
        assert result.n_passed == 1

    def test_sqlite_error_on_bad_table(self, tmp_path: Path) -> None:
        db = tmp_path / "db.sqlite"
        sqlite3.connect(str(db)).execute("CREATE TABLE t (id INTEGER PRIMARY KEY)").connection.close()
        golden = tmp_path / "golden.json"
        golden.write_text(json.dumps([
            {"query": "foo", "min_hits": 1},
            {"query": "bar", "min_hits": 1},
            {"query": "baz", "min_hits": 1},
        ]))
        result = validate_fts5_golden(db, "bad_table", golden)
        assert result.passed is False
        assert result.failures  # sqlite errors recorded
