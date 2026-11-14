"""tests/conftest.py

Shared pytest fixtures across unit, integration, and security test suites.
"""

import pytest
from app.core.config import get_settings


@pytest.fixture(scope="session")
def settings():
    """Provides application settings for the test session."""
    return get_settings()
