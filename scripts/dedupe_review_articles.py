"""Collapse high-confidence duplicate events before asking for source text."""
import re
import sqlite3
from contextlib import closing
from itertools import combinations

from init_db import DB_PATH, ensure_schema
from report_dates import report_week, today

STOP_WORDS = {
    "the", "and", "for", "with", "from", "after", "says", "said", "amid",
    "over", "new", "latest", "reuters", "military", "middle", "east", "that", "was",
}


def title_tokens(title: str) -> set[str]:
    return {word for word in re.findall(r"[^\W_]{2,}", title.lower()) if word not in STOP_WORDS and not word.isdigit()}


def same_event(left: str, right: str) -> bool:
    left_tokens, right_tokens = title_tokens(left), title_tokens(right)
    if not left_tokens or not right_tokens:
        return False
    shared = left_tokens & right_tokens
    coverage = len(shared) / min(len(left_tokens), len(right_tokens))
    return len(shared) >= 4 and coverage >= 0.55


def dedupe_review_articles(week_of: str | None = None) -> dict:
    week_start, _ = report_week(week_of or today())
    with closing(sqlite3.connect(DB_PATH)) as connection, connection:
        ensure_schema(connection)
        connection.row_factory = sqlite3.Row
        articles = connection.execute(
            "SELECT id,COALESCE(ai_title,title) AS dedupe_title,report_status,original,excerpt,collected_at FROM articles "
            "WHERE week_start=? AND report_status IN ('pending','included','review')",
            (week_start,),
        ).fetchall()
        parent = {article["id"]: article["id"] for article in articles}

        def find(article_id: int) -> int:
            while parent[article_id] != article_id:
                parent[article_id] = parent[parent[article_id]]
                article_id = parent[article_id]
            return article_id

        def union(left_id: int, right_id: int) -> None:
            left_root, right_root = find(left_id), find(right_id)
            if left_root != right_root:
                parent[right_root] = left_root

        for left, right in combinations(articles, 2):
            if same_event(left["dedupe_title"] or "", right["dedupe_title"] or ""):
                union(left["id"], right["id"])

        clusters: dict[int, list[sqlite3.Row]] = {}
        for article in articles:
            clusters.setdefault(find(article["id"]), []).append(article)
        changed = 0
        for cluster in clusters.values():
            if len(cluster) < 2:
                continue
            representative = max(
                cluster,
                key=lambda item: (
                    item["report_status"] == "included",
                    len(item["original"] or ""),
                    len(item["excerpt"] or ""),
                    item["collected_at"] or "",
                ),
            )
            for article in cluster:
                if article["id"] == representative["id"]:
                    continue
                connection.execute(
                    "UPDATE articles SET report_status='duplicate',duplicate_of=?,report_reason=? WHERE id=?",
                    (representative["id"], "제목상 동일 사건 — 대표 기사 연결", article["id"]),
                )
                changed += 1
    return {"week_start": week_start, "duplicates": changed}


if __name__ == "__main__":
    print(dedupe_review_articles())
