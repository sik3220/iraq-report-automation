"""Copy the retained local SQLite database to an empty Supabase Postgres project."""
import os
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv
import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parent.parent
TABLES = ("articles", "source_checks", "analysis_attempts", "job_runs", "ai_spend", "ai_budget_state")
IDENTITY_TABLES = ("articles", "analysis_attempts", "job_runs", "ai_spend")


def connection_url() -> str:
    load_dotenv(ROOT / ".env")
    value = os.getenv("DATABASE_URL", "").strip()
    host = (urlsplit(value).hostname or "").lower()
    if not value or not (host.endswith(".supabase.co") or host.endswith(".pooler.supabase.com")):
        raise ValueError("Supabase Connect 화면의 DATABASE_URL이 필요합니다")
    return value


def migrate(source_path: Path = ROOT / "data/articles.db") -> dict[str, int]:
    if not source_path.is_file():
        raise FileNotFoundError(f"SQLite 원본을 찾을 수 없습니다: {source_path}")
    schema = (ROOT / "supabase/migrations/20260914000000_initial.sql").read_text(encoding="utf-8")
    copied = {}
    with sqlite3.connect(source_path) as source, psycopg.connect(
        connection_url(), sslmode="require", prepare_threshold=None
    ) as target:
        source.row_factory = sqlite3.Row
        target.execute(schema)
        if target.execute("select count(*) from public.articles").fetchone()[0]:
            raise RuntimeError("Supabase articles 테이블이 비어 있지 않아 이전을 중단했습니다")
        existing = {row[0] for row in source.execute("select name from sqlite_master where type='table'")}
        for table in TABLES:
            if table not in existing:
                copied[table] = 0
                continue
            columns = [row[1] for row in source.execute(f"pragma table_info({table})")]
            rows = source.execute(f"select * from {table}").fetchall()
            if rows:
                names = sql.SQL(",").join(map(sql.Identifier, columns))
                values = sql.SQL(",").join(sql.Placeholder() * len(columns))
                statement = sql.SQL("insert into public.{} ({}) values ({}) on conflict do nothing").format(
                    sql.Identifier(table), names, values
                )
                target.executemany(statement, [tuple(row[column] for column in columns) for row in rows])
            copied[table] = len(rows)
        for table in IDENTITY_TABLES:
            target.execute(
                sql.SQL("select setval(pg_get_serial_sequence({}, 'id'), greatest(coalesce(max(id), 1), 1), count(*) > 0) from public.{}")
                .format(sql.Literal(f"public.{table}"), sql.Identifier(table))
            )
    return copied


if __name__ == "__main__":
    print(migrate())
