"""Check source metadata without fetching article bodies or calling AI."""
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from rss_to_db import fetch_entries, source_status
from init_db import DB_PATH, ensure_schema
from news_sources import NEWS_SOURCES
from report_dates import BAGHDAD, article_date

def check(source):
    note = source.get('note', '')
    counts = {}
    status = 'disabled'
    if source['enabled']:
        try:
            entries = fetch_entries(source)
            dates = [article_date(e.get('published') or e.get('updated'), None)[0] for e in entries]
            latest = max((d for d in dates if d), default=None)
            status = source_status(source, latest)
            counts = {'discovered': len(entries)}
            note += ' | 제목 목록 점검만 수행, 본문 수집 미검증'
            if latest: note += ' | 최신 게시일 ' + latest
            if not entries: status = 'error'; note = '기사 목록 없음'
        except Exception as error:
            status = 'error'; note = f'연결 점검 실패: {type(error).__name__}: {error}'
    return (source['id'], source['name'], status, note, datetime.now(BAGHDAD).isoformat(), json.dumps(counts))

if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(check, NEWS_SOURCES))
    with sqlite3.connect(DB_PATH) as connection:
        ensure_schema(connection)
        for row in results:
            connection.execute('INSERT INTO source_checks VALUES (?,?,?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET status=excluded.status,note=excluded.note,checked_at=excluded.checked_at,counts=excluded.counts', row)
            print(json.dumps(dict(id=row[0],status=row[2],note=row[3]),ensure_ascii=True))
