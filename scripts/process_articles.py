from contextlib import closing
import argparse
import sqlite3
from datetime import datetime

from ai_processor import analyze_article
from ai_budget import BudgetExceeded
from report_dates import today
from dedupe_review_articles import dedupe_review_articles
from category_mapper import classify_category
from init_db import DB_PATH, ensure_schema
from news_dedup import normalized_text
from news_sources import NEWS_SOURCES

DEFAULT_LIMIT = None
MAX_BACKUPS = 20
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
    "استثمار": 5, "مستثمر": 5, "سكن": 5, "اقتصادي": 5,
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


# These are recall guards, not a final editorial decision.
IRAQ_SOURCES = {s["name"] for s in NEWS_SOURCES if s["region"] == "이라크"}
CORE_TOPICS = (
    "parliament", "housing", "residential", "investment", "cabinet", "election",
    "budget", "refinery", "electricity", "militia", "disarm", "prime minister",
    "국회", "주택", "투자", "예산", "전력", "무장", "برلمان", "مجلس النواب",
    "الحلبوسي", "السوداني", "مجلس الوزراء", "انتخابات", "موازنة", "استثمار",
    "سكن", "مدن جديدة", "المدن الجديدة", "مصفاة", "كهرباء", "الفصائل", "الأمن",
    "منطقة حرة", "مطار دولي", "هيئة الاستثمار", "رئيس الوزراء",
)
REGIONAL_TOPICS = (
    "hormuz", "red sea", "opec", "هرمز", "البحر الأحمر", "أوبك",
    "호르무즈", "홍해", "iran", "إيران", "이란", "gulf", "الخليج",
)
REGIONAL_EVENTS = (
    "attack", "strike", "sanction", "blockade", "ceasefire", "negotiat", "missile",
    "oil", "shipping", "war", "هجوم", "قصف", "عقوبات", "حصار", "مفاوض",
    "صاروخ", "نفط", "حرب", "공격", "제재", "협상", "원유", "휴전",
)


def priority_score(article) -> int:
    title = normalized_text(article["title"] or "")
    score = sum(weight for term, weight in PRIORITY_TERMS.items()
                if normalized_text(term) in title)
    iraq = article["source"] in IRAQ_SOURCES or any(
        term in title for term in ("iraq", "العراق", "이라크"))
    if iraq and any(normalized_text(term) in title for term in CORE_TOPICS):
        score = max(score, MIN_PRIORITY_SCORE)
    if any(normalized_text(term) in title for term in REGIONAL_TOPICS) and any(
            normalized_text(term) in title for term in REGIONAL_EVENTS):
        score = max(score, MIN_PRIORITY_SCORE)
    return score


def eligible(article) -> bool:
    return not pre_ai_exclusion_reason(article["title"] or "") and priority_score(article) >= MIN_PRIORITY_SCORE


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
        ids = [(article["id"],) for article in articles if not eligible(article)]
        connection.executemany(
            "UPDATE articles SET report_status='excluded',report_reason='사전 분류: 중요도 기준 미달' WHERE id=?",
            ids,
        )
        connection.commit()
    return len(ids)


def process_articles(reprocess: bool = False, limit: int | None = DEFAULT_LIMIT, week_of: str | None = None) -> int:
    target_week = week_of or (None if reprocess else today())
    if not reprocess:
        filter_low_priority(target_week)
        dedupe_review_articles(target_week)
    connection = sqlite3.connect(DB_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    try:
        ensure_schema(connection)
        conditions = []
        parameters: list[str] = []
        if not reprocess:
            conditions.append("report_status = 'pending'")
        if target_week:
            from report_dates import report_week
            week_start, _ = report_week(target_week)
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
            ranked = [article for article in ranked if eligible(article)]
        articles = ranked[:limit] if limit is not None else ranked
        failures = 0
        counts = {"included": 0, "excluded": 0, "review": 0}
        if not articles:
            print(f"처리 결과: {counts}, 실패 0건", flush=True)
            return 0
        backup_dir = DB_PATH.parent / "backups"
        backup_dir.mkdir(exist_ok=True)
        backup_path = backup_dir / f"articles-{datetime.now():%Y%m%d-%H%M%S-%f}.db"
        with closing(sqlite3.connect(backup_path)) as backup:
            connection.backup(backup)
        for old in sorted(backup_dir.glob("articles-*.db"))[:-MAX_BACKUPS]:
            old.unlink()
        print(f"백업: {backup_path}", flush=True)
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
            connection.execute("BEGIN IMMEDIATE")
            attempted = connection.execute(
                "SELECT 1 FROM analysis_attempts WHERE article_id=? AND day=?",
                (article["id"],today())).fetchone()
            current = connection.execute("SELECT report_status FROM articles WHERE id=?", (article["id"],)).fetchone()
            if attempted or (not reprocess and current[0] != "pending"):
                connection.rollback()
                continue
            attempt = connection.execute(
                "INSERT INTO analysis_attempts(article_id,day,status) VALUES (?,?,'started')",
                (article["id"],today())).lastrowid
            connection.commit()
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
                connection.execute("UPDATE analysis_attempts SET status='complete' WHERE id=?", (attempt,))
                connection.commit()
                counts[report.status] += 1
                print(f"{report.status}: {report.title}\n{report.summary}\n근거: {report.reason}", flush=True)
            except BudgetExceeded:
                connection.rollback()
                connection.execute("DELETE FROM analysis_attempts WHERE id=?", (attempt,))
                connection.commit()
                print("예산 대기: 남은 기사는 삭제하지 않고 다음 실행에 처리", flush=True)
                break
            except Exception as error:
                connection.rollback()
                connection.execute("UPDATE analysis_attempts SET status='failed' WHERE id=?", (attempt,))
                connection.commit()
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
