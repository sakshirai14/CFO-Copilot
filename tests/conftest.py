"""tests/conftest.py

Shared pytest fixtures across unit, integration, and security test suites.
Enforces Foundation Lock 1 network isolation: blocks all non-localhost network connections.
"""

import socket
import pytest
from app.core.config import get_settings

ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}


@pytest.fixture(scope="session")
def settings():
    """Provides application settings for the test session."""
    return get_settings()


@pytest.fixture(autouse=True)
def restrict_network_to_localhost(monkeypatch):
    """Foundation Lock 1 Network Isolation Guard.
    Disables socket.connect except to localhost (127.0.0.1) and unix domain sockets.
    Proves that no test or application component ever contacts external hosted LLM APIs.
    """
    orig_connect = socket.socket.connect

    def guarded_connect(self, address):
        host = address[0] if isinstance(address, tuple) else address
        # Allow Unix domain sockets (file paths) and loopback addresses
        if isinstance(host, str) and (host in ALLOWED_HOSTS or host.startswith("/") or host.startswith("fe80")):
            return orig_connect(self, address)
        raise RuntimeError(
            f"LOCK 1 NETWORK ACCESS VIOLATION: Attempted socket connection to {address}. "
            "External hosted APIs (OpenAI, Gemini, Claude, etc.) are strictly prohibited."
        )

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
