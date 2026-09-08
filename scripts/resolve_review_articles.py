"""Retry body collection for review articles from publishers that allow direct access."""
import argparse
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed

from article_scraper import fetch_article_text
from init_db import DB_PATH, ensure_schema
from news_sources import NEWS_SOURCES
from report_dates import report_week, today


def resolve_review_articles(week_of: str | None = None) -> dict:
    start, _ = report_week(week_of or today())
    allowed = {source["name"] for source in NEWS_SOURCES if source.get("body_fetch_review")}
    with sqlite3.connect(DB_PATH) as connection:
        ensure_schema(connection)
        articles = connection.execute(
            "SELECT id,source,url FROM articles WHERE week_start=? AND report_status='review' "
            "AND COALESCE(original,'')=''",
            (start,),
        ).fetchall()
    articles = [article for article in articles if article[1] in allowed]
    results: dict[int, tuple[str, str]] = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fetch_article_text, url): article_id for article_id, _, url in articles}
        for future in as_completed(futures):
            article_id = futures[future]
            try:
                results[article_id] = ("pending", future.result())
            except Exception as error:
                results[article_id] = ("review", type(error).__name__)
    resolved = 0
    with sqlite3.connect(DB_PATH) as connection:
        for article_id, (status, value) in results.items():
            if status == "pending":
                connection.execute(
                    "UPDATE articles SET original=?,report_status='pending',"
                    "report_reason='자동 원문 확보 완료 — 분석 대기' WHERE id=? AND report_status='review'",
                    (value, article_id),
                )
                resolved += 1
            else:
                connection.execute(
                    "UPDATE articles SET report_reason=? WHERE id=? AND report_status='review'",
                    (f"자동 원문 재시도 실패: {value}", article_id),
                )
    return {"attempted": len(articles), "resolved": resolved, "remaining": len(articles) - resolved}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="검토 대기 기사의 원문 자동 재수집")
    parser.add_argument("--week-of", help="보고 기간에 포함되는 날짜 YYYY-MM-DD")
    args = parser.parse_args()
    print(resolve_review_articles(args.week_of))
