"""PostgreSQL access. Every query is parameterized (psycopg placeholders)."""
from __future__ import annotations

import json
import pathlib
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from . import config

_pool: ConnectionPool | None = None


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            config.database_url(), min_size=1, max_size=5, kwargs={"row_factory": dict_row}, open=True
        )
    return _pool


def reset_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
    _pool = None


@contextmanager
def conn() -> Iterator[psycopg.Connection]:
    with pool().connection() as c:
        yield c


def migrate() -> None:
    sql = (pathlib.Path(__file__).parent / "schema.sql").read_text()
    with conn() as c:
        # every service migrates on start-up; serialize so parallel cold starts don't race
        c.execute("SELECT pg_advisory_xact_lock(hashtext('apex-migrate'))")
        c.execute(sql)


def fetch(sql: str, params: tuple | dict = ()) -> list[dict[str, Any]]:
    with conn() as c:
        return list(c.execute(sql, params).fetchall())


def fetch_one(sql: str, params: tuple | dict = ()) -> dict[str, Any] | None:
    with conn() as c:
        return c.execute(sql, params).fetchone()


def execute(sql: str, params: tuple | dict = ()) -> int:
    with conn() as c:
        return c.execute(sql, params).rowcount


def audit(user_id, service: str, action: str, *, symbol=None, strategy=None, request=None, response=None,
          success: bool = True) -> None:
    execute(
        """INSERT INTO live_audit_log (user_id, service, action, symbol, strategy, request, response, success)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (user_id, service, action, symbol, strategy,
         json.dumps(request, default=str) if request is not None else None,
         json.dumps(response, default=str) if response is not None else None, success),
    )


@contextmanager
def advisory_lock(name: str) -> Iterator[bool]:
    """Non-blocking cross-instance lock so overlapping scheduler runs never trade twice."""
    with pool().connection() as c:
        got = c.execute("SELECT pg_try_advisory_lock(hashtext(%s)) AS ok", (name,)).fetchone()["ok"]
        try:
            yield bool(got)
        finally:
            if got:
                c.execute("SELECT pg_advisory_unlock(hashtext(%s))", (name,))
