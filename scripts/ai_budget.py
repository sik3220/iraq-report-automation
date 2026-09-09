"""Persistent reservations for this project's text-only GPT-5.5 calls."""
from contextlib import closing
from decimal import Decimal
import json
from pathlib import Path
import sqlite3
from init_db import DB_PATH
from report_dates import today

SETTINGS = Path(__file__).resolve().parent.parent / "deploy/analysis-settings.json"
# Standard GPT-5.5 rates verified 2026-09-09:
# https://developers.openai.com/api/docs/models/gpt-5.5
INPUT_MICRO = 5
OUTPUT_MICRO = 30
MAX_OUTPUT = 2048


class BudgetExceeded(Exception):
    pass


def limits():
    data = json.loads(SETTINGS.read_text(encoding="utf-8-sig"))
    values = tuple(int(Decimal(str(data[key])) * 1_000_000)
                   for key in ("daily_usd", "monthly_usd"))
    if any(v < 0 for v in values):
        raise ValueError("예산은 0 이상이어야 합니다")
    return values


def ensure_budget(db):
    db.execute("""CREATE TABLE IF NOT EXISTS ai_spend(
        id INTEGER PRIMARY KEY, day TEXT NOT NULL, reserved INTEGER NOT NULL,
        charged INTEGER, status TEXT NOT NULL DEFAULT 'reserved')""")
    db.execute("""CREATE TABLE IF NOT EXISTS ai_budget_state(
        day TEXT PRIMARY KEY, daily_limit INTEGER, monthly_limit INTEGER,
        blocked INTEGER NOT NULL DEFAULT 0)""")


def reserve(instructions, payload):
    # ponytail: UTF-8 bytes upper-bound text tokens; release surplus after usage arrives.
    amount = (len((instructions + payload).encode("utf-8")) + 512) * INPUT_MICRO + MAX_OUTPUT * OUTPUT_MICRO
    day = today()
    daily, monthly = limits()
    with closing(sqlite3.connect(DB_PATH, timeout=30)) as db, db:
        ensure_budget(db)
        db.execute("BEGIN IMMEDIATE")
        used_day = db.execute("SELECT COALESCE(SUM(COALESCE(charged,reserved)),0) FROM ai_spend WHERE day=?", (day,)).fetchone()[0]
        used_month = db.execute("SELECT COALESCE(SUM(COALESCE(charged,reserved)),0) FROM ai_spend WHERE substr(day,1,7)=?", (day[:7],)).fetchone()[0]
        blocked = used_day + amount > daily or used_month + amount > monthly
        db.execute("INSERT OR REPLACE INTO ai_budget_state VALUES (?,?,?,?)", (day,daily,monthly,int(blocked)))
        if blocked:
            db.commit()
            raise BudgetExceeded("예산 잔액 부족 — 다음 실행까지 분석 대기")
        return db.execute("INSERT INTO ai_spend(day,reserved) VALUES (?,?)", (day,amount)).lastrowid


def settle(reservation, usage):
    # Unknown outcomes retain the full reservation, including after a process crash.
    if usage is None:
        return
    cost = usage.input_tokens * INPUT_MICRO + usage.output_tokens * OUTPUT_MICRO
    with closing(sqlite3.connect(DB_PATH, timeout=30)) as db, db:
        db.execute("UPDATE ai_spend SET charged=?,status='complete' WHERE id=?", (cost,reservation))
