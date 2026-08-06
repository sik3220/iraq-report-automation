import sqlite3
from datetime import datetime

import feedparser

from news_sources import NEWS_SOURCES
from article_scraper import fetch_article_text


DB_PATH = "data/articles.db"
MAX_ARTICLES_PER_SOURCE = 5


def save_rss_articles() -> None:
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    total_saved = 0

    try:
        for source in NEWS_SOURCES:
            feed = feedparser.parse(source["url"])

            saved_for_source = 0

            for article in feed.entries[:MAX_ARTICLES_PER_SOURCE]:
                title = article.get("title", "").strip()
                url = article.get("link", "").strip()
                try:
                    original = fetch_article_text(url)
                except Exception as e:
                    print(f"Error fetching article text: {e}")
                    original = ""

                if not title or not url:
                    continue

                cursor.execute(
                    "SELECT id FROM articles WHERE url = ?",
                    (url,),
                )

                if cursor.fetchone():
                    continue

                cursor.execute(
                    """
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
                    """,
                    (
                        source["name"],
                        source["category"],
                        title,
                        "",
                        original,
                        "en",
                        article.get("published", ""),
                        datetime.now().isoformat(),
                        url,
                    ),
                )

                saved_for_source += 1
                total_saved += 1

            print(
                f"{source['name']}: 새 기사 {saved_for_source}건 저장"
            )

        connection.commit()

    finally:
        connection.close()

    print(f"✅ 전체 새 기사 {total_saved}건 저장 완료")


if __name__ == "__main__":
    save_rss_articles()