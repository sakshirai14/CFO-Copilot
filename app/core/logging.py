"""app/core/logging.py

Structured JSON Logging for CFO Copilot using structlog.
Enforces Foundation Lock Lantern (Observability).
Outputs machine-parseable JSON lines containing request_id, tenant, route, status, latency.
"""

import logging
import sys
import structlog


def setup_structured_logging():
    """Configures structlog to emit JSON lines to standard output."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "cfo_copilot"):
    return structlog.get_logger(name)
