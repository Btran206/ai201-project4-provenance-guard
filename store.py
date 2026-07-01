import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "provenance.db"


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS content_records (
                content_id     TEXT PRIMARY KEY,
                text           TEXT NOT NULL,
                creator_id     TEXT,
                timestamp      TEXT NOT NULL,
                status         TEXT NOT NULL DEFAULT 'processing',
                classification TEXT,
                confidence     REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                event          TEXT NOT NULL,
                content_id     TEXT NOT NULL,
                timestamp      TEXT NOT NULL,
                classification TEXT,
                attribution    TEXT,
                confidence     REAL,
                signals_used   TEXT,
                heuristic_score REAL,
                llm_score      REAL,
                appeal_id      TEXT,
                appeal_reason  TEXT,
                status         TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS appeals (
                appeal_id   TEXT PRIMARY KEY,
                content_id  TEXT NOT NULL,
                creator_id  TEXT,
                reason      TEXT NOT NULL,
                timestamp   TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'under_review'
            )
        """)
        conn.commit()


def get_log(limit: int = 50) -> list:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


def insert_content(content_id: str, text: str, creator_id, timestamp: str):
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO content_records (content_id, text, creator_id, timestamp, status)
            VALUES (?, ?, ?, ?, 'processing')
            """,
            (content_id, text, creator_id, timestamp),
        )
        conn.commit()


def update_content_status(content_id: str, status: str, classification: str, confidence: float):
    with _connect() as conn:
        conn.execute(
            """
            UPDATE content_records
            SET status = ?, classification = ?, confidence = ?
            WHERE content_id = ?
            """,
            (status, classification, confidence, content_id),
        )
        conn.commit()


def insert_audit_log(
    event: str,
    content_id: str,
    timestamp: str,
    classification: str,
    attribution: str,
    confidence: float,
    heuristic_score: float,
    llm_score: float,
    status: str,
    appeal_id: str | None = None,
    appeal_reason: str | None = None,
):
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO audit_log (
                event, content_id, timestamp, classification, attribution,
                confidence, signals_used, heuristic_score, llm_score,
                appeal_id, appeal_reason, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event, content_id, timestamp, classification, attribution,
                confidence, '["heuristic", "llm"]', heuristic_score, llm_score,
                appeal_id, appeal_reason, status,
            ),
        )
        conn.commit()


def get_content(content_id: str):
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM content_records WHERE content_id = ?", (content_id,)
        ).fetchone()
    return dict(row) if row else None


def get_appeal_by_content_id(content_id: str):
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM appeals WHERE content_id = ?", (content_id,)
        ).fetchone()
    return dict(row) if row else None


def insert_appeal(appeal_id: str, content_id: str, creator_id, reason: str, timestamp: str):
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO appeals (appeal_id, content_id, creator_id, reason, timestamp, status)
            VALUES (?, ?, ?, ?, ?, 'under_review')
            """,
            (appeal_id, content_id, creator_id, reason, timestamp),
        )
        conn.commit()


def update_content_appeal_status(content_id: str, status: str):
    with _connect() as conn:
        conn.execute(
            "UPDATE content_records SET status = ? WHERE content_id = ?",
            (status, content_id),
        )
        conn.commit()
