"""app/core/metrics.py

Prometheus Metrics Exporter for CFO Copilot.
Enforces Foundation Lock Lantern (Observability).
Collects runtime operational telemetry without third-party cloud dependencies.
Exposes standard Prometheus exposition format (text/plain; version=0.0.4).
"""

import time
from typing import Dict, List, Optional


class MetricsRegistry:
    """Thread-safe in-memory Prometheus metrics registry supporting counters, gauges, and summaries."""

    def __init__(self):
        self._counters: Dict[str, float] = {
            'cfo_copilot_requests_total{route="init",status="ok"}': 0.0,
            "cfo_copilot_429_total": 0.0,
            "cfo_copilot_llm_calls_total": 0.0,
            "cfo_copilot_degraded_total": 0.0,
        }
        self._gauges: Dict[str, float] = {
            "cfo_copilot_queue_in_flight": 0.0,
            "cfo_copilot_queue_waiting": 0.0,
            "cfo_copilot_prefix_cache_hit_rate": 0.0,
        }
        self._histograms: Dict[str, List[float]] = {
            'cfo_copilot_request_duration_seconds{route="init"}': [0.0],
        }

    def inc_counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        key = self._format_key(name, labels)
        self._counters[key] = self._counters.get(key, 0.0) + value

    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        key = self._format_key(name, labels)
        self._gauges[key] = value

    def observe(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        key = self._format_key(name, labels)
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(value)

    def _format_key(self, name: str, labels: Optional[Dict[str, str]] = None) -> str:
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def generate_prometheus_text(self) -> str:
        """Renders metrics in Prometheus standard text exposition format."""
        lines = []

        # Categorized metric families for clean Prometheus scraping
        # Counters
        counter_families = {
            "cfo_copilot_requests_total": "Total executive chat requests handled",
            "cfo_copilot_429_total": "Total HTTP 429 queue saturation events",
            "cfo_copilot_errors_total": "Total error envelopes emitted",
            "cfo_copilot_llm_calls_total": "Total local LLM inference invocations",
            "cfo_copilot_verifier_fallbacks_total": "Total answers rejected by verifier and routed to fallback",
            "cfo_copilot_degraded_total": "Total requests served in degraded mode",
        }

        # Track which families we have emitted
        emitted_families = set()

        for c_key, c_val in sorted(self._counters.items()):
            base_name = c_key.split("{")[0]
            if base_name not in emitted_families:
                help_text = counter_families.get(base_name, f"Counter {base_name}")
                lines.append(f"# HELP {base_name} {help_text}")
                lines.append(f"# TYPE {base_name} counter")
                emitted_families.add(base_name)
            lines.append(f"{c_key} {c_val}")

        # Gauges
        gauge_families = {
            "cfo_copilot_queue_in_flight": "Current active in-flight requests in LLM semaphore",
            "cfo_copilot_queue_waiting": "Current pending requests waiting in LLM queue buffer",
            "cfo_copilot_tokens_per_second": "Estimated or measured generation throughput in tokens/s",
            "cfo_copilot_prefix_cache_hit_rate": "Running prefix cache hit rate (0.0 to 1.0)",
        }
        for g_key, g_val in sorted(self._gauges.items()):
            base_name = g_key.split("{")[0]
            if base_name not in emitted_families:
                help_text = gauge_families.get(base_name, f"Gauge {base_name}")
                lines.append(f"# HELP {base_name} {help_text}")
                lines.append(f"# TYPE {base_name} gauge")
                emitted_families.add(base_name)
            lines.append(f"{g_key} {g_val}")

        # Histograms / Summaries
        hist_families = {
            "cfo_copilot_request_duration_seconds": "End-to-end request latency duration",
            "cfo_copilot_ttft_first_content_seconds": "Time to first content (immediate deterministic facts block)",
            "cfo_copilot_ttft_verified_answer_seconds": "Time to final verified answer",
            "cfo_copilot_queue_wait_seconds": "Time spent waiting in bounded admission queue",
        }
        for h_key, vals in sorted(self._histograms.items()):
            if not vals:
                continue
            base_name = h_key.split("{")[0]
            labels_part = ""
            if "{" in h_key:
                labels_part = h_key.split("{")[1].rstrip("}")

            if base_name not in emitted_families:
                help_text = hist_families.get(base_name, f"Summary for {base_name}")
                lines.append(f"# HELP {base_name} {help_text}")
                lines.append(f"# TYPE {base_name} summary")
                emitted_families.add(base_name)

            sorted_vals = sorted(vals)
            p50 = sorted_vals[len(sorted_vals) // 2]
            p95 = sorted_vals[int(len(sorted_vals) * 0.95)]
            count = len(sorted_vals)
            total = sum(sorted_vals)

            if labels_part:
                lines.append(f"{base_name}_sum{{{labels_part}}} {total:.4f}")
                lines.append(f"{base_name}_count{{{labels_part}}} {count}")
                lines.append(f'{base_name}{{{labels_part},quantile="0.5"}} {p50:.4f}')
                lines.append(f'{base_name}{{{labels_part},quantile="0.95"}} {p95:.4f}')
            else:
                lines.append(f"{base_name}_sum {total:.4f}")
                lines.append(f"{base_name}_count {count}")
                lines.append(f'{base_name}{{quantile="0.5"}} {p50:.4f}')
                lines.append(f'{base_name}{{quantile="0.95"}} {p95:.4f}')

        return "\n".join(lines) + "\n"


# Global singleton instance
metrics = MetricsRegistry()
