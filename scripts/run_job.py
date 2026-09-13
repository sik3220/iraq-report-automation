"""Record one scheduled job without changing the job's implementation."""
import argparse
import sqlite3
import subprocess
import sys
from contextlib import closing
from datetime import datetime
from pathlib import Path

from init_db import DB_PATH, ensure_schema
from report_dates import BAGHDAD


def run_recorded(job: str, command: list[str], db_path: Path = DB_PATH) -> int:
    started = datetime.now(BAGHDAD).isoformat()
    with closing(sqlite3.connect(db_path)) as connection, connection:
        ensure_schema(connection)
        run_id = connection.execute(
            "INSERT INTO job_runs(job,started_at,status) VALUES (?,?,'running')",
            (job, started),
        ).lastrowid
        connection.commit()
    try:
        result = subprocess.run([sys.executable, "-X", "utf8", *command], check=False)
        status = "success" if result.returncode == 0 else "failed"
        detail = "" if result.returncode == 0 else f"종료 코드 {result.returncode}"
        code = result.returncode
    except Exception as error:
        status, detail, code = "failed", type(error).__name__, 1
    with closing(sqlite3.connect(db_path)) as connection, connection:
        connection.execute(
            "UPDATE job_runs SET finished_at=?,status=?,detail=? WHERE id=?",
            (datetime.now(BAGHDAD).isoformat(), status, detail, run_id),
        )
        connection.commit()
    return code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="예약 작업 실행 기록")
    parser.add_argument("job", choices=("collection", "analysis"))
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.command:
        parser.error("실행할 Python 스크립트가 필요합니다")
    raise SystemExit(run_recorded(args.job, args.command))