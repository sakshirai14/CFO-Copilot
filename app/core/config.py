"""app/core/config.py

Platform configuration management using Pydantic Settings.
Implements Foundation Lock 6 (Role segregation) and Lock 11 (No secrets in repo).
Reads environment variables from .env if present.
"""

from functools import lru_cache
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for CFO Copilot."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Application Settings
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    # Database Host & Ports
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5435
    POSTGRES_DB: str = "cfo_copilot"
    POSTGRES_TEST_DB: str = "cfo_copilot_test"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = ""

    # Segregated Database Roles (Lock 6)
    DB_OWNER_USER: str = "cfo_owner"
    DB_OWNER_PASSWORD: str = ""

    DB_APP_RW_USER: str = "app_rw"
    DB_APP_RW_PASSWORD: str = ""

    DB_APP_RO_USER: str = "app_ro"
    DB_APP_RO_PASSWORD: str = ""

    # Multi-Tenant & Authentication
    TENANTS: str = "acme,borealis"
    DEFAULT_TENANT: str = "acme"
    TENANT_API_KEYS: str = "cfo_key_acme_dev:acme,cfo_key_borealis_dev:borealis"

    # Concurrency & Rate Limits
    MAX_CONCURRENT_SESSIONS: int = 16
    REQUEST_QUEUE_TIMEOUT_SECONDS: int = 10
    RATE_LIMIT_RPS: int = 20
    MAX_QUESTION_LENGTH: int = 2000
    MAX_BODY_SIZE_BYTES: int = 65536
    ENABLE_FAULT_INJECTION: bool = False

    # Inference Serving
    INFERENCE_API_BASE: str = "http://localhost:8080/v1"
    INFERENCE_MODEL: str = "openai/qwen2.5-3b-instruct"
    INFERENCE_API_KEY: str = "not-needed-for-local"
    INFERENCE_TIMEOUT_SECONDS: int = 30
    MAX_CONTEXT_TOKENS: int = 4096
    DROP2_MAX_CONTEXT_TOKENS: int = 8192

    @property
    def tenant_list(self) -> List[str]:
        return [t.strip() for t in self.TENANTS.split(",") if t.strip()]

    def get_tenant_for_api_key(self, api_key: Optional[str]) -> Optional[str]:
        if not api_key:
            return None
        mapping = {}
        for pair in self.TENANT_API_KEYS.split(","):
            if ":" in pair:
                k, t = pair.strip().split(":", 1)
                mapping[k.strip()] = t.strip()
        return mapping.get(api_key.strip())

    def get_role_credentials(self, role: str) -> tuple[str, str]:
        """Returns (username, password) for a specified DB role."""
        role = role.lower()
        if role in ("owner", "cfo_owner"):
            return self.DB_OWNER_USER, self.DB_OWNER_PASSWORD
        elif role in ("rw", "app_rw"):
            return self.DB_APP_RW_USER, self.DB_APP_RW_PASSWORD
        elif role in ("ro", "app_ro"):
            return self.DB_APP_RO_USER, self.DB_APP_RO_PASSWORD
        elif role in ("postgres", "superuser", "admin"):
            return self.POSTGRES_USER, self.POSTGRES_PASSWORD
        else:
            raise ValueError(f"Unknown database role: {role}. Must be owner, app_rw, app_ro, or postgres.")

    def get_connection_params(self, role: str = "owner", is_test: bool = False) -> dict:
        """Returns connection dict suitable for psycopg2.connect(**params)."""
        user, password = self.get_role_credentials(role)
        db_name = self.POSTGRES_TEST_DB if is_test else self.POSTGRES_DB
        return {
            "host": self.POSTGRES_HOST,
            "port": self.POSTGRES_PORT,
            "dbname": db_name,
            "user": user,
            "password": password,
            "connect_timeout": 5,
        }

    def get_database_url(self, role: str = "owner", is_test: bool = False) -> str:
        """Returns standard postgresql:// connection URI."""
        user, password = self.get_role_credentials(role)
        db_name = self.POSTGRES_TEST_DB if is_test else self.POSTGRES_DB
        # URL encode password if needed
        return f"postgresql://{user}:{password}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{db_name}"


@lru_cache()
def get_settings() -> Settings:
    """Returns singleton settings instance."""
    return Settings()
