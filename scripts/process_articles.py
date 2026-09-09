from contextlib import closing
import argparse
import sqlite3
from datetime import datetime

from ai_processor import analyze_article
from category_mapper import classify_category
from init_db import DB_PATH, ensure_schema

DEFAULT_LIMIT = None
MIN_PRIORITY_SCORE = 11
PRIORITY_TERMS = {
    "이라크": 8, "iraq": 8, "العراق": 8,
    "안보": 6, "security": 6, "امن": 6,
    "에너지": 6, "oil": 6, "energy": 6, "نفط": 6,
    "호르무즈": 6, "hormuz": 6, "هرمز": 6,
    "이란": 5, "iran": 5, "إيران": 5,
    "미국": 4, "united states": 4, "ترامب": 4,
    "투자": 5, "investment": 5, "اقتصاد": 4,
    "정부": 3, "government": 3, "حكومة": 3,
    "مجلس النواب": 6, "رئيس الوزراء": 5, "وزير الخارجية": 4,
    "الحشد الشعبي": 6, "داعش": 8, "الداخلية": 4,
    "استثمار": 5, "سكن": 5, "اقتصادي": 5,
    "لبنان": 4, "إسرائيل": 4, "اليمن": 4,
    "israel": 4, "lebanon": 4, "yemen": 4, "gaza": 4,
    "الإطار التنسيقي": 7,
}

PRE_AI_EXCLUSIONS = (
    (("الطلبة", "الاعتداء"), "개별 유학생 피습·영사 대응"),
    (("الطلبة", "السفارة"), "개별 유학생 피습·영사 대응"),
    (("دعم الصيادلة",), "직능단체 일상 면담"),
    (("القبض على 4 متهمين بالمخدرات",), "일상적 지역 치안 단속"),
    (("يفتتحان المبنى",), "건물 개관 행사"),
    (("farmers detained",), "국지적 개인 구금 사건"),
    (("egypt drugs case",), "이라크와 무관한 형사 사건"),
    (("palestinian teens killed",), "개인 피해 중심 사건"),
    (("fbi bury evidence", "9/11"), "이라크와 무관한 과거 사건"),
    (("father of teen shot dead",), "개인 피해 중심 사건"),
)

def pre_ai_exclusion_reason(title: str) -> str | None:
    lowered = title.lower()
    for terms, reason in PRE_AI_EXCLUSIONS:
        if all(term.lower() in lowered for term in terms):
            return reason
    return None


def priority_score(article: sqlite3.Row) -> int:
    text = f"{article['title'] or ''} {article['source'] or ''}".lower()
    return sum(weight for term, weight in PRIORITY_TERMS.items() if term in text)


def filter_low_priority(week_of: str | None = None) -> int:
    conditions = ["report_status IN ('pending','review')"]
    parameters: list[str] = []
    if week_of:
        from report_dates import report_week
        week_start, _ = report_week(week_of)
        conditions.append("week_start = ?")
        parameters.append(week_start)
    with closing(sqlite3.connect(DB_PATH)) as connection, connection:
        connection.row_factory = sqlite3.Row
        ensure_schema(connection)
        articles = connection.execute(
            f"SELECT id,title,source FROM articles WHERE {' AND '.join(conditions)}",
            parameters,
        ).fetchall()
        ids = [(article["id"],) for article in articles if priority_score(article) < MIN_PRIORITY_SCORE]
        connection.executemany(
            "UPDATE articles SET report_status='excluded',report_reason='사전 분류: 중요도 기준 미달' WHERE id=?",
            ids,
        )
        connection.commit()
    return len(ids)


def process_articles(reprocess: bool = False, limit: int | None = DEFAULT_LIMIT, week_of: str | None = None) -> int:
    if not reprocess:
        filter_low_priority(week_of)
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
        conditions = []
        parameters: list[str] = []
        if not reprocess:
            conditions.append("report_status = 'pending'")
        if week_of:
            from report_dates import report_week
            week_start, _ = report_week(week_of)
            conditions.append("week_start = ?")
            parameters.append(week_start)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        articles = connection.execute(
            f"SELECT id,title,source,original,collected_at,category,region,excerpt FROM articles {where} "
            "ORDER BY collected_at DESC",
            parameters,
        ).fetchall()
        ranked = sorted(
            articles,
            key=lambda article: (priority_score(article), article["collected_at"] or ""),
            reverse=True,
        )
        if not reprocess:
            ranked = [article for article in ranked if priority_score(article) >= MIN_PRIORITY_SCORE]
        articles = ranked[:limit] if limit is not None else ranked
        failures = 0
        counts = {"included": 0, "excluded": 0, "review": 0}
        for index, article in enumerate(articles, start=1):
            print(f"[{index}/{len(articles)}] 기사 {article['id']} 처리 중", flush=True)
            exclusion = pre_ai_exclusion_reason(article["title"] or "")
            if exclusion:
                connection.execute(
                    "UPDATE articles SET report_status='excluded',report_reason=? WHERE id=?",
                    (f"사전 분류: {exclusion}", article["id"]),
                )
                connection.commit()
                counts["excluded"] += 1
                print(f"excluded: {exclusion}", flush=True)
                continue
            try:
                report = analyze_article(article["title"] or "", article["original"] or "")
                category = classify_category(
                    title=article["title"] or "", ai_title=report.title,
                    summary=report.summary, original=article["original"] or "",
                    excerpt=article["excerpt"] or "", region=article["region"] or "",
                    current_category=article["category"] or "미분류",
                )
                connection.execute(
                    "UPDATE articles SET ai_title=?,summary=?,report_status=?,report_reason=?,category=? WHERE id=?",
                    (report.title, report.summary, report.status, report.reason, category, article["id"]),
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
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="선택적 수동 상한; 생략하면 중요도 기준 통과 기사를 모두 처리")
    parser.add_argument("--week-of", help="해당 날짜가 포함된 목~수 보고 기간만 처리 YYYY-MM-DD")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit은 1 이상이어야 합니다")
    raise SystemExit(1 if process_articles(args.reprocess, args.limit, args.week_of) else 0)
