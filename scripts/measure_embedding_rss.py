#!/usr/bin/env python3
"""scripts/measure_embedding_rss.py

Phase 4 Step 0 (e): Separate-process model RSS benchmark.
Measures the true resident set size (RSS) of BAAI/bge-small-en-v1.5 vs
sentence-transformers/all-MiniLM-L6-v2 in isolated subprocesses.
Uses standard resource.getrusage without external dependencies.
"""

import json
import os
import resource
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

WORKER_CODE = """
import json
import os
import sys
import time
import resource
from fastembed import TextEmbedding

model_name = sys.argv[1]

def get_current_max_rss_mb():
    usage = resource.getrusage(resource.RUSAGE_SELF)
    # On macOS, ru_maxrss is in bytes; on Linux, in kilobytes
    if sys.platform == "darwin":
        return usage.ru_maxrss / (1024 * 1024)
    return usage.ru_maxrss / 1024

rss_initial = get_current_max_rss_mb()

t0 = time.perf_counter()
model = TextEmbedding(model_name=model_name)
load_time_s = time.perf_counter() - t0

rss_after_load = get_current_max_rss_mb()

# Run inference on financial text
sample_query = "What was Aurora Retail Group's operating margin in fiscal 2024 quarter 1?"
t1 = time.perf_counter()
embeddings = list(model.embed([sample_query]))
infer_time_ms = (time.perf_counter() - t1) * 1000.0

dim = len(embeddings[0])
rss_peak = get_current_max_rss_mb()

result = {
    "model_name": model_name,
    "dimension": dim,
    "initial_rss_mb": round(rss_initial, 2),
    "model_load_time_s": round(load_time_s, 3),
    "loaded_rss_mb": round(rss_after_load, 2),
    "peak_rss_mb": round(rss_peak, 2),
    "net_rss_mb": round(rss_peak - rss_initial, 2),
    "infer_latency_ms": round(infer_time_ms, 2)
}

print(json.dumps(result))
"""

def benchmark_model(model_name: str) -> dict:
    venv_python = str(PROJECT_ROOT / ".venv" / "bin" / "python")
    cmd = [venv_python, "-c", WORKER_CODE, model_name]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        print(f"Subprocess stderr:\n{res.stderr}", file=sys.stderr)
        raise RuntimeError(f"Subprocess failed with code {res.returncode}")
    for line in res.stdout.strip().split("\n"):
        if line.startswith("{"):
            return json.loads(line)
    raise RuntimeError(f"Failed to parse worker output: {res.stdout}\nStderr: {res.stderr}")

def main():
    print("================================================================================")
    print("SEPARATE-PROCESS EMBEDDING MODEL RESIDENT MEMORY BENCHMARK (STEP 0e)")
    print("================================================================================")
    
    models = [
        "BAAI/bge-small-en-v1.5",
        "sentence-transformers/all-MiniLM-L6-v2"
    ]
    
    results = []
    print(f"{'Model':<40} | {'Dim':<5} | {'Load(s)':<8} | {'Peak RSS':<10} | {'Latency':<10}")
    print("-" * 80)
    
    for m in models:
        stats = benchmark_model(m)
        results.append(stats)
        print(f"{stats['model_name']:<40} | {stats['dimension']:<5} | {stats['model_load_time_s']:<8.2f} | {stats['peak_rss_mb']:<7.1f} MB | {stats['infer_latency_ms']:<6.2f} ms")
        
    out_path = PROJECT_ROOT / "benchmarks" / "results" / "embedding_model_rss.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print("-" * 80)
    print(f"[OK] Saved separate-process benchmark results to {out_path}")

if __name__ == "__main__":
    main()
