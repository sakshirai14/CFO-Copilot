-- migrations/008_chat_message_slots.sql
-- Schema extensions for Phase 6 API & Orchestration:
-- 1. resolved_slots on chat_messages for server-side multi-turn context
-- 2. metadata extensions on answer_log for comprehensive request auditing

ALTER TABLE chat_messages
  ADD COLUMN IF NOT EXISTS resolved_slots JSONB DEFAULT '{}'::jsonb;

ALTER TABLE answer_log
  ADD COLUMN IF NOT EXISTS facts JSONB DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS tool_calls JSONB DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS llm_calls INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS policy_version VARCHAR(32) DEFAULT 'v1.2.0',
  ADD COLUMN IF NOT EXISTS degraded BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS degraded_reason TEXT,
  ADD COLUMN IF NOT EXISTS timings JSONB DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS envelope JSONB DEFAULT '{}'::jsonb;

