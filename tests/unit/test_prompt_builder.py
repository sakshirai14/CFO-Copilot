"""tests/unit/test_prompt_builder.py

Unit tests for PromptBuilder enforcing the 7-layer Prefix Layout Contract (Phase 7.1).
Tests:
1. Static-part hash is byte-identical across 100 random requests.
2. Permuting input tool order produces identical bytes and identical SHA-256.
3. No timestamp (HH:MM:SS) or request-id pattern anywhere in the static prompt.
4. Conversation history is an exact byte-prefix of subsequent turns until a hysteresis jump.
5. The static part contains strictly ZERO tenant names, user names, or company names.
"""

import random
import re
import pytest
from app.domain.prompt_builder import PromptBuilder, DEFAULT_CANONICAL_TOOLS
from app.domain.agent_envelope import FactItem


def test_static_part_hash_identical_across_100_requests():
    """Requirement 1: Static prefix hash is 100% invariant across 100 diverse requests."""
    tenants = ["acme", "borealis", "zenith"]
    users = ["user_1", "user_2", "alice", "bob"]
    questions = [
        "What was gross margin?",
        "Compare revenue between Q1 and Q2.",
        "Explain supply chain headwinds in Note 8.",
        "Provide EBITDA and debt ratios."
    ]

    base_prompt = PromptBuilder.build_prompt(
        question="Initial test question",
        retrieved_facts=[],
        tenant_id="acme",
        user_id="user_init"
    )
    expected_hash = base_prompt.static_sha256

    for _ in range(100):
        t = random.choice(tenants)
        u = random.choice(users)
        q = random.choice(questions)
        facts = [
            FactItem(fact_id=f"fact_{i}", text=f"Factual statement number {i}")
            for i in range(random.randint(0, 5))
        ]
        built = PromptBuilder.build_prompt(
            question=q,
            retrieved_facts=facts,
            tenant_id=t,
            user_id=u
        )
        assert built.static_sha256 == expected_hash
        assert built.static_prefix == base_prompt.static_prefix


def test_permuting_tool_order_invariant_bytes():
    """Requirement 2: Permuting input tool order does not change output bytes or hash."""
    shuffled_tools = list(DEFAULT_CANONICAL_TOOLS)
    random.shuffle(shuffled_tools)

    b1 = PromptBuilder.build_prompt("Question 1", [], "acme", tools=DEFAULT_CANONICAL_TOOLS)
    b2 = PromptBuilder.build_prompt("Question 1", [], "acme", tools=shuffled_tools)

    assert b1.static_prefix == b2.static_prefix
    assert b1.static_sha256 == b2.static_sha256


def test_no_timestamp_or_request_id_in_static_prompt():
    """Requirement 3: No timestamp (HH:MM:SS) or request-id pattern above boundary."""
    built = PromptBuilder.build_prompt("What was revenue?", [], "acme", user_id="cfo_user")

    # Static prefix must not contain clock time
    clock_pattern = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b")
    assert not clock_pattern.search(built.static_prefix)

    # Static prefix must not contain request_id patterns
    req_pattern = re.compile(r"request[_\-\s]?id|req-[a-z0-9]+", re.IGNORECASE)
    assert not req_pattern.search(built.static_prefix)


def test_conversation_history_byte_prefix_until_hysteresis():
    """Requirement 4: History is an exact byte-prefix until turn 9 triggers hysteresis."""
    history = []
    built_prompts = []

    # Turns 1 through 8: Each turn added preserves strict prefix property
    for i in range(1, 9):
        history.append({"role": "user", "content": f"Turn {i} question and verified content"})
        b = PromptBuilder.build_prompt(
            question=f"Turn {i+1} query",
            retrieved_facts=[],
            tenant_id="acme",
            conversation_history=history
        )
        built_prompts.append(b)

    # Verify that each history string is a strict prefix of the next history string (turns 1..8)
    for i in range(len(built_prompts) - 1):
        curr_hist = built_prompts[i].tenant_context
        next_hist = built_prompts[i+1].tenant_context
        assert next_hist.startswith(curr_hist)

    # Turn 9 triggers hysteresis drop (drops oldest 4 turns)
    history.append({"role": "user", "content": "Turn 9 question"})
    b_turn9 = PromptBuilder.build_prompt(
        question="Turn 10 query",
        retrieved_facts=[],
        tenant_id="acme",
        conversation_history=history
    )
    # Turn 1 should no longer be present in turn 9's context
    assert "Turn 1 question" not in b_turn9.tenant_context
    assert "Turn 5 question" in b_turn9.tenant_context


def test_static_part_contains_zero_tenant_user_or_company_names():
    """Requirement 5: Static prefix contains strictly ZERO tenant/user/company names."""
    built = PromptBuilder.build_prompt(
        question="Query for ARG in FY2024",
        retrieved_facts=[],
        tenant_id="borealis",
        user_id="analyst_alexander"
    )

    static = built.static_prefix.lower()

    # Assert zero tenant tokens
    assert "borealis" not in static
    assert "acme" not in static

    # Assert zero user tokens
    assert "alexander" not in static

    # Assert zero company names or tickers
    for company in ["arg", "aurora", "cep", "cobalt", "hbs", "helix", "msi", "meridian", "nwi", "northwind", "zlg", "zephyr"]:
        assert f" {company} " not in static
