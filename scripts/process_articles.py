from contextlib import closing
import argparse
import sqlite3
from datetime import datetime

from ai_processor import analyze_article
from init_db import DB_PATH, ensure_schema

MAX_ARTICLES = 10


def process_articles(reprocess: bool = False, limit: int = MAX_ARTICLES) -> int:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        # Snapshot before schema migration and before replacing existing report text.
        backup_dir = DB_PATH.parent / "backups"
        backup_dir.mkdir(exist_ok=True)
        backup_path = backup_dir / f"articles-{datetime.now():%Y%m%d-%H%M%S-%f}.db"
        with closing(sqlite3.connect(backup_path)) as backup:
            connection.backup(backup)
        print(f"백업: {backup_path}", flush=True)
        ensure_schema(connection)
        where = "" if reprocess else "WHERE report_status = 'pending'"
        articles = connection.execute(
            f"SELECT id, title, original FROM articles {where} "
            "ORDER BY collected_at DESC LIMIT ?", (limit,)
        ).fetchall()
        failures = 0
        counts = {"included": 0, "excluded": 0, "review": 0}
        for index, article in enumerate(articles, start=1):
            print(f"[{index}/{len(articles)}] 기사 {article['id']} 처리 중", flush=True)
            try:
                report = analyze_article(article["title"] or "", article["original"] or "")
                connection.execute(
                    "UPDATE articles SET ai_title=?, summary=?, report_status=?, report_reason=? WHERE id=?",
                    (report.title, report.summary, report.status, report.reason, article["id"]),
                )
                connection.commit()
                counts[report.status] += 1
                print(f"{report.status}: {report.title}\n{report.summary}\n근거: {report.reason}", flush=True)
            except Exception as error:
                connection.rollback()
                failures += 1
                # No overwrite on failure; keep the previous report and status.
                print(f"처리 실패(기사 {article['id']}): {type(error).__name__}", flush=True)
        print(f"처리 결과: {counts}, 실패 {failures}건", flush=True)
        return failures
    finally:
        connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="기사 선정 및 현식식 보고서 문안 생성")
    parser.add_argument("--reprocess", action="store_true", help="기존 기사도 새 기준으로 재처리")
    parser.add_argument("--limit", type=int, default=MAX_ARTICLES)
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit은 1 이상이어야 합니다")
    raise SystemExit(1 if process_articles(args.reprocess, args.limit) else 0)
