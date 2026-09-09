import hashlib
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref_src"}


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username:
        raise ValueError("기사 주소는 공개 HTTP(S) URL이어야 합니다")
    host = parts.hostname.lower().removeprefix("www.")
    if parts.port and parts.port not in (80, 443):
        host += f":{parts.port}"
    query = sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                   if not k.lower().startswith("utm_") and k.lower() not in TRACKING)
    return urlunsplit(("https", host, parts.path.rstrip("/") or "/", urlencode(query), ""))


def normalized_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = "".join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in text)
    text = re.sub(r"[ـً-ٰٟ]", "", text)
    return " ".join(re.findall(r"[^\W_]+(?:[.,][0-9]+)?", text, flags=re.UNICODE))


def title_hash(title: str) -> str | None:
    normal = normalized_text(title)
    # Very short/generic headlines are unsafe to merge automatically.
    return hashlib.sha256(normal.encode()).hexdigest() if len(normal) >= 30 else None


def body_hash(body: str) -> str | None:
    normal = normalized_text(body)
    return hashlib.sha256(normal.encode()).hexdigest() if len(normal) >= 200 else None


def duplicate_title(connection, fingerprint: str | None, day: str | None):
    if not fingerprint or not day:
        return None
    row = connection.execute(
        "SELECT id FROM articles WHERE title_hash=? AND report_date=? AND duplicate_of IS NULL "
        "ORDER BY id LIMIT 1", (fingerprint, day)
    ).fetchone()
    return row[0] if row else None
