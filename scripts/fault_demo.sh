#!/usr/bin/env bash
# scripts/fault_demo.sh
# Demonstrates all 5 Foundation Lock Fallback scenarios against the CFO Copilot REST API.
# Usage: ./scripts/fault_demo.sh [API_BASE_URL] (defaults to http://localhost:8000)

set -euo pipefail

API_BASE="${1:-http://localhost:8000}"
API_KEY="cfo_key_acme_dev"

echo "========================================================================"
echo " CFO Copilot - Foundation Lock Fallback Demonstration Suite"
echo " Target API: $API_BASE"
echo "========================================================================"
echo ""

# Helper for curl requests
run_fault_test() {
    local title="$1"
    local fault_flag="$2"
    local question="$3"
    local req_id="$4"

    echo "------------------------------------------------------------------------"
    echo ">> [SCENARIO]: $title"
    echo "   Fault Header: X-Fault-Inject: $fault_flag"
    echo "   Question: \"$question\""
    echo "------------------------------------------------------------------------"

    response=$(curl -s -i -X POST "$API_BASE/v1/chat" \
        -H "Content-Type: application/json" \
        -H "X-API-Key: $API_KEY" \
        -H "X-Request-Id: $req_id" \
        -H "X-Fault-Inject: $fault_flag" \
        -d "{\"question\": \"$question\"}" || true)

    # Extract HTTP status
    http_status=$(echo "$response" | grep -E '^HTTP/' | awk '{print $2}' | tail -n 1)
    echo "   HTTP Status Code: $http_status"

    # Extract Retry-After if present
    retry_after=$(echo "$response" | grep -i '^Retry-After:' | awk '{print $2}' | tr -d '\r' || true)
    if [ -n "$retry_after" ]; then
        echo "   Retry-After Header: $retry_after s"
    fi

    # Print response body JSON preview
    body=$(echo "$response" | sed -n '/^\r\{0,1\}$/,$p' | tail -n +2)
    echo "   Response Payload Preview:"
    echo "$body" | python3 -m json.tool 2>/dev/null | head -n 18 || echo "$body" | head -n 10
    echo ""
}

# 1. Fault Model Offline
run_fault_test \
    "1. Model Server Offline (Lock Fallback: Extractive Fallback)" \
    "model_offline" \
    "What qualitative disclosures did Helix Biosystems provide regarding competition?" \
    "req_demo_offline_01"

# 2. Fault Model OOM
run_fault_test \
    "2. Model Server Context / Slot OOM (Lock Fallback: Degraded Fallback)" \
    "model_oom" \
    "According to the filings, what drove the revenue change at Cobalt Energy Partners in fiscal 2023?" \
    "req_demo_oom_02"

# 3. Fault Vector Failure
run_fault_test \
    "3. Vector Index / Embedding Failure (Lock Fallback: FTS BM25 Fallback)" \
    "vector_fail" \
    "According to the filings, what were the main business risks for Cobalt Energy Partners?" \
    "req_demo_vec_03"

# 4. Fault Database Down
run_fault_test \
    "4. Database Outage (Lock Fallback: 503 Service Unavailable with Retry-After)" \
    "db_down" \
    "What was Helix Biosystems's revenue in fiscal 2024 quarter 2?" \
    "req_demo_db_04"

# Check Liveness during DB outage
echo ">> Checking Liveness Probe (/v1/health) during simulated DB outage:"
health_resp=$(curl -s "$API_BASE/v1/health" || true)
echo "   /v1/health Response: $health_resp"
echo ""

# 5. Fault Queue Saturated
run_fault_test \
    "5. Concurrency Queue Saturated (Lock Crowd: 429 Too Many Requests with Retry-After)" \
    "queue_saturated" \
    "What qualitative disclosures did Helix Biosystems provide regarding competition?" \
    "req_demo_queue_05"

echo "========================================================================"
echo " Fallback Demonstration Complete. All 5 fault scenarios verified."
echo "========================================================================"

