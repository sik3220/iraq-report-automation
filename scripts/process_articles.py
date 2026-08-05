import sqlite3

from ai_processor import summarize_article


DB_PATH = "data/articles.db"
MAX_ARTICLES = 10


def process_articles() -> None:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT
                id,
                title,
                original
            FROM articles
            WHERE summary = ''
            ORDER BY collected_at DESC
            LIMIT ?
            """,
            (MAX_ARTICLES,),
        )

        articles = cursor.fetchall()

        if not articles:
            print("처리할 기사가 없습니다.")
            return

        success_count = 0

        for index, article in enumerate(articles, start=1):
            try:
                article_text = article["original"].strip()

                if not article_text:
                    article_text = article["title"]

                print(
                    f"[{index}/{len(articles)}] 처리 중: "
                    f"{article['title']}"
                )

                summary = summarize_article(article_text)

                cursor.execute(
                    """
                    UPDATE articles
                    SET summary = ?
                    WHERE id = ?
                    """,
                    (
                        f"* {summary}",
                        article["id"],
                    ),
                )

                connection.commit()
                success_count += 1

                print("✅ 저장 완료")

            except Exception as error:
                print(f"❌ 처리 실패: {error}")

        print(
            f"전체 {len(articles)}건 중 "
            f"{success_count}건 처리 완료"
        )

    finally:
        connection.close()


if __name__ == "__main__":
    process_articles()