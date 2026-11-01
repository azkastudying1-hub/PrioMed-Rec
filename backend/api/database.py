"""
api/database.py
----------------
SQLite persistence layer for PrioMed-Rec.

Tables:
  bpmh_records   — Best Possible Medication History per patient
  audit_entries  — Pharmacist review audit trail
  ward_configs   — Ward capacity configuration
  patient_status — Workflow status per patient
  local_high_alert — Hospital-specific high-alert medications
"""

from __future__ import annotations
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

# Database file path — can be overridden via env var DB_PATH
import os
_DB_PATH = os.getenv("DB_PATH", str(Path(__file__).parent.parent / "data" / "priomed.db"))


def get_db_path() -> str:
    return os.getenv("DB_PATH", _DB_PATH)


_INIT_DONE = False

@contextmanager
def get_db():
    """Context manager: yields a sqlite3 connection with row_factory = dict-like."""
    global _INIT_DONE
    if not _INIT_DONE:
        try:
            init_database()
            _INIT_DONE = True
        except Exception:
            pass
    conn = sqlite3.connect(get_db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database(db_path: Optional[str] = None) -> None:
    """Create all tables if they don't exist. Called on FastAPI startup."""
    path = db_path or get_db_path()
    # Ensure data directory exists
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS bpmh_records (
                patient_id      TEXT NOT NULL,
                encounter_id    TEXT NOT NULL,
                pharmacist_id   TEXT,
                saved_at        TEXT NOT NULL,
                source_notes    TEXT,
                medications_json TEXT NOT NULL,
                PRIMARY KEY (patient_id, encounter_id)
            );

            CREATE TABLE IF NOT EXISTS audit_entries (
                review_id       TEXT PRIMARY KEY,
                case_id         TEXT NOT NULL,
                patient_id      TEXT,
                pharmacist_id   TEXT,
                action          TEXT NOT NULL,
                timestamp       TEXT NOT NULL,
                note            TEXT,
                model_version   TEXT,
                rule_version    TEXT,
                ai_result_json  TEXT
            );

            CREATE TABLE IF NOT EXISTS ward_configs (
                ward_id         TEXT PRIMARY KEY,
                ward_name       TEXT NOT NULL,
                capacity        INTEGER NOT NULL DEFAULT 10,
                allocated       INTEGER NOT NULL DEFAULT 0,
                pharmacists     INTEGER NOT NULL DEFAULT 1,
                updated_at      TEXT
            );

            CREATE TABLE IF NOT EXISTS patient_status (
                patient_id      TEXT NOT NULL,
                encounter_id    TEXT NOT NULL,
                workflow_status TEXT NOT NULL DEFAULT 'MENUNGGU_BPMH',
                updated_at      TEXT,
                updated_by      TEXT,
                PRIMARY KEY (patient_id, encounter_id)
            );

            CREATE TABLE IF NOT EXISTS local_high_alert (
                drug_name       TEXT PRIMARY KEY,
                category        TEXT,
                added_by        TEXT,
                added_at        TEXT
            );
        """)
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# BPMH helpers
# ---------------------------------------------------------------------------

def save_bpmh(patient_id: str, encounter_id: str, pharmacist_id: Optional[str],
              source_notes: Optional[str], medications: list, saved_at: str) -> None:
    with get_db() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO bpmh_records
               (patient_id, encounter_id, pharmacist_id, saved_at, source_notes, medications_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (patient_id, encounter_id, pharmacist_id, saved_at, source_notes, json.dumps(medications))
        )
        # Update patient_status
        conn.execute(
            """INSERT OR REPLACE INTO patient_status
               (patient_id, encounter_id, workflow_status, updated_at, updated_by)
               VALUES (?, ?, 'BPMH_TERISI', ?, ?)""",
            (patient_id, encounter_id, saved_at, pharmacist_id or 'system')
        )


def get_bpmh(patient_id: str) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM bpmh_records WHERE patient_id = ? ORDER BY saved_at DESC LIMIT 1",
            (patient_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d['medications'] = json.loads(d['medications_json'])
        return d


# ---------------------------------------------------------------------------
# Audit helpers
# ---------------------------------------------------------------------------

def save_audit(review_id: str, case_id: str, patient_id: Optional[str],
               pharmacist_id: Optional[str], action: str, timestamp: str,
               note: Optional[str], model_version: str, rule_version: str,
               ai_result: dict) -> None:
    with get_db() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO audit_entries
               (review_id, case_id, patient_id, pharmacist_id, action, timestamp,
                note, model_version, rule_version, ai_result_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (review_id, case_id, patient_id, pharmacist_id, action, timestamp,
             note, model_version, rule_version, json.dumps(ai_result))
        )
        # Update patient_status if patient_id known
        if patient_id:
            status = 'DISETUJUI' if action == 'APPROVE' else ('DITOLAK' if action == 'REJECT' else 'DIEDIT')
            conn.execute(
                """INSERT OR IGNORE INTO patient_status (patient_id, encounter_id, workflow_status, updated_at, updated_by)
                   VALUES (?, '', ?, ?, ?)""",
                (patient_id, status, timestamp, pharmacist_id or 'system')
            )
            conn.execute(
                """UPDATE patient_status SET workflow_status=?, updated_at=?, updated_by=?
                   WHERE patient_id=?""",
                (status, timestamp, pharmacist_id or 'system', patient_id)
            )


def get_audit_log(patient_id: Optional[str] = None, action: Optional[str] = None,
                  date_from: Optional[str] = None, date_to: Optional[str] = None,
                  limit: int = 100) -> list[dict]:
    query = "SELECT * FROM audit_entries WHERE 1=1"
    params: list = []
    if patient_id:
        query += " AND patient_id = ?"
        params.append(patient_id)
    if action:
        query += " AND action = ?"
        params.append(action)
    if date_from:
        query += " AND timestamp >= ?"
        params.append(date_from)
    if date_to:
        query += " AND timestamp <= ?"
        params.append(date_to)
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    
    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            if d.get('ai_result_json'):
                try:
                    d['ai_result'] = json.loads(d['ai_result_json'])
                except Exception:
                    d['ai_result'] = {}
            result.append(d)
        return result


# ---------------------------------------------------------------------------
# Ward helpers
# ---------------------------------------------------------------------------

_DEFAULT_WARDS = [
    {"ward_id": "icu",        "ward_name": "ICU Terpadu",        "capacity": 8,  "allocated": 5,  "pharmacists": 1},
    {"ward_id": "hcu",        "ward_name": "HCU",                "capacity": 6,  "allocated": 4,  "pharmacists": 1},
    {"ward_id": "interna",    "ward_name": "Penyakit Dalam",     "capacity": 12, "allocated": 9,  "pharmacists": 2},
    {"ward_id": "kardiologi", "ward_name": "Kardiologi",         "capacity": 8,  "allocated": 6,  "pharmacists": 1},
    {"ward_id": "bedah",      "ward_name": "Bedah Umum",         "capacity": 10, "allocated": 4,  "pharmacists": 1},
    {"ward_id": "neurologi",  "ward_name": "Neurologi",          "capacity": 7,  "allocated": 3,  "pharmacists": 1},
    {"ward_id": "geriatri",   "ward_name": "Geriatri",           "capacity": 6,  "allocated": 4,  "pharmacists": 1},
]


def get_wards() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM ward_configs").fetchall()
        if not rows:
            # Seed defaults
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()
            for w in _DEFAULT_WARDS:
                conn.execute(
                    "INSERT OR IGNORE INTO ward_configs (ward_id, ward_name, capacity, allocated, pharmacists, updated_at) VALUES (?,?,?,?,?,?)",
                    (w["ward_id"], w["ward_name"], w["capacity"], w["allocated"], w["pharmacists"], now)
                )
            rows = conn.execute("SELECT * FROM ward_configs").fetchall()
        return [dict(r) for r in rows]


def save_wards(wards: list[dict], updated_at: str) -> None:
    with get_db() as conn:
        for w in wards:
            conn.execute(
                """INSERT OR REPLACE INTO ward_configs
                   (ward_id, ward_name, capacity, allocated, pharmacists, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (w["ward_id"], w["ward_name"], w["capacity"], w["allocated"], w.get("pharmacists", 1), updated_at)
            )


# ---------------------------------------------------------------------------
# Local high-alert helpers
# ---------------------------------------------------------------------------

def get_local_high_alerts() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM local_high_alert ORDER BY added_at DESC").fetchall()
        return [dict(r) for r in rows]


def save_local_high_alerts(drugs: list[dict], added_by: str, added_at: str) -> None:
    with get_db() as conn:
        # Clear and replace
        conn.execute("DELETE FROM local_high_alert")
        for d in drugs:
            conn.execute(
                "INSERT INTO local_high_alert (drug_name, category, added_by, added_at) VALUES (?, ?, ?, ?)",
                (d.get("drug_name", ""), d.get("category", ""), added_by, added_at)
            )
