import sqlite3
from datetime import datetime

# DB 연결
conn = sqlite3.connect("data/articles.db")

cursor = conn.cursor()

# 테스트 기사 저장
cursor.execute("""
INSERT INTO articles (
    source,
    category,
    title,
    summary,
    original,
    language,
    published_at,
    collected_at,
    url
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    "Reuters",
    "정치",
    "테스트 기사",
    "이것은 테스트 요약입니다.",
    "This is the original article.",
    "en",
    datetime.now().isoformat(),
    datetime.now().isoformat(),
    "https://test.com"
))

conn.commit()
conn.close()

print("✅ 테스트 기사 저장 완료")