from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import concurrent.futures
import sqlite3
import tempfile
import unittest
import ai_budget as budget
from dedupe_review_articles import duplicate_content
from news_dedup import normalized_text


class BudgetTests(unittest.TestCase):
    def test_reservations_survive_restart_and_failures_and_reset_by_month(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "budget.db"
            with patch.object(budget, "DB_PATH", db), patch.object(budget, "limits", return_value=(100000,100000)):
                with patch.object(budget, "today", return_value="2026-09-09"):
                    first = budget.reserve("hello","world")
                    with self.assertRaises(budget.BudgetExceeded):
                        budget.reserve("hello","world")
                    budget.settle(first, SimpleNamespace(input_tokens=100,output_tokens=100))
                    budget.reserve("hello","world")  # Unknown result retains reservation.
                with patch.object(budget, "today", return_value="2026-09-10"):
                    with self.assertRaises(budget.BudgetExceeded):
                        budget.reserve("hello","world")
                with patch.object(budget, "today", return_value="2026-10-01"):
                    budget.reserve("hello","world")

    def test_concurrent_calls_cannot_overspend(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "budget.db"
            with closing(sqlite3.connect(db)) as connection, connection:
                budget.ensure_budget(connection)
            with patch.object(budget, "DB_PATH", db), patch.object(budget, "limits", return_value=(100000,100000)):
                def attempt(_):
                    try:
                        budget.reserve("hello","world")
                        return 1
                    except budget.BudgetExceeded:
                        return 0
                with concurrent.futures.ThreadPoolExecutor(2) as pool:
                    self.assertEqual(sum(pool.map(attempt, range(2))),1)

    def test_daily_limit_resets_but_month_does_not(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(budget,"DB_PATH",Path(directory)/"budget.db"), patch.object(budget,"limits",return_value=(100000,200000)):
                for day in ("2026-09-09","2026-09-10"):
                    with patch.object(budget,"today",return_value=day):
                        budget.reserve("hello","world")
                        with self.assertRaises(budget.BudgetExceeded):
                            budget.reserve("hello","world")

    def test_api_budget_block_prevents_network_call(self):
        import ai_processor
        with patch.object(ai_processor, "load_dotenv"), patch.object(ai_processor.os, "getenv", return_value="test-key"), patch.object(ai_processor, "OpenAI") as client, patch.object(ai_processor, "reserve", side_effect=budget.BudgetExceeded):
            with self.assertRaises(budget.BudgetExceeded):
                ai_processor.analyze_article("Iraq housing", "body text")
            client.return_value.responses.create.assert_not_called()

    def test_api_records_usage_before_rejecting_invalid_output(self):
        import ai_processor
        usage = SimpleNamespace(input_tokens=100, output_tokens=200)
        response = SimpleNamespace(usage=usage, status="completed", output_text="invalid json")
        with patch.object(ai_processor, "load_dotenv"), patch.object(ai_processor.os, "getenv", return_value="test-key"), patch.object(ai_processor, "OpenAI") as client, patch.object(ai_processor, "reserve", return_value=1), patch.object(ai_processor, "settle") as settle:
            client.return_value.responses.create.return_value = response
            with self.assertRaises(ValueError):
                ai_processor.analyze_article("Iraq housing", "body text")
            settle.assert_called_once_with(1, usage)
            self.assertEqual(client.call_args.kwargs["max_retries"], 0)
            self.assertEqual(client.return_value.responses.create.call_args.kwargs["max_output_tokens"], budget.MAX_OUTPUT)

    def test_numbers_dates_and_changed_body_are_preserved(self):
        base = {"report_date":"2026-09-09","title":"Iraq announces housing construction programme","excerpt":"","original":"Housing programme approved. " * 20}
        self.assertTrue(duplicate_content(base,dict(base)))
        self.assertFalse(duplicate_content(base,{**base,"report_date":"2026-09-10"}))
        self.assertFalse(duplicate_content(base,{**base,"original":base["original"]+"Budget raised to 5 billion."}))
        self.assertNotEqual(normalized_text("٣ ناقلات"), normalized_text("٥ ناقلات"))
        self.assertTrue(normalized_text("مجلس النواب يناقش الإسكان"))


if __name__ == "__main__":
    unittest.main()
