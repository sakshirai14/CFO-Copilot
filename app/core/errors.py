"""app/core/errors.py

Typed exception hierarchy for CFO Copilot platform.
Prevents unhandled low-level driver stack traces and enables
structured degradation and error reporting.
"""


class CFOCopilotError(Exception):
    """Base exception for all domain and platform errors."""
    pass


class DatabaseUnavailableError(CFOCopilotError):
    """Raised when the primary or read-only database is unreachable or connection fails."""
    pass


class ModelUnavailableError(CFOCopilotError):
    """Raised when the local LLM inference server is unreachable or offline."""
    pass


class GroundingVerificationError(CFOCopilotError):
    """Raised when an answer violates the grounded-answer contract or verification fails."""
    pass


class SecurityViolationError(CFOCopilotError):
    """Raised when a tenant isolation breach or security guardrail is tripped."""
    pass
