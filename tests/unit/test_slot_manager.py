"""tests/unit/test_slot_manager.py

Unit tests for SlotManager (Phase 7.2 - Partition & Slot Affinity).
Verifies:
1. Strict per-tenant slot pool isolation (acme in 0..7, borealis in 8..15).
2. Session pinning / slot affinity for repeated requests within the same session.
3. Intra-pool LRU eviction when pool is saturated.
4. Slot handover sanitization flag.
"""

import asyncio
import pytest
from app.orchestration.slot_manager import SlotManager


@pytest.mark.anyio
async def test_strict_per_tenant_pool_isolation():
    """Requirement: Acme only ever gets slots 0..7; Borealis only ever gets slots 8..15."""
    sm = SlotManager(total_slots=16)

    # 1. Allocate 8 sessions for Acme
    acme_slots = []
    for i in range(8):
        s = await sm.get_or_assign_slot(f"session_acme_{i}", tenant_id="acme")
        acme_slots.append(s)
        assert 0 <= s <= 7
        assert s not in range(8, 16)

    # All 8 acme slots should be unique across the 8 sessions
    assert len(set(acme_slots)) == 8

    # 2. Allocate 8 sessions for Borealis
    borealis_slots = []
    for i in range(8):
        s = await sm.get_or_assign_slot(f"session_borealis_{i}", tenant_id="borealis")
        borealis_slots.append(s)
        assert 8 <= s <= 15
        assert s not in range(0, 8)

    # All 8 borealis slots should be unique across the 8 sessions
    assert len(set(borealis_slots)) == 8

    # Disjoint check: intersection must be strictly empty
    assert set(acme_slots).isdisjoint(set(borealis_slots))


@pytest.mark.anyio
async def test_session_affinity_pinning():
    """Requirement: A session repeatedly receives the exact same slot ID."""
    sm = SlotManager(total_slots=16)

    slot_1 = await sm.get_or_assign_slot("session_alpha", "acme")
    slot_2 = await sm.get_or_assign_slot("session_beta", "acme")

    assert slot_1 != slot_2

    # Repeated requests for session_alpha return slot_1
    for _ in range(10):
        reused = await sm.get_or_assign_slot("session_alpha", "acme")
        assert reused == slot_1

    # Repeated requests for session_beta return slot_2
    for _ in range(10):
        reused = await sm.get_or_assign_slot("session_beta", "acme")
        assert reused == slot_2


@pytest.mark.anyio
async def test_intra_pool_lru_eviction():
    """Requirement: In a saturated pool, 9th session evicts the oldest idle session."""
    sm = SlotManager(total_slots=16)

    # Fill all 8 acme slots (0..7)
    for i in range(8):
        await sm.get_or_assign_slot(f"acme_user_{i}", "acme")

    # Access users 1..7 so user 0 is the least recently used
    for i in range(1, 8):
        await sm.get_or_assign_slot(f"acme_user_{i}", "acme")

    # 9th session: user 0 should be evicted and its slot reassigned
    slot_evicted = await sm.get_or_assign_slot("acme_user_9", "acme")
    assert 0 <= slot_evicted <= 7

    # Verify user 0 is no longer pinned
    assert "acme_user_0" not in sm.session_to_slot
    assert sm.session_to_slot["acme_user_9"] == slot_evicted

    # Verify sanitization flag is active on the reassigned slot
    assert sm.slots[slot_evicted].needs_sanitization is True
    # Sanitize
    sanitized = await sm.sanitize_slot_if_needed(slot_evicted)
    assert sanitized is True
    assert sm.slots[slot_evicted].needs_sanitization is False
