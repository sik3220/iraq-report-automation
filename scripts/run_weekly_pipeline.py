"""Run one complete Thursday-Wednesday collection cycle for the current dashboard."""
import argparse
import json

from dedupe_review_articles import dedupe_review_articles
from process_articles import filter_low_priority, process_articles
from report_dates import today
from resolve_review_articles import resolve_review_articles
from rss_to_db import save_rss_articles


def run_pipeline(
    week_of: str | None = None,
    sources: list[str] | None = None,
    run_ai: bool = True,
) -> dict:
    week_of = week_of or today()
    collected = save_rss_articles(week_of, sources)
    filtered = filter_low_priority(week_of)
    deduped = dedupe_review_articles(week_of)
    resolved = resolve_review_articles(week_of)
    failures = process_articles(week_of=week_of) if run_ai else None
    return {
        "week_of": week_of,
        "collection": collected,
        "initial_filter": {"excluded": filtered},
        "dedupe": deduped,
        "body_resolution": resolved,
        "ai": {"executed": run_ai, "failures": failures},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="목~수 이라크 주간보고 수집 파이프라인")
    parser.add_argument("--week-of", help="보고 기간에 포함되는 날짜 YYYY-MM-DD")
    parser.add_argument("--source", action="append", help="특정 출처만 수집; 여러 번 지정 가능")
    parser.add_argument("--skip-ai", action="store_true", help="수집·중복 제거·본문 확보만 실행")
    args = parser.parse_args()
    print(json.dumps(run_pipeline(args.week_of, args.source, not args.skip_ai), ensure_ascii=False), flush=True)

