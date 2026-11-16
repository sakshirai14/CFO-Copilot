#!/usr/bin/env python3
"""scripts/benchmark_decode_throughput_v2.py

Item 0.5 (a) & (b):
Re-measures aggregate decode throughput at n = 1, 2, 4, 8, 16 concurrent streams
with realistic prompts (~700 tokens) and outputs (~200 tokens), 5 repetitions each.
Reports median, min, max aggregate tokens/s across the 5 repetitions.
Recomputes utilization and expected queue wait at 16 sessions, 20s think time,
for 10%, 30%, 50%, and 100% LLM share using empirical mu(n).
"""

import asyncio
import json
import statistics
import time
from pathlib import Path
from typing import Any, Dict, List
import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = PROJECT_ROOT / "docs" / "evidence" / "step05_decode_throughput.json"
REPORT_MD = PROJECT_ROOT / "docs" / "evidence" / "step05_decode_throughput_report.md"

# Realistic financial prompt (~700 tokens) constructed from multiple 10-K disclosures
PROMPT_700_TOKENS = (
    "You are CFO Copilot, an expert financial analyst. Analyze the following verified SEC 10-K disclosures:\n\n"
    "[FACT 1 - Revenue Growth & Segments]\n"
    "Aurora Retail Group (ARG) reported total net sales of $3,245,600,000 for fiscal 2024, representing an increase of 6.8% "
    "compared to $3,038,950,000 in fiscal 2023. Comparable store sales increased 4.2%, driven by a 2.8% increase in average ticket "
    "and a 1.4% increase in transaction count. Digital channel sales grew 18.4% year-over-year, accounting for 28.5% of total net sales.\n\n"
    "[FACT 2 - Margins & Operating Costs]\n"
    "Gross profit reached $1,135,960,000, or 35.0% of net sales, expanding 120 basis points from 33.8% in fiscal 2023. "
    "The gross margin expansion reflected lower inbound freight rates (-85 bps) and favorable category mix shifts (-45 bps), "
    "partially offset by higher promotional discounts (+10 bps). Selling, general, and administrative (SG&A) expenses totaled "
    "$746,488,000, or 23.0% of net sales, compared to $698,958,500, or 23.0% of net sales in fiscal 2023. Increased store labor wage rates "
    "and performance-based incentive compensation were offset by corporate restructuring savings and corporate overhead discipline.\n\n"
    "[FACT 3 - Operating Income & EBITDA]\n"
    "Operating income rose 14.5% to $389,472,000 from $340,150,000 in fiscal 2023. Operating margin improved by 80 basis points to 12.0%. "
    "Depreciation and amortization expense was $142,300,000. Adjusted EBITDA increased 11.2% to $531,772,000, achieving an Adjusted "
    "EBITDA margin of 16.38%.\n\n"
    "[FACT 4 - Cash Flows & Capital Expenditures]\n"
    "Operating cash flow was $468,200,000, compared to $412,500,000 in the prior year, primarily reflecting stronger net earnings and working "
    "capital improvements in inventory turnover. Capital expenditures were $185,400,000, dedicated to opening 32 new stores, remodeling "
    "48 locations, and enhancing supply chain automation capabilities. Free cash flow was $282,800,000.\n\n"
    "[FACT 5 - Capital Structure & Balance Sheet]\n"
    "Total debt at fiscal year-end stood at $1,150,000,000, comprised of $800M in 4.5% senior notes due 2028 and $350M drawn under the revolving "
    "credit facility. Cash and cash equivalents totaled $320,000,000, yielding net debt of $830,000,000. Net debt to Adjusted EBITDA ratio "
    "improved to 1.56x from 1.85x.\n\n"
    "Provide a detailed, thorough four-paragraph executive narrative explaining: (1) key top-line and digital growth drivers, (2) the margin "
    "expansion dynamics including gross margin drivers and SG&A leverage, (3) cash conversion and capital expenditure deployment, and (4) "
    "balance sheet solvency and leverage ratios."
)

async def run_single_stream(client: httpx.AsyncClient, stream_id: int) -> Dict[str, Any]:
    t0 = time.perf_counter()
    resp = await client.post(
        "http://127.0.0.1:8080/v1/chat/completions",
        json={
            "model": "qwen2.5-3b-instruct",
            "messages": [
                {"role": "system", "content": "You are a detailed financial analyst. Provide thorough explanations."},
                {"role": "user", "content": f"{PROMPT_700_TOKENS}\n[Stream Request ID: {stream_id}]"}
            ],
            "max_tokens": 220,
            "temperature": 0.0
        },
        timeout=180.0
    )
    elapsed = time.perf_counter() - t0
    data = resp.json()
    usage = data.get("usage", {})
    comp_tokens = usage.get("completion_tokens", 0)
    prompt_tokens = usage.get("prompt_tokens", 0)
    timings = data.get("timings", {})
    predicted_per_sec = timings.get("predicted_per_second", 0.0)
    return {
        "stream_id": stream_id,
        "elapsed_sec": elapsed,
        "completion_tokens": comp_tokens,
        "prompt_tokens": prompt_tokens,
        "predicted_per_sec": predicted_per_sec,
    }

async def benchmark_concurrency_rep(n: int, rep: int) -> Dict[str, Any]:
    limits = httpx.Limits(max_keepalive_connections=32, max_connections=32)
    async with httpx.AsyncClient(limits=limits) as client:
        t0 = time.perf_counter()
        tasks = [run_single_stream(client, i) for i in range(n)]
        results = await asyncio.gather(*tasks)
        wall_time = time.perf_counter() - t0

    total_comp_tokens = sum(r["completion_tokens"] for r in results)
    avg_prompt_tokens = sum(r["prompt_tokens"] for r in results) / len(results)
    avg_comp_tokens = total_comp_tokens / len(results)
    # Aggregate decode tokens/s = total completion tokens generated / wall time
    agg_throughput = total_comp_tokens / wall_time

    return {
        "n": n,
        "rep": rep,
        "wall_time_sec": round(wall_time, 2),
        "total_completion_tokens": total_comp_tokens,
        "avg_prompt_tokens": round(avg_prompt_tokens, 1),
        "avg_completion_tokens": round(avg_comp_tokens, 1),
        "aggregate_tokens_per_sec": round(agg_throughput, 2)
    }

async def main():
    print("=" * 90)
    print("ITEM 0.5 (a): RE-MEASURING DECODE THROUGHPUT AT n=1, 2, 4, 8, 16 (5 reps each)")
    print("Prompt: ~700 tokens | Output: ~200 tokens")
    print("=" * 90)

    concurrency_levels = [1, 2, 4, 8, 16]
    reps = 5
    summary_by_n = {}

    for n in concurrency_levels:
        print(f"\n--- Testing Concurrency n = {n} (5 repetitions) ---")
        rep_results = []
        for r in range(1, reps + 1):
            res = await benchmark_concurrency_rep(n, r)
            rep_results.append(res)
            print(f"  Rep {r}: {res['aggregate_tokens_per_sec']:.2f} tok/s (wall: {res['wall_time_sec']:.2f}s, tok: {res['total_completion_tokens']})")

        throughputs = [x["aggregate_tokens_per_sec"] for x in rep_results]
        summary_by_n[n] = {
            "n": n,
            "median_tokens_per_sec": round(statistics.median(throughputs), 2),
            "min_tokens_per_sec": round(min(throughputs), 2),
            "max_tokens_per_sec": round(max(throughputs), 2),
            "mean_tokens_per_sec": round(statistics.mean(throughputs), 2),
            "avg_prompt_tokens": rep_results[0]["avg_prompt_tokens"],
            "avg_completion_tokens": rep_results[0]["avg_completion_tokens"],
            "raw_reps": rep_results
        }

    # Item 0.5 (b): Utilization & Queue Wait at 16 sessions, 20s think time
    # User arrival rate: 16 sessions with 20s think time
    # Average request generation: 200 tokens
    # mu(n) = median aggregate throughput / avg_completion_tokens (requests/sec)
    print("\n" + "=" * 90)
    print("ITEM 0.5 (b): QUEUE WAIT & UTILIZATION AT 16 SESSIONS, 20s THINK TIME")
    print("=" * 90)

    # Use n=16 throughput for peak capacity mu
    mu_16_tok = summary_by_n[16]["median_tokens_per_sec"]
    avg_tokens_per_req = summary_by_n[16]["avg_completion_tokens"]
    mu_req_per_sec = mu_16_tok / avg_tokens_per_req # requests / sec capacity

    think_time = 20.0
    # Closed network arrival rate: Lambda = 16 / (think_time + avg_latency)
    # Approx Lambda_total = 16 / 20 = 0.8 req/sec
    lambda_total = 16.0 / think_time # 0.80 req/s

    queue_table = []
    shares = [0.10, 0.30, 0.50, 1.00]
    for s in shares:
        lambda_llm = lambda_total * s
        rho = lambda_llm / mu_req_per_sec
        # M/M/1 queue wait approximation: W_q = rho / (mu * (1 - rho)) if rho < 1 else Inf
        if rho < 0.999:
            w_q_sec = rho / (mu_req_per_sec * (1.0 - rho))
        else:
            w_q_sec = float("inf")

        queue_table.append({
            "llm_share_pct": int(s * 100),
            "lambda_llm_req_s": round(lambda_llm, 3),
            "mu_capacity_req_s": round(mu_req_per_sec, 3),
            "utilization_rho": round(rho, 4),
            "utilization_pct": round(rho * 100, 2),
            "expected_queue_wait_sec": round(w_q_sec, 3) if w_q_sec != float("inf") else "INF (Over capacity)"
        })

    # Save results
    payload = {
        "decode_throughput_scaling": summary_by_n,
        "queue_wait_analysis": queue_table,
        "parameters": {
            "prompt_length_tokens": summary_by_n[16]["avg_prompt_tokens"],
            "output_length_tokens": avg_tokens_per_req,
            "sessions": 16,
            "think_time_sec": think_time,
            "mu_16_tokens_per_sec": mu_16_tok,
            "mu_16_req_per_sec": round(mu_req_per_sec, 3)
        }
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"\n[OK] Results saved to {OUTPUT_FILE}")

    # Print summary table
    print("\nAGGREGATE DECODE THROUGHPUT TABLE:")
    print(f"{'n (streams)':<12} | {'Median tok/s':<14} | {'Min tok/s':<12} | {'Max tok/s':<12} | {'Prompt Tok':<12} | {'Comp Tok':<10}")
    print("-" * 80)
    for n in concurrency_levels:
        s = summary_by_n[n]
        print(f"{n:<12} | {s['median_tokens_per_sec']:<14.2f} | {s['min_tokens_per_sec']:<12.2f} | {s['max_tokens_per_sec']:<12.2f} | {s['avg_prompt_tokens']:<12.1f} | {s['avg_completion_tokens']:<10.1f}")

    print("\nQUEUE WAIT & UTILIZATION AT 16 SESSIONS (20s Think Time):")
    print(f"{'LLM Share':<12} | {'Lambda (req/s)':<16} | {'Mu (req/s)':<12} | {'Rho (%)':<10} | {'Expected W_q (s)':<18}")
    print("-" * 75)
    for q in queue_table:
        print(f"{q['llm_share_pct']}%{'':<9} | {q['lambda_llm_req_s']:<16.3f} | {q['mu_capacity_req_s']:<12.3f} | {q['utilization_pct']:<10.1f} | {q['expected_queue_wait_sec']}")

if __name__ == "__main__":
    asyncio.run(main())

