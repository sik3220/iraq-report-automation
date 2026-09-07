from contextlib import closing
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_processor import parse_report
from init_db import ensure_schema
from name_mapper import replace_names
from report_style import normalize_summary
import process_articles as batch


class ReportTests(unittest.TestCase):
    def test_names_single_pass_and_idempotent(self):
        text = "Donald Trump, Trump 대통령, 트럼프"
        expected = "Trump 대통령, Trump 대통령, Trump 대통령"
        self.assertEqual(replace_names(text), expected)
        self.assertEqual(replace_names(expected), expected)
        self.assertEqual(replace_names("Trumpet"), "Trumpet")

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