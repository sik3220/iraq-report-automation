"""Collect inexpensive publisher metadata first. This module never calls an AI model."""
import argparse
import json
import re
import sqlite3
from contextlib import closing
from datetime import date, datetime
from urllib.parse import urljoin, urlsplit

import feedparser
import requests
from bs4 import BeautifulSoup

from init_db import DB_PATH, ensure_schema
from news_sources import NEWS_SOURCES
from news_dedup import canonical_url, title_hash
from report_dates import BAGHDAD, article_date, report_week, today
from article_scraper import fetch_article_text

MAX_ENTRIES = 100
HEADERS = {"User-Agent": "IraqReportCollector/0.1"}
SKIP_SECTIONS = ("sport", "رياضة", "ريـاضة", "entertainment", "lifestyle")
WORLD_PRIORITY_TERMS = {
    "iraq": 12, "hormuz": 9,
    "oil": 6, "energy": 6, "opec": 6, "shipping": 6, "maritime": 6, "strait": 6,
    "iran": 5, "gulf": 4, "uae": 4, "saudi": 4, "kuwait": 4, "oman": 4,
    "israel": 4, "lebanon": 4, "yemen": 4, "syria": 4, "gaza": 4, "hezbollah": 4,
    "strike": 3, "war": 3, "sanction": 3, "blockade": 3, "ceasefire": 3, "attack": 3,
    "united states": 2, "u.s.": 2, "us ": 2,
}


def world_priority_score(title, excerpt):
    text = f"{title} {excerpt}".lower()
    return sum(weight for term, weight in WORLD_PRIORITY_TERMS.items() if term in text)

def source_status(source, latest, reference_day=None):
    """Separate a working limited feed from a feed that has actually stopped updating."""
    if latest and (date.fromisoformat(reference_day or today()) - date.fromisoformat(latest)).days >= source.get("stale_after_days", 3):
        return "stale"
    return "metadata" if source.get("metadata_only") else "ok"


def request_page(url):
    response = requests.get(url, headers=HEADERS, timeout=(5, 20))
    response.raise_for_status()
    return response


def fetch_entries(source):
    response = request_page(source["url"])
    if source["type"] == "telegram":
        soup = BeautifulSoup(response.content, "html.parser")
        result = []
        for post in soup.select(".tgme_widget_message_wrap"):
            message = post.select_one("[data-post]")
            body = post.select_one(".tgme_widget_message_text")
            stamp = post.select_one("time[datetime]")
            if not message or not body or not stamp:
                continue
            text = body.get_text("\n", strip=True)
            lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]
            post_id = message.get("data-post", "")
            title = next((line for line in lines if len(line) >= 12), "")
            if title and post_id:
                result.append(dict(title=title[:300], link=f"https://t.me/{post_id}",
                                   published=stamp.get("datetime", ""), summary=text[:1200], _body=text[:20000]))
        if not result:
            raise ValueError("텔레그램 공개 게시물이 비어 있음")
        return result[:MAX_ENTRIES]
    if source["type"] == "discover_rss":
        soup = BeautifulSoup(response.content, "html.parser")
        links = soup.select('link[type="application/rss+xml"][href]')
        if not links:
            raise ValueError("공식 RSS 링크를 찾지 못함")
        url = urljoin(response.url, links[0]["href"])
        if urlsplit(url).hostname != urlsplit(response.url).hostname:
            raise ValueError("다른 도메인의 RSS는 확인 필요")
        response = request_page(url)
    if source["type"] == "listing":
        soup = BeautifulSoup(response.content, "html.parser")
        result, seen = [], set()
        for anchor in soup.select("a[href]"):
            url = urljoin(response.url, anchor["href"])
            title = anchor.get_text(" ", strip=True)
            if (urlsplit(url).hostname == urlsplit(response.url).hostname
                    and re.search(source["article_pattern"], urlsplit(url).path)
                    and len(title) >= 25 and url not in seen):
                seen.add(url)
                result.append(dict(title=title, link=url, published="", summary=""))
        # Listing metadata has no reliable timestamp; explicitly mark collection date.
        if source.get("recent_id_window") and result:
            ids = [int(match.group(1)) for item in result
                   if (match := re.search(r"/([0-9]+)[^/]*\.html$", item["link"]))]
            if ids:
                minimum = max(ids) - source["recent_id_window"]
                result = [item for item in result if (match := re.search(r"/([0-9]+)[^/]*\.html$", item["link"]))
                          and int(match.group(1)) >= minimum]
        return result[:MAX_ENTRIES]
    feed = feedparser.parse(response.content)
    if not feed.entries:
        raise ValueError("RSS 기사 목록이 비어 있거나 XML 형식이 아님")
    entries = feed.entries
    if source.get("publisher_host"):
        host = source["publisher_host"]
        entries = [e for e in entries if (urlsplit(e.get("source", {}).get("href", "")).hostname or "").removeprefix("www.") == host]
    return entries[:MAX_ENTRIES]


def store_entry(connection, source, entry, collected, start, end):
    title = entry.get("title", "").strip()
    url = entry.get("link", "").strip()
    excerpt = BeautifulSoup(entry.get("summary", ""), "html.parser").get_text(" ", strip=True)[:1200]
    if source.get("metadata_only") and source.get("region") == "세계" and world_priority_score(title, excerpt) < 9:
        return "low_relevance"
    if source.get("relevance_sections"):
        section_match = re.search(r"/ar/([^/]+)/", url)
        section = section_match.group(1) if section_match else ""
        terms = source.get("relevance_terms", ())
        if section not in source["relevance_sections"] and not any(term in title for term in terms):
            return "low_relevance"
    if not title or not url:
        return "invalid"
    try:
        canonical = canonical_url(url)
    except ValueError:
        return "invalid"
    # This check happens before any article-body request or AI call.
    if connection.execute("SELECT 1 FROM articles WHERE canonical_url=?", (canonical,)).fetchone():
        return "existing"
    published = entry.get("published") or entry.get("updated") or ""
    day, basis = article_date(published, collected)
    if not day or day < start or day > end or day > article_date(collected, collected)[0]:
        return "outside_period"
    fingerprint = title_hash(title)
    duplicate = None  # Compare fetched content before classifying a same-title follow-up.
    tags = " ".join(str(tag.get("term", "")) for tag in entry.get("tags", []))
    sections = (url + " " + tags).lower()
    is_low_priority = any(word in sections for word in SKIP_SECTIONS)
    status = "duplicate" if duplicate else "excluded" if is_low_priority else "pending"
    reason = "동일 날짜·동일 제목 — 대표 기사 연결" if duplicate else "사전 분류: 스포츠·연예·생활 섹션" if is_low_priority else ""
    excerpt = BeautifulSoup(entry.get("summary", ""), "html.parser").get_text(" ", strip=True)[:1200]
    original = entry.get("_body", "")
    if status == "pending" and source.get("metadata_only"):
        status = "review"
        reason = source.get("note", "제목·요약만 수집 — 본문 확인 필요")
    if status == "pending" and not original:
        try:
            original = fetch_article_text(url)
        except Exception as error:
            reason = f"본문 수집 실패: {type(error).__name__}"
            status = "review"
    if status == "excluded":
        excerpt = ""
        original = ""
    connection.execute(
        "INSERT INTO articles(source,category,title,summary,original,language,published_at,collected_at,url,"
        "report_status,report_reason,canonical_url,title_hash,report_date,date_basis,week_start,duplicate_of,region,excerpt) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (source["name"], source["category"], title, "", original, source["language"], published, collected, url,
         status, reason, canonical, fingerprint, day, basis, report_week(day)[0], duplicate, source["region"], excerpt)
    )
    return status


def save_rss_articles(week_of: str | None = None, selected_sources: list[str] | None = None) -> dict:
    start, end = report_week(week_of or today())
    collected = datetime.now(BAGHDAD).isoformat()
    all_results = []
    with closing(sqlite3.connect(DB_PATH)) as connection:
        ensure_schema(connection)
        pruned = connection.execute(
            "DELETE FROM articles WHERE report_status='excluded' AND week_start < ?", (start,),
        ).rowcount
        compacted = connection.execute(
            "UPDATE articles SET original='',excerpt='' WHERE report_status='excluded' "
            "AND (COALESCE(original,'')<>'' OR COALESCE(excerpt,'')<>'')"
        ).rowcount
        connection.commit()
        for source in NEWS_SOURCES:
            if selected_sources and source["id"] not in selected_sources:
                continue
            counts = {}
            status, note = "disabled", source.get("note", "")
            if source["enabled"]:
                try:
                    entries = fetch_entries(source)
                    for entry in entries:
                        outcome = store_entry(connection, source, entry, collected, start, end)
                        counts[outcome] = counts.get(outcome, 0) + 1
                    dated = [article_date(e.get("published") or e.get("updated"), None)[0] for e in entries]
                    latest = max((d for d in dated if d), default=None)
                    status = source_status(source, latest)
                    if status == "stale":
                        note = f"RSS 최신 게시일 {latest} — 3일 이상 갱신 없음"
                    elif source["type"] == "listing":
                        detail = source.get("note", "")
                        note = "게시일 확인 전: 수집일 기준으로 표시"
                        if detail:
                            note = f"{note} — {detail}"
                except Exception as error:
                    status, note = "error", f"수집 실패: {type(error).__name__}"
                connection.commit()
            connection.execute(
                "INSERT INTO source_checks(source_id,name,status,note,checked_at,counts) VALUES (?,?,?,?,?,?) "
                "ON CONFLICT(source_id) DO UPDATE SET status=excluded.status,note=excluded.note,"
                "checked_at=excluded.checked_at,counts=excluded.counts",
                (source["id"], source["name"], status, note, collected, json.dumps(counts))
            )
            connection.commit()
            result = dict(name=source["name"], status=status, note=note, counts=counts)
            all_results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
    return {"week_start": start, "week_end": end, "sources": all_results, "pruned": pruned, "compacted": compacted, "ai_calls": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="목~수 보고 기간의 기사 메타데이터 수집 (AI 호출 없음)")
    parser.add_argument("--week-of", help="보고 기간에 포함되는 날짜 YYYY-MM-DD")
    parser.add_argument("--source", action="append", help="특정 출처 id만 수집")
    args = parser.parse_args()
    known = {source["id"] for source in NEWS_SOURCES}
    if args.source and set(args.source) - known:
        parser.error("등록되지 않은 출처 id")
    print(json.dumps(save_rss_articles(args.week_of, args.source), ensure_ascii=False), flush=True)
