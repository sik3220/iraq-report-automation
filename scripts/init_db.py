from contextlib import closing
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "articles.db"


def ensure_schema(connection: sqlite3.Connection) -> None:
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
    ):
        if name not in columns:
            connection.execute(f"ALTER TABLE articles ADD COLUMN {name} {definition}")
    connection.commit()


if __name__ == "__main__":
    DB_PATH.parent.mkdir(exist_ok=True)
    with closing(sqlite3.connect(DB_PATH)) as connection:
        ensure_schema(connection)
    print("articles.db 준비 완료")
