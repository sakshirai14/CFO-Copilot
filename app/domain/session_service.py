"""app/domain/session_service.py

Domain Service for Session Persistence, Chat History, and Audit Logging.
Enforces Foundation Lock 6 (Tenant isolation via RLS and transaction settings)
and Foundation Lock 8 (Reproducibility & Immutable Audit Logging).
"""

import datetime
import json
import uuid
from typing import Any, Dict, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from app.core.config import get_settings
from app.data.provenance import get_provenance_trace


class SessionService:
    """Manages chat sessions, messages, and answer audit logs."""

    def __init__(self, is_test: bool = False):
        self.is_test = is_test
        self.settings = get_settings()

    def _get_connection(self, tenant_id: str, role: str = "rw"):
        params = self.settings.get_connection_params(role=role, is_test=self.is_test)
        conn = psycopg2.connect(**params)
        # Enforce tenant isolation via session setting
        with conn.cursor() as cur:
            cur.execute("SET LOCAL app.current_tenant = %s;", (tenant_id,))
        return conn

    def check_db_health(self) -> bool:
        """Checks if the PostgreSQL database is reachable and accepting queries."""
        try:
            conn = self._get_connection("acme", role="ro")
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
            conn.close()
            return True
        except Exception:
            return False

    def create_session(self, tenant_id: str, title: Optional[str] = None) -> Dict[str, Any]:
        """Creates a new isolated chat session for the tenant."""
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        title_text = title or f"Session {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M')}"
        now = datetime.datetime.now(datetime.timezone.utc)

        conn = self._get_connection(tenant_id, role="rw")
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO chat_sessions (session_id, tenant_id, user_id, title, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING session_id, tenant_id, title, created_at;
                    """,
                    (session_id, tenant_id, f"user_{tenant_id}", title_text, now, now)
                )
                row = cur.fetchone()
                conn.commit()
                return {
                    "session_id": row[0],
                    "tenant_id": row[1],
                    "title": row[2],
                    "created_at": row[3].isoformat()
                }
        finally:
            conn.close()

    def list_sessions(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Lists all chat sessions belonging strictly to the authenticated tenant."""
        conn = self._get_connection(tenant_id, role="ro")
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT session_id, tenant_id, title, created_at, updated_at
                    FROM chat_sessions
                    WHERE tenant_id = %s
                    ORDER BY updated_at DESC;
                    """,
                    (tenant_id,)
                )
                rows = cur.fetchall()
                return [
                    {
                        "session_id": r["session_id"],
                        "tenant_id": r["tenant_id"],
                        "title": r["title"],
                        "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                        "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
                    }
                    for r in rows
                ]
        finally:
            conn.close()

    def get_session_messages(self, tenant_id: str, session_id: str) -> List[Dict[str, Any]]:
        """Retrieves conversation history for a session."""
        conn = self._get_connection(tenant_id, role="ro")
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT message_id, session_id, tenant_id, role, content, resolved_slots, created_at
                    FROM chat_messages
                    WHERE tenant_id = %s AND session_id = %s
                    ORDER BY created_at ASC;
                    """,
                    (tenant_id, session_id)
                )
                rows = cur.fetchall()
                return [
                    {
                        "message_id": r["message_id"],
                        "session_id": r["session_id"],
                        "role": r["role"],
                        "content": r["content"],
                        "resolved_slots": r["resolved_slots"],
                        "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                    }
                    for r in rows
                ]
        finally:
            conn.close()

    def get_last_resolved_slots(self, tenant_id: str, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves resolved slots from the most recent user turn to support multi-turn inheritance."""
        conn = self._get_connection(tenant_id, role="ro")
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT resolved_slots
                    FROM chat_messages
                    WHERE tenant_id = %s AND session_id = %s AND resolved_slots IS NOT NULL AND resolved_slots != '{}'::jsonb
                    ORDER BY created_at DESC
                    LIMIT 1;
                    """,
                    (tenant_id, session_id)
                )
                row = cur.fetchone()
                return row[0] if row else None
        finally:
            conn.close()

    def save_turn(
        self,
        tenant_id: str,
        session_id: Optional[str],
        user_message: str,
        assistant_message: str,
        resolved_slots: Optional[Dict[str, Any]] = None,
        envelope_data: Optional[Dict[str, Any]] = None,
        log_meta: Optional[Dict[str, Any]] = None
    ):
        """Atomically saves the user message, assistant answer, and immutable answer_log record."""
        conn = self._get_connection(tenant_id, role="rw")
        now = datetime.datetime.now(datetime.timezone.utc)
        target_session_id = session_id or f"sess_adhoc_{uuid.uuid4().hex[:10]}"
        u_msg_id = f"msg_{uuid.uuid4().hex[:10]}"
        a_msg_id = f"msg_{uuid.uuid4().hex[:10]}"

        try:
            with conn.cursor() as cur:
                # 1. Ensure session exists in chat_sessions
                cur.execute(
                    """
                    INSERT INTO chat_sessions (session_id, tenant_id, user_id, title, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (session_id) DO UPDATE SET updated_at = EXCLUDED.updated_at;
                    """,
                    (target_session_id, tenant_id, f"user_{tenant_id}", user_message[:60], now, now)
                )

                # 2. Insert user message with resolved slots
                cur.execute(
                    """
                    INSERT INTO chat_messages (message_id, session_id, tenant_id, role, content, resolved_slots, created_at)
                    VALUES (%s, %s, %s, 'user', %s, %s, %s);
                    """,
                    (u_msg_id, target_session_id, tenant_id, user_message, json.dumps(resolved_slots or {}), now)
                )

                # 3. Insert assistant response
                cur.execute(
                    """
                    INSERT INTO chat_messages (message_id, session_id, tenant_id, role, content, resolved_slots, created_at)
                    VALUES (%s, %s, %s, 'assistant', %s, %s, %s);
                    """,
                    (a_msg_id, target_session_id, tenant_id, assistant_message, json.dumps(resolved_slots or {}), now)
                )

                # 4. Insert into immutable answer_log
                meta = log_meta or {}
                cur.execute(
                    """
                    INSERT INTO answer_log (
                        request_id, session_id, tenant_id, user_query, routed_to,
                        model_version, prompt_template_hash, answer_text,
                        ttft_ms, total_time_ms, prompt_tokens, completion_tokens,
                        cached_tokens, retrieval_snapshot, facts, tool_calls,
                        llm_calls, policy_version, degraded, degraded_reason,
                        timings, envelope, created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s
                    );
                    """,
                    (
                        meta.get("request_id"),
                        target_session_id,
                        tenant_id,
                        user_message,
                        meta.get("routed_to", "STRUCTURED"),
                        meta.get("model_version", "qwen2.5-3b-instruct"),
                        meta.get("prompt_template_hash", "frozen_prompt_v1"),
                        assistant_message,
                        meta.get("ttft_ms", 0.0),
                        meta.get("total_time_ms", 0.0),
                        meta.get("prompt_tokens", 0),
                        meta.get("completion_tokens", 0),
                        meta.get("cached_tokens", 0),
                        json.dumps(meta.get("retrieval_snapshot") or {}),
                        json.dumps(meta.get("facts") or []),
                        json.dumps(meta.get("tool_calls") or []),
                        meta.get("llm_calls", 0),
                        meta.get("policy_version", "v1.2.0"),
                        meta.get("degraded", False),
                        meta.get("degraded_reason"),
                        json.dumps(meta.get("timings") or {}),
                        json.dumps(envelope_data or {}),
                        now
                    )
                )
                conn.commit()
        finally:
            conn.close()

    def get_kpi_definitions(self) -> List[Dict[str, Any]]:
        """Returns the canonical catalog of all 16 supported financial KPIs."""
        conn = self._get_connection("acme", role="ro")
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT kpi_id, kpi_name, formula, unit, notes
                    FROM kpi_definitions
                    ORDER BY kpi_id;
                    """
                )
                return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def get_provenance(self, kpi_value_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves forensic audit provenance for a specific calculated KPI value."""
        conn = self._get_connection("acme", role="ro")
        try:
            return get_provenance_trace(conn, kpi_value_id=kpi_value_id)
        finally:
            conn.close()
