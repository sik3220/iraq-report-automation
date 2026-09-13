from contextlib import closing
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from ai_processor import parse_report
from init_db import ensure_schema
from name_mapper import replace_names
from report_style import normalize_summary
from dedupe_review_articles import same_event
from category_mapper import classify_category
from article_scraper import fetch_article_text
from rss_to_db import fetch_entries, save_rss_articles, source_status
from run_job import run_recorded
import process_articles as batch


class ReportTests(unittest.TestCase):
    def test_collection_prunes_only_old_excluded_articles(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "articles.db"
            with closing(sqlite3.connect(path)) as db, db:
                ensure_schema(db)
                db.executemany(
                    "INSERT INTO articles(id,title,report_status,week_start,original,date_basis) VALUES (?,?,?,?,?,?)",
                    [
                        (1, "old rejected", "excluded", "2026-09-03", "large body", "published"),
                        (2, "current rejected", "excluded", "2026-09-10", "current body", "published"),
                        (3, "old selected", "included", "2026-09-03", "selected body", "published"),
                    ],
                )
            with patch("rss_to_db.DB_PATH", path), patch("rss_to_db.NEWS_SOURCES", []):
                result = save_rss_articles("2026-09-13")
            self.assertEqual(result["pruned"], 1)
            self.assertEqual(result["compacted"], 1)
            with closing(sqlite3.connect(path)) as db:
                self.assertEqual(db.execute("SELECT id,original FROM articles ORDER BY id").fetchall(), [(2, ""), (3, "selected body")])

    def test_sqlite_uses_wal_and_waits_for_scheduled_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "articles.db"
            with closing(sqlite3.connect(path)) as db:
                ensure_schema(db)
                self.assertEqual(db.execute("PRAGMA journal_mode").fetchone()[0], "wal")
                self.assertEqual(db.execute("PRAGMA busy_timeout").fetchone()[0], 30000)

    def test_default_analysis_only_current_week_and_limits_backups(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "articles.db"
            with closing(sqlite3.connect(path)) as db, db:
                ensure_schema(db)
                db.executemany(
                    "INSERT INTO articles(id,title,source,original,report_status,week_start,collected_at,region,category) VALUES (?,?,?,?,?,?,?,?,?)",
                    [
                        (1, "Iraq oil investment", "INA", "current body", "pending", "2026-09-10", "2026-09-13", "이라크", "경제"),
                        (2, "Iraq oil investment", "INA", "old body", "pending", "2026-09-03", "2026-09-06", "이라크", "경제"),
                    ],
                )
            backup_dir = path.parent / "backups"
            backup_dir.mkdir()
            for number in range(20):
                (backup_dir / f"articles-20260101-000000-{number:06}.db").write_bytes(b"old")
            report = SimpleNamespace(title="이라크, 석유 투자 추진", summary="", status="excluded", reason="중요도 미달")
            with patch.object(batch, "DB_PATH", path), patch.object(batch, "today", return_value="2026-09-13"), patch.object(
                batch, "dedupe_review_articles"
            ), patch.object(batch, "analyze_article", return_value=report):
                self.assertEqual(batch.process_articles(), 0)
                self.assertEqual(batch.process_articles(), 0)
            with closing(sqlite3.connect(path)) as db:
                self.assertEqual(db.execute("SELECT id,report_status,original FROM articles ORDER BY id").fetchall(), [(1, "excluded", ""), (2, "pending", "old body")])
            self.assertEqual(len(list(backup_dir.glob("articles-*.db"))), 20)
            self.assertFalse((backup_dir / "articles-20260101-000000-000000.db").exists())

    def test_nic_telegram_extracts_public_post_body(self):
        html = '''<div class="tgme_widget_message_wrap"><div class="tgme_widget_message"
                  data-post="investpromo_gov_iq/3421"><div class="tgme_widget_message_text">
                  🟢\nالهيئة الوطنية للاستثمار تعلن فرصة استثمارية\nتفاصيل المشروع</div>
                  <time datetime="2026-09-11T11:38:33+00:00"></time></div></div>'''
        response = type("Response", (), {"content": html.encode("utf-8")})()
        source = {"type": "telegram", "url": "https://t.me/s/investpromo_gov_iq"}
        with patch("rss_to_db.request_page", return_value=response):
            entry = fetch_entries(source)[0]
        self.assertEqual(entry["title"], "الهيئة الوطنية للاستثمار تعلن فرصة استثمارية")
        self.assertEqual(entry["link"], "https://t.me/investpromo_gov_iq/3421")
        self.assertEqual(entry["published"], "2026-09-11T11:38:33+00:00")
        self.assertIn("تفاصيل المشروع", entry["_body"])

    def test_job_harness_records_success_and_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "articles.db"
            result = type("Result", (), {"returncode": 0})()
            with patch("run_job.subprocess.run", return_value=result):
                self.assertEqual(run_recorded("collection", ["worker.py"], path), 0)
            result.returncode = 2
            with patch("run_job.subprocess.run", return_value=result):
                self.assertEqual(run_recorded("analysis", ["worker.py"], path), 2)
            with closing(sqlite3.connect(path)) as db:
                self.assertEqual(db.execute("SELECT job,status FROM job_runs ORDER BY id").fetchall(),
                                 [("collection", "success"), ("analysis", "failed")])
    def test_source_status_only_warns_after_three_days(self):
        full = {"metadata_only": False}
        limited = {"metadata_only": True}
        self.assertEqual(source_status(full, "2026-09-09", "2026-09-10"), "ok")
        self.assertEqual(source_status(limited, "2026-09-09", "2026-09-10"), "metadata")
        self.assertEqual(source_status(full, "2026-09-07", "2026-09-10"), "stale")
        occasional = {"stale_after_days": 14}
        self.assertEqual(source_status(occasional, "2026-09-01", "2026-09-10"), "ok")
        self.assertEqual(source_status(occasional, "2026-08-27", "2026-09-10"), "stale")

    def test_article_body_itemprop_fallback(self):
        body = "هذا نص خبري طويل يشرح تفاصيل القرار الحكومي وآثاره الاقتصادية على العراق " * 5
        response = type("Response", (), {"text": f'<form><div itemprop="articleBody">{body}</div></form>', "raise_for_status": lambda self: None})()
        with patch("article_scraper.requests.get", return_value=response):
            self.assertIn("القرار الحكومي", fetch_article_text("https://example.com/article"))

    def test_category_mapper_classifies_iraq_articles_and_preserves_editorial_values(self):
        self.assertEqual(classify_category(ai_title="이라크 투자청, 100만 주택용지 가격 인하", region="이라크"), "주택")
        self.assertEqual(classify_category(ai_title="이라크 PMF, 니네와서 ISIS 조직원 체포", region="이라크"), "안보")
        self.assertEqual(classify_category(ai_title="이라크 석유부, 원유 수출 확대 발표", region="이라크"), "경제")
        self.assertEqual(classify_category(ai_title="Al-Halbousi 국회의장, 튀르키예 공식 방문", region="이라크"), "정치")
        self.assertEqual(classify_category(ai_title="이란, 호르무즈 관련 경고", region="세계"), "세계")
        self.assertEqual(classify_category(ai_title="석유 투자", region="이라크", current_category="NIC"), "NIC")

    def test_low_priority_filter_reduces_pending_and_review_without_ai(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "articles.db"
            with closing(sqlite3.connect(path)) as db, db:
                ensure_schema(db)
                db.executemany(
                    "INSERT INTO articles(title,source,report_status,week_start,date_basis) VALUES (?,?,?,?,?)",
                    [
                        ("Iraq oil export plan", "INA", "pending", "2026-09-03", "published"),
                        ("Local ceremony", "INA", "pending", "2026-09-03", "published"),
                        ("العراق يناقش النفط والطاقة", "Shafaq", "review", "2026-09-03", "published"),
                        ("Community event", "Shafaq", "review", "2026-09-03", "published"),
                    ],
                )
            with closing(sqlite3.connect(path)) as db, db:
                db.execute("UPDATE articles SET original='body',excerpt='excerpt'")
            with patch.object(batch, "DB_PATH", path):
                self.assertEqual(batch.filter_low_priority("2026-09-08"), 2)
            with closing(sqlite3.connect(path)) as db:
                self.assertEqual(
                    db.execute("SELECT report_status,COUNT(*) FROM articles GROUP BY report_status ORDER BY report_status").fetchall(),
                    [("excluded", 2), ("pending", 1), ("review", 1)],
                )
                self.assertEqual(db.execute("SELECT COUNT(*) FROM articles WHERE report_status='excluded' AND (original<>'' OR excerpt<>'')").fetchone()[0], 0)

    def test_names_single_pass_and_idempotent(self):
        text = "Donald Trump, Trump 대통령, 트럼프"
        expected = "Trump 대통령, Trump 대통령, Trump 대통령"
        self.assertEqual(replace_names(text), expected)
        self.assertEqual(replace_names(expected), expected)
        self.assertEqual(replace_names("Trumpet"), "Trumpet")
        self.assertEqual(replace_names("Zaydi 총리"), "Al-Zaidi 총리")
        self.assertEqual(replace_names("Halbousi 국회의장, Maliki 전 총리, Sudani 전 총리"), "Al-Halbousi 국회의장, Al-Maliki 전 총리, Al-Sudani 전 총리")

    def test_pre_ai_excludes_routine_incidents(self):
        self.assertEqual(batch.pre_ai_exclusion_reason("farmers detained in Lebanon"), "국지적 개인 구금 사건")
        self.assertEqual(batch.pre_ai_exclusion_reason("السفارة تتابع الاعتداء على الطلبة"), "개별 유학생 피습·영사 대응")
        self.assertIsNone(batch.pre_ai_exclusion_reason("العراق يوسع الاستثمار في الطاقة"))

    def test_duplicate_match_preserves_changed_numbers_and_negation(self):
        self.assertTrue(same_event("Iraq announces new housing investment programme", "Iraq announces new housing investment programme"))
        self.assertFalse(same_event("US destroys three Iranian oil carriers", "US destroys five Iranian oil carriers"))
        self.assertFalse(same_event("Iraq approves new housing programme", "Iraq does not approve new housing programme"))
        self.assertFalse(same_event("미국 이란 유조선 3척 공격 발표", "미국 이란 유조선 5척 공격 발표"))

    def test_priority_preserves_iraq_topics_without_country_name(self):
        for title in ("مجلس النواب يناقش قانون الانتخابات", "هيئة الاستثمار تعلن المدن الجديدة",
                      "الحلبوسي يترأس مباحثات برلمانية", "القوات الأمنية تحمي الحدود"):
            self.assertTrue(batch.eligible({"title": title, "source": "INA"}), title)
        self.assertTrue(batch.eligible({"title": "تسهيلات جديدة لدعم المستثمرين في العراق", "source": "NIC 공식 Telegram"}))
        self.assertTrue(batch.eligible({"title": "US and Iran trade attacks on ships", "source": "BBC"}))
        self.assertFalse(batch.eligible({"title": "Egypt drugs case", "source": "BBC"}))

    def test_country_names_and_missing_body(self):
        self.assertEqual(replace_names("Iran, Oman 협의"), "이란, 오만 협의")
        value = dict(status="included", reason="안보", title="공습", summary=["* 원문 없는 추가 사실"])
        self.assertEqual(parse_report(json.dumps(value), has_body=False).summary, "")

    def test_terminal_period_only(self):
        self.assertEqual(
            normalize_summary(['* 3.14% 증가.', '* 9.7 협상 재개。', '* "합의 추진."']),
            ['* 3.14% 증가', '* 9.7 협상 재개', '* "합의 추진"'],
        )

    def test_parse_title_only_and_summary_limit(self):
        value = dict(status="included", reason="역내 안보", title="협상 재개.", summary=[])
        self.assertEqual(parse_report(json.dumps(value)).title, "협상 재개")
        self.assertEqual(parse_report(json.dumps(value)).summary, "")
        value["summary"] = ["* 하나", "* 둘", "* 셋"]
        with self.assertRaises(ValueError):
            parse_report(json.dumps(value))

    def test_excluded_does_not_have_report_text(self):
        value = dict(status="excluded", reason="개인 스포츠", title="시민권 부여", summary=["* 내용"])
        with self.assertRaises(ValueError):
            parse_report(json.dumps(value))
        value["summary"] = []
        self.assertEqual(parse_report(json.dumps(value)).status, "excluded")
        value["status"] = "anything"
        with self.assertRaises(ValueError):
            parse_report(json.dumps(value))

    def test_legacy_schema_migration_keeps_data(self):
        with closing(sqlite3.connect(":memory:")) as db, db:
            db.execute("CREATE TABLE articles (id INTEGER PRIMARY KEY, title TEXT)")
            db.execute("INSERT INTO articles VALUES (1, 'original')")
            ensure_schema(db)
            ensure_schema(db)
            self.assertEqual(db.execute("SELECT title, report_status FROM articles").fetchone(),
                             ("original", "pending"))

    def test_failed_reprocessing_preserves_text_and_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "articles.db"
            with closing(sqlite3.connect(path)) as db, db:
                ensure_schema(db)
                db.execute("INSERT INTO articles(id,title,ai_title,summary,report_status) VALUES "
                           "(1,'original','saved title','saved summary','included')")
            with patch.object(batch, "DB_PATH", path), patch.object(
                batch, "analyze_article", side_effect=ValueError("invalid response")
            ):
                self.assertEqual(batch.process_articles(reprocess=True), 1)
            for target in [path, *path.parent.glob("backups/*.db")]:
                with closing(sqlite3.connect(target)) as db:
                    self.assertEqual(db.execute("SELECT ai_title,summary,report_status FROM articles").fetchone(),
                                     ("saved title", "saved summary", "included"))
            self.assertEqual(len(list(path.parent.glob("backups/*.db"))), 1)


if __name__ == "__main__":
    unittest.main()