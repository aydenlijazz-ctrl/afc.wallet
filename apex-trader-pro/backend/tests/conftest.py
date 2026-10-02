import os

os.environ.setdefault("DATABASE_URL", "postgresql://apex:apex@localhost:5432/apex_test")
os.environ["ADMIN_SECRET"] = "test-admin-secret"
os.environ["OWNER_EMAIL"] = "owner@example.com"
os.environ["TELEGRAM_CHAT_ID"] = "777"
os.environ["APEX_USE_SECRET_MANAGER"] = "false"
for k in ("TELEGRAM_BOT_TOKEN", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_CLOUD_PROJECT"):
    os.environ.pop(k, None)

import psycopg  # noqa: E402
import pytest  # noqa: E402

from apex import config, db  # noqa: E402
from tests.fakes import FakeExchange, FakeTelegram  # noqa: E402

TABLES = ["trades", "bot_settings", "strategy_positions", "adaptive_reverse_log", "auto_reverse_log", "ai_cache",
          "ai_usage", "ai_feedback", "live_audit_log"]


@pytest.fixture(scope="session", autouse=True)
def _database():
    url = os.environ["DATABASE_URL"]
    admin = url.rsplit("/", 1)[0] + "/postgres"
    name = url.rsplit("/", 1)[1]
    with psycopg.connect(admin, autocommit=True) as c:
        c.execute(f"DROP DATABASE IF EXISTS {name}")
        c.execute(f"CREATE DATABASE {name}")
    config.secret.cache_clear()
    db.reset_pool()
    db.migrate()
    yield
    db.reset_pool()


@pytest.fixture(autouse=True)
def _clean():
    db.execute("TRUNCATE " + ", ".join(TABLES))
    yield


@pytest.fixture
def uid():
    return config.owner_user_id()


@pytest.fixture
def ex():
    return FakeExchange()


@pytest.fixture
def tg():
    return FakeTelegram()
