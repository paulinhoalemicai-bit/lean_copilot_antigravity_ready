from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path("leancopilot.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        project_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        state_json TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS drafts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id TEXT NOT NULL,
        tool TEXT NOT NULL,
        draft_json TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(project_id, tool)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS session_logs (
        session_id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        tool TEXT NOT NULL,
        event_type TEXT NOT NULL,
        user_delta TEXT,
        coach_payload TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()


def list_projects() -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT project_id, name, updated_at FROM projects ORDER BY updated_at DESC, created_at DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def upsert_project(project_id: str, name: str, state: Dict[str, Any]) -> None:
    conn = get_conn()
    cur = conn.cursor()
    state_json = json.dumps(state, ensure_ascii=False)

    cur.execute("""
    INSERT INTO projects (project_id, name, state_json, updated_at)
    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(project_id) DO UPDATE SET
        name=excluded.name,
        state_json=excluded.state_json,
        updated_at=CURRENT_TIMESTAMP
    """, (project_id, name, state_json))

    conn.commit()
    conn.close()


def get_project_state(project_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT state_json FROM projects WHERE project_id = ?", (project_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return json.loads(row["state_json"])


def save_draft(project_id: str, tool: str, payload: Dict[str, Any]) -> None:
    conn = get_conn()
    cur = conn.cursor()
    draft_json = json.dumps(payload, ensure_ascii=False)

    cur.execute("""
    INSERT INTO drafts (project_id, tool, draft_json, updated_at)
    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(project_id, tool) DO UPDATE SET
        draft_json=excluded.draft_json,
        updated_at=CURRENT_TIMESTAMP
    """, (project_id, tool, draft_json))

    conn.commit()
    conn.close()


def load_draft(project_id: str, tool: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT draft_json FROM drafts WHERE project_id = ? AND tool = ?", (project_id, tool))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return json.loads(row["draft_json"])


def add_session_log(
    session_id: str,
    project_id: str,
    tool: str,
    event_type: str,
    user_delta: str,
    coach_payload: Dict[str, Any],
) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO session_logs (session_id, project_id, tool, event_type, user_delta, coach_payload)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        session_id,
        project_id,
        tool,
        event_type,
        user_delta,
        json.dumps(coach_payload, ensure_ascii=False),
    ))
    conn.commit()
    conn.close()


def list_recent_sessions(project_id: str, limit: int = 6) -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    SELECT session_id, project_id, tool, event_type, user_delta, coach_payload, created_at
    FROM session_logs
    WHERE project_id = ?
    ORDER BY created_at DESC
    LIMIT ?
    """, (project_id, limit))
    rows = cur.fetchall()
    conn.close()

    out = []
    for r in rows:
        d = dict(r)
        d["coach"] = json.loads(d.pop("coach_payload") or "{}")
        out.append(d)
    return out
