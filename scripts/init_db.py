from contextlib import closing
import sqlite3
from pathlib import Path
from report_dates import article_date, report_week
from news_dedup import canonical_url, title_hash
from news_sources import NEWS_SOURCES

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "articles.db"


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA busy_timeout=30000")
    if not connection.in_transaction:
        connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT, category TEXT, title TEXT, ai_title TEXT,
            summary TEXT, original TEXT, language TEXT,
            published_at TEXT, collected_at TEXT, url TEXT,
            report_status TEXT NOT NULL DEFAULT 'pending',
            report_reason TEXT
        )
    """)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(articles)")}
    for name, definition in (
        ("ai_title", "TEXT"),
        ("report_status", "TEXT NOT NULL DEFAULT 'pending'"),
        ("report_reason", "TEXT"),
        ("edited_title", "TEXT"),
        ("edited_summary", "TEXT"),
        ("edit_revision", "INTEGER NOT NULL DEFAULT 0"),
        ("canonical_url", "TEXT"),
        ("title_hash", "TEXT"),
        ("body_hash", "TEXT"),
        ("report_date", "TEXT"),
        ("date_basis", "TEXT"),
        ("week_start", "TEXT"),
        ("duplicate_of", "INTEGER"),
        ("region", "TEXT"),
        ("excerpt", "TEXT"),
    ):
        if name not in columns:
            connection.execute(f"ALTER TABLE articles ADD COLUMN {name} {definition}")
    all_columns = {row[1] for row in connection.execute("PRAGMA table_info(articles)")}
    if {"published_at", "collected_at", "url"}.issubset(all_columns):
        for row in connection.execute(
            "SELECT id,title,published_at,collected_at,url FROM articles WHERE date_basis IS NULL"
        ).fetchall():
            day, basis = article_date(row[2], row[3])
            try:
                canonical = canonical_url(row[4] or "")
            except ValueError:
                canonical = None
            connection.execute(
                "UPDATE articles SET report_date=?,date_basis=?,week_start=?,canonical_url=?,title_hash=? WHERE id=?",
                (day, basis, report_week(day)[0] if day else None, canonical, title_hash(row[1] or ""), row[0])
            )
    connection.execute("CREATE INDEX IF NOT EXISTS articles_period ON articles(week_start,report_status)")
    connection.execute("CREATE INDEX IF NOT EXISTS articles_url ON articles(canonical_url)")
    connection.execute("CREATE INDEX IF NOT EXISTS articles_title_date ON articles(title_hash,report_date)")
    connection.execute("""CREATE TABLE IF NOT EXISTS source_checks(
        source_id TEXT PRIMARY KEY,name TEXT,status TEXT,note TEXT,checked_at TEXT,counts TEXT)""")
    for source in NEWS_SOURCES:
        connection.execute(
            "INSERT OR IGNORE INTO source_checks(source_id,name,status,note,checked_at,counts) VALUES (?,?,?,?,NULL,'{}')",
            (source["id"], source["name"], "unchecked" if source["enabled"] else "disabled", source.get("note", "수집 실행 이력 없음"))
        )
    connection.execute("""CREATE TABLE IF NOT EXISTS analysis_attempts(
        id INTEGER PRIMARY KEY,article_id INTEGER NOT NULL,day TEXT NOT NULL,
        started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,status TEXT NOT NULL)""")
    connection.execute("""CREATE TABLE IF NOT EXISTS job_runs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,job TEXT NOT NULL,
        started_at TEXT NOT NULL,finished_at TEXT,status TEXT NOT NULL,detail TEXT)""")
    connection.execute("CREATE INDEX IF NOT EXISTS job_runs_job_id ON job_runs(job,id DESC)")
    connection.commit()


if __name__ == "__main__":
    DB_PATH.parent.mkdir(exist_ok=True)
    with closing(sqlite3.connect(DB_PATH)) as connection:
        ensure_schema(connection)
    print("articles.db 준비 완료")
