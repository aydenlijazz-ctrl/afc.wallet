"""Runtime configuration.

Secrets are read from environment variables first (Cloud Run can mount Secret
Manager secrets as env vars via --set-secrets) and fall back to the Secret
Manager API when GOOGLE_CLOUD_PROJECT is set.
"""
from __future__ import annotations

import functools
import os
import uuid

SECRET_NAMES = (
    "BYBIT_API_KEY",
    "BYBIT_API_SECRET",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "ADMIN_SECRET",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "LIVE_KEY_ENCRYPTION_SECRET",
)


@functools.lru_cache(maxsize=None)
def secret(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value:
        return value.strip()
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if project and os.environ.get("APEX_USE_SECRET_MANAGER", "true") == "true":
        try:
            from google.cloud import secretmanager

            client = secretmanager.SecretManagerServiceClient()
            path = f"projects/{project}/secrets/{name}/versions/latest"
            return client.access_secret_version(name=path).payload.data.decode().strip()
        except Exception:  # secret missing or no permission
            return default
    return default


def env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def database_url() -> str:
    # Cloud SQL via unix socket: postgresql://user:pass@/db?host=/cloudsql/PROJECT:REGION:INSTANCE
    return secret("DATABASE_URL") or env("DATABASE_URL", "postgresql://apex:apex@localhost:5432/apex")


def owner_email() -> str:
    return env("OWNER_EMAIL", "owner@example.com").lower()


def user_id_for_email(email: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"apex-trader-pro:{email.lower()}")


def owner_user_id() -> uuid.UUID:
    """The bot trades a single Bybit account, so it has a single owner."""
    return user_id_for_email(owner_email())


BYBIT_BASE_URLS = [u for u in env("BYBIT_BASE_URLS", "https://api.bybit.com,https://api.bybitglobal.com").split(",") if u]
RECV_WINDOW = "5000"
