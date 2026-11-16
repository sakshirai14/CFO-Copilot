#!/usr/bin/env python3
"""scripts/replay.py

Reproducibility Replay Harness for Foundation Lock Black Box.
Reloads stored query parameters, facts, retrieval snapshot ID, prompt hash,
and model hash from answer_log, re-executes the synthesis pipeline, and computes
exact-match diffs.
"""

import argparse
import difflib
import json
import sys
import time
from typing import Any, Dict, List, Optional
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2
from psycopg2.extras import RealDictCursor

from app.agents.answer_writer import AnswerWriterAgent
from app.domain.question_resolver import QuestionResolver
from app.core.config import get_settings
from app.domain.agent_envelope import FactItem, ResolvedQuery, RouteType
from app.domain.answer_composer import AnswerComposer

CURRENT_MODEL_VERSION = "626b4a6678b86442240e33df819e00132d3ba7dddfe1cdc4fbb18e0a9615c62d"
CURRENT_PROMPT_TEMPLATE_HASH = "dd4a4ded237acf238396237ca7e87b98ad5213a9550085c1451d604580db1f8e"
CURRENT_LAYOUT_VERSION = "v1.0"


def get_db_connection():
    settings = get_settings()
    params = settings.get_connection_params(role="ro")
    return psycopg2.connect(**params)


def load_logged_request(conn, request_id: str, tenant_id: str = "acme") -> Optional[Dict[str, Any]]:
    """Loads audit record from answer_log by request_id."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SET LOCAL app.current_tenant = %s;", (tenant_id,))
        cur.execute(
            """
            SELECT request_id, session_id, tenant_id, user_query, routed_to,
                   model_version, prompt_template_hash, answer_text,
                   ttft_ms, total_time_ms, facts, retrieval_snapshot,
                   tool_calls, llm_calls, policy_version, degraded, degraded_reason
            FROM answer_log
            WHERE request_id = %s;
            """,
            (request_id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None


def load_recent_requests(conn, limit: int = 20, tenant_id: str = "acme") -> List[Dict[str, Any]]:
    """Loads the most recent N records from answer_log."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SET LOCAL app.current_tenant = %s;", (tenant_id,))
        cur.execute(
            """
            SELECT request_id, session_id, tenant_id, user_query, routed_to,
                   model_version, prompt_template_hash, answer_text,
                   ttft_ms, total_time_ms, facts, retrieval_snapshot,
                   tool_calls, llm_calls, policy_version, degraded, degraded_reason
            FROM answer_log
            ORDER BY created_at DESC
            LIMIT %s;
            """,
            (limit,)
        )
        return [dict(r) for r in cur.fetchall()]


def replay_request(record: Dict[str, Any]) -> Dict[str, Any]:
    """Replays a single logged request deterministically."""
    req_id = record["request_id"]
    stored_model = record.get("model_version")
    stored_prompt_hash = record.get("prompt_template_hash")
    stored_answer = record.get("answer_text", "")
    routed_to = record.get("routed_to", "STRUCTURED")
    user_query = record.get("user_query", "")

    # 1. Enforce Hash Integrity Gates (Foundation Lock Black Box)
    if stored_model and stored_model != CURRENT_MODEL_VERSION:
        return {
            "request_id": req_id,
            "replayed": False,
            "refusal_reason": f"Model hash mismatch: stored '{stored_model}' vs current '{CURRENT_MODEL_VERSION}'",
            "exact_match": False,
            "diff": ""
        }

    if stored_prompt_hash and stored_prompt_hash != CURRENT_PROMPT_TEMPLATE_HASH:
        return {
            "request_id": req_id,
            "replayed": False,
            "refusal_reason": f"Prompt template hash mismatch: stored '{stored_prompt_hash}' vs current '{CURRENT_PROMPT_TEMPLATE_HASH}'",
            "exact_match": False,
            "diff": ""
        }

    # 2. Re-resolve query slots
    resolved_query: ResolvedQuery = QuestionResolver.resolve(user_query)

    # 3. Parse stored facts
    raw_facts = record.get("facts")
    if isinstance(raw_facts, str):
        raw_facts = json.loads(raw_facts)
    facts_list = [FactItem(**f) for f in (raw_facts or [])]

    # 4. Deterministic Replay Execution
    replayed_answer = ""
    if routed_to == RouteType.STRUCTURED.value:
        replayed_answer = AnswerComposer.compose_structured_answer(resolved_query, facts_list)
    elif routed_to == RouteType.REFUSAL.value:
        replayed_answer = AnswerComposer.compose_refusal_answer(resolved_query)
    elif routed_to == RouteType.CHITCHAT.value:
        replayed_answer = AnswerComposer.compose_chitchat_answer()
    else:
        # Qualitative / Mixed
        if record.get("degraded"):
            replayed_answer = AnswerComposer.compose_fallback_answer(facts_list, resolved_query)
        else:
            # Deterministic AnswerWriter invocation with temperature 0
            writer = AnswerWriterAgent()
            import asyncio
            payload = asyncio.run(writer.write_answer(user_query, facts_list, []))
            cand_ans = payload.get("answer", "")
            cand_status = payload.get("status", "ok")
            has_relevant = any(bool(f.text and f.text.strip()) for f in facts_list)
            if (cand_status in ("refused", "insufficient_data", "unsupported") or cand_ans.strip().startswith("Refused:")) and has_relevant:
                replayed_answer = AnswerComposer.compose_fallback_answer(facts_list, resolved_query)
            else:
                replayed_answer = cand_ans

    # 5. Diff Computation
    clean_stored = stored_answer.strip()
    clean_replayed = replayed_answer.strip()
    exact_match = (clean_stored == clean_replayed)

    diff_text = ""
    if not exact_match:
        diff_lines = list(difflib.unified_diff(
            clean_stored.splitlines(keepends=True),
            clean_replayed.splitlines(keepends=True),
            fromfile="stored_answer",
            tofile="replayed_answer"
        ))
        diff_text = "".join(diff_lines)

    return {
        "request_id": req_id,
        "replayed": True,
        "exact_match": exact_match,
        "stored_answer": clean_stored,
        "replayed_answer": clean_replayed,
        "diff": diff_text
    }


def main():
    parser = argparse.ArgumentParser(description="Replay CFO Copilot requests from answer_log")
    parser.add_argument("request_id", nargs="?", help="Specific request ID to replay")
    parser.add_argument("--batch", type=int, default=0, help="Replay latest N requests")
    args = parser.parse_args()

    conn = get_db_connection()
    try:
        if args.request_id:
            record = load_logged_request(conn, args.request_id)
            if not record:
                print(f"Error: Request '{args.request_id}' not found in answer_log.", file=sys.stderr)
                sys.exit(1)
            res = replay_request(record)
            print(f"=== Replay Result for {args.request_id} ===")
            print(f"Replayed: {res['replayed']}")
            if not res["replayed"]:
                print(f"Refusal: {res['refusal_reason']}")
                sys.exit(2)
            print(f"Exact Match: {res['exact_match']}")
            if not res["exact_match"]:
                print("\nDiff:\n" + res["diff"])
            else:
                print(f"Answer: {res['replayed_answer']}")
        else:
            limit = args.batch or 20
            records = load_recent_requests(conn, limit=limit)
            if not records:
                print(f"No records found in answer_log to replay.")
                sys.exit(0)

            print(f"=== Replaying {len(records)} Requests from answer_log ===")
            route_stats: Dict[str, Dict[str, int]] = {}
            mismatches: List[Dict[str, Any]] = []

            for idx, r in enumerate(records, 1):
                route = r.get("routed_to", "UNKNOWN")
                if route not in route_stats:
                    route_stats[route] = {"total": 0, "match": 0, "mismatch": 0, "refused": 0}
                route_stats[route]["total"] += 1

                res = replay_request(r)
                if not res["replayed"]:
                    status_str = "HASH_MISMATCH"
                    route_stats[route]["refused"] += 1
                    mismatches.append({
                        "request_id": r["request_id"],
                        "route": route,
                        "cause": res["refusal_reason"]
                    })
                elif res["exact_match"]:
                    status_str = "MATCH"
                    route_stats[route]["match"] += 1
                else:
                    status_str = "CONTENT_MISMATCH"
                    route_stats[route]["mismatch"] += 1
                    mismatches.append({
                        "request_id": r["request_id"],
                        "route": route,
                        "cause": f"Content diff: {res['diff'][:120]}"
                    })

                print(f"[{idx:02d}/{len(records)}] {r['request_id']} ({route}): {status_str}")
                if not res["replayed"]:
                    print(f"     Cause: {res['refusal_reason']}")
                elif not res["exact_match"] and res["diff"]:
                    print("     " + res["diff"].replace("\n", "\n     "))

            total_matches = sum(s["match"] for s in route_stats.values())
            print("\n--- Per-Route Exact-Match Summary ---")
            for route, s in sorted(route_stats.items()):
                print(f"Route '{route}': Total {s['total']} | Match: {s['match']} | Content Mismatch: {s['mismatch']} | Hash Mismatch: {s['refused']}")

            rate = (total_matches / len(records)) * 100.0 if records else 0.0
            print(f"\nTotal Tested: {len(records)} | Exact Matches: {total_matches} | Match Rate: {rate:.1f}%")
            if mismatches:
                print("\n--- Detailed Mismatches & Causes ---")
                for m in mismatches:
                    print(f"- {m['request_id']} ({m['route']}): {m['cause']}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
