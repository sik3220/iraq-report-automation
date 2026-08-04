import sqlite3
from pathlib import Path

# data 폴더 생성
data_folder = Path("data")
data_folder.mkdir(exist_ok=True)

# DB 파일 위치
db_path = data_folder / "articles.db"

# DB 연결
conn = sqlite3.connect(db_path)

# 테이블 생성
conn.execute("""
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT,
    category TEXT,
    title TEXT,
    summary TEXT,
    original TEXT,
    language TEXT,
    published_at TEXT,
    collected_at TEXT,
    url TEXT
)
""")

conn.commit()
conn.close()

print("✅ articles.db 생성 완료")