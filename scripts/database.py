"""Use one database at a time: Supabase Postgres when configured, SQLite otherwise."""
import os
import sqlite3 as local_sqlite
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT / "data" / "articles.db"
load_dotenv(ROOT / ".env")
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
Row = local_sqlite.Row


class HybridRow(dict):
    def __getitem__(self, key):
        return list(self.values())[key] if isinstance(key, int) else super().__getitem__(key)


def _hybrid_row(cursor):
    names = [column.name for column in cursor.description]
    return lambda values: HybridRow(zip(names, values))


def _is_default_path(database) -> bool:
    try:
        return Path(database).resolve() == DEFAULT_DB_PATH.resolve()
    except TypeError:
        return True


def _postgres_sql(statement: str) -> str:
    statement = statement.replace("BEGIN IMMEDIATE", "BEGIN").replace("?", "%s")
    if statement.startswith("INSERT OR REPLACE INTO ai_budget_state VALUES"):
        return statement.replace("INSERT OR REPLACE INTO", "INSERT INTO") + (
            " ON CONFLICT(day) DO UPDATE SET daily_limit=EXCLUDED.daily_limit,"
            "monthly_limit=EXCLUDED.monthly_limit,blocked=EXCLUDED.blocked"
        )
    return statement


class Connection:
    def __init__(self, raw, postgres=False):
        self.raw = raw
        self.postgres = postgres

    def execute(self, statement, parameters=()):
        return self.raw.execute(_postgres_sql(statement) if self.postgres else statement, parameters)

    def executemany(self, statement, parameters):
        return self.raw.executemany(_postgres_sql(statement) if self.postgres else statement, parameters)

    def commit(self):
        return self.raw.commit()

    def rollback(self):
        return self.raw.rollback()

    def close(self):
        return self.raw.close()

    def backup(self, target):
        return self.raw.backup(target.raw)

    @property
    def in_transaction(self):
        return self.raw.info.transaction_status != 0 if self.postgres else self.raw.in_transaction

    @property
    def row_factory(self):
        return None if self.postgres else self.raw.row_factory

    @row_factory.setter
    def row_factory(self, value):
        if not self.postgres:
            self.raw.row_factory = value

    def __enter__(self):
        self.raw.__enter__()
        return self

    def __exit__(self, *args):
        return self.raw.__exit__(*args)


def connect(database=DEFAULT_DB_PATH, timeout=30):
    if DATABASE_URL and _is_default_path(database):
        import psycopg
        raw = psycopg.connect(DATABASE_URL, sslmode="require", connect_timeout=timeout,
                              prepare_threshold=None, row_factory=_hybrid_row)
        return Connection(raw, postgres=True)
    raw = local_sqlite.connect(database, timeout=timeout)
    raw.row_factory = local_sqlite.Row
    return Connection(raw)


def is_postgres(connection) -> bool:
    return bool(getattr(connection, "postgres", False))
