import sqlite3
import feedparser
from datetime import datetime

RSS_URL = "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml"

# RSS 읽기
feed = feedparser.parse(RSS_URL)

# DB 연결
conn = sqlite3.connect("data/articles.db")
cursor = conn.cursor()

saved_count = 0

for article in feed.entries[:5]:   # 우선 5개만 저장

    title = article.get("title", "")
    url = article.get("link", "")

    # 이미 저장된 기사인지 확인
    cursor.execute(
        "SELECT id FROM articles WHERE url=?",
        (url,)
    )

    if cursor.fetchone():
        continue

    cursor.execute("""
        INSERT INTO articles(
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

        "BBC",
        "세계",
        title,
        "",
        "",
        "en",
        article.get("published", ""),
        datetime.now().isoformat(),
        url

    ))

    saved_count += 1

conn.commit()
conn.close()

print(f"✅ 새 기사 {saved_count}건 저장 완료")