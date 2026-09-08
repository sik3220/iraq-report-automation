"""Assign Iraq report categories without making an AI call."""
from contextlib import closing
import sqlite3

from init_db import DB_PATH, ensure_schema

VALID_CATEGORIES = ("정치", "안보", "주택", "경제", "세계", "NIC")

CATEGORY_TERMS = {
    "주택": {
        "주택": 8, "주택용지": 10, "부동산": 8, "housing": 8, "real estate": 8,
        "سكن": 8, "إسكان": 8, "عقار": 8, "أراضي سكنية": 10,
    },
    "안보": {
        "안보": 7, "치안": 7, "군": 5, "공습": 8, "무장": 7, "테러": 8,
        "isis": 10, "pmf": 9, "militia": 8, "armed group": 8, "security": 7,
        "strike": 6, "attack": 6, "sanction": 5, "disarm": 8,
        "داعش": 10, "الحشد الشعبي": 9, "أمن": 7, "عسكري": 6, "هجوم": 7,
        "عقوبات": 6, "نزع السلاح": 8,
    },
    "경제": {
        "경제": 7, "원유": 9, "석유": 9, "유가": 8, "수출": 6, "정유": 8,
        "가스": 7, "에너지": 7, "투자": 7, "전력": 7, "전기": 7, "운송": 6,
        "oil": 9, "crude": 9, "brent": 9, "export": 6, "refin": 8, "gas": 7,
        "energy": 7, "investment": 7, "electricity": 7, "transport": 6,
        "نفط": 9, "خام": 9, "تصدير": 6, "مصفاة": 8, "غاز": 7, "طاقة": 7,
        "استثمار": 7, "اقتصاد": 7, "كهرباء": 7, "نقل": 6,
    },
    "정치": {
        "정치": 7, "국회": 8, "의회": 8, "국회의장": 10, "총리": 6, "장관": 4,
        "정부": 5, "외교": 7, "회담": 5, "방문": 4, "조정프레임워크": 10,
        "parliament": 8, "speaker": 7, "prime minister": 6, "minister": 4,
        "government": 5, "diplom": 7, "talks": 5, "visit": 4, "coordination framework": 10,
        "برلمان": 8, "مجلس النواب": 9, "رئيس الوزراء": 6, "وزير": 4,
        "حكومة": 5, "دبلوماس": 7, "مباحثات": 5, "زيارة": 4, "الإطار التنسيقي": 10,
    },
}

IRAQ_CORE_TERMS = (
    "이라크", "iraq", "العراق", "baghdad", "바그다드", "بغداد",
    "krg", "쿠르디스탄", "kurdistan", "الحكومة العراقية", "مجلس النواب العراقي",
)

WORLD_CONTEXT_TERMS = (
    "이란", "한국", "호르무즈", "이스라엘", "레바논", "예멘", "가자",
    "iran", "korea", "hormuz", "israel", "lebanon", "yemen", "gaza",
    "إيران", "كوريا", "هرمز", "إسرائيل", "لبنان", "اليمن", "غزة",
)


def classify_category(*, title: str = "", ai_title: str = "", summary: str = "",
                      original: str = "", excerpt: str = "", region: str = "",
                      current_category: str = "미분류") -> str:
    """Return a dashboard category, preserving explicit editorial categories."""
    if current_category in VALID_CATEGORIES and current_category != "세계":
        return current_category
    if region == "세계" or current_category == "세계":
        return "세계"

    headline = f"{ai_title} {title}".lower()
    if (any(term in headline for term in WORLD_CONTEXT_TERMS)
            and not any(term in headline for term in IRAQ_CORE_TERMS)):
        return "세계"
    body = f"{summary} {excerpt} {original[:4000]}".lower()
    scores = {}
    for category, terms in CATEGORY_TERMS.items():
        scores[category] = sum(
            weight * (3 if term in headline else 1)
            for term, weight in terms.items()
            if term in headline or term in body
        )

    best = max(scores, key=scores.get)
    return best if scores[best] else "정치"


def backfill_categories() -> dict[str, int]:
    counts = {category: 0 for category in VALID_CATEGORIES}
    with closing(sqlite3.connect(DB_PATH)) as connection:
        connection.row_factory = sqlite3.Row
        ensure_schema(connection)
        rows = connection.execute(
            "SELECT id,title,ai_title,summary,original,excerpt,region,category FROM articles "
            "WHERE report_status='included' AND (category IS NULL OR category='' OR category='미분류')"
        ).fetchall()
        for row in rows:
            category = classify_category(
                title=row["title"] or "", ai_title=row["ai_title"] or "",
                summary=row["summary"] or "", original=row["original"] or "",
                excerpt=row["excerpt"] or "", region=row["region"] or "",
                current_category=row["category"] or "미분류",
            )
            connection.execute("UPDATE articles SET category=? WHERE id=?", (category, row["id"]))
            counts[category] += 1
        connection.commit()
    return {category: count for category, count in counts.items() if count}


if __name__ == "__main__":
    print(backfill_categories())
