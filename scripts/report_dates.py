from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

BAGHDAD = timezone(timedelta(hours=3))


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        result = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        try:
            result = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
    return result.replace(tzinfo=BAGHDAD) if result.tzinfo is None else result


def article_date(published: str | None, collected: str | None) -> tuple[str | None, str]:
    for value, basis in ((published, "published"), (collected, "collected")):
        parsed = parse_datetime(value)
        if parsed:
            return parsed.astimezone(BAGHDAD).date().isoformat(), basis
    return None, "unknown"


def report_week(day: str) -> tuple[str, str]:
    value = date.fromisoformat(day)
    start = value - timedelta(days=(value.weekday() - 3) % 7)
    return start.isoformat(), (start + timedelta(days=6)).isoformat()


def today() -> str:
    return datetime.now(BAGHDAD).date().isoformat()
