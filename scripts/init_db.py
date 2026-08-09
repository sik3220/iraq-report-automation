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
    ai_title TEXT,
    summary TEXT,
    original TEXT,
    language TEXT,
    published_at TEXT,
    collected_at TEXT,
    url TEXT
)
""")

# 기존 DB에 ai_title 컬럼이 없으면 추가
columns = [
    row[1]
    for row in conn.execute("PRAGMA table_info(articles)")
]

if "ai_title" not in columns:
    conn.execute("ALTER TABLE articles ADD COLUMN ai_title TEXT")
    print("✅ ai_title 컬럼 추가 완료")

conn.commit()
conn.close()

print("✅ articles.db 생성 완료")