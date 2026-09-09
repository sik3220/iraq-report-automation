"""Conservative same-day duplicate removal; preserve changed facts and user edits."""
import re
from contextlib import closing
import sqlite3
from init_db import DB_PATH, ensure_schema
from news_dedup import normalized_text
from report_dates import report_week, today


def title_tokens(title):
    return set(normalized_text(title).split())


def same_event(left, right):
    # A shared topic is not evidence of duplication. Keep all numbers and negations.
    a, b = normalized_text(left), normalized_text(right)
    return len(a) >= 30 and a == b


def duplicate_content(left, right):
    if not left["report_date"] or left["report_date"] != right["report_date"]:
        return False
    a, b = normalized_text(left["original"] or ""), normalized_text(right["original"] or "")
    if a and b:
        return len(a) >= 200 and a == b
    return same_event(left["title"] or "", right["title"] or "") and (
        normalized_text(left["excerpt"] or "") == normalized_text(right["excerpt"] or ""))


def dedupe_review_articles(week_of=None):
    week_start, _ = report_week(week_of or today())
    with closing(sqlite3.connect(DB_PATH)) as db, db:
        ensure_schema(db)
        db.row_factory = sqlite3.Row
        rows = db.execute(
            "SELECT * FROM articles WHERE week_start=? AND report_status IN ('pending','included','review') "
            "ORDER BY (report_status='included') DESC,LENGTH(COALESCE(original,'')) DESC,id",
            (week_start,),
        ).fetchall()
        representatives = []
        changed = 0
        for article in rows:
            # Never hide already selected/edited report candidates during collection.
            if article["report_status"] == "included" or article["edit_revision"]:
                representatives.append(article)
                continue
            representative = next((r for r in representatives if duplicate_content(article,r)), None)
            if representative:
                db.execute("UPDATE articles SET report_status='duplicate',duplicate_of=?,report_reason=? WHERE id=?",
                           (representative["id"],"동일 날짜·동일 내용 — 대표 기사 연결",article["id"]))
                changed += 1
            else:
                representatives.append(article)
    return {"week_start": week_start, "duplicates": changed}


if __name__ == "__main__":
    print(dedupe_review_articles())
