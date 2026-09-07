import json
import os
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI

from name_mapper import replace_names
from report_style import REPORT_INSTRUCTIONS, normalize_summary, strip_terminal_period

MAX_ARTICLE_LENGTH = 12000


@dataclass(frozen=True)
class ReportArticle:
    status: str
    reason: str
    title: str
    summary: str


def parse_report(result: str, *, has_body: bool = True) -> ReportArticle:
    data = json.loads(result)
    if not isinstance(data, dict):
        raise ValueError("AI 출력은 JSON 객체여야 합니다")
    if data.get("status") not in ("included", "excluded", "review"):
        raise ValueError("기사 선정 상태가 올바르지 않습니다")
    if not isinstance(data.get("reason"), str) or not data["reason"].strip():
        raise ValueError("기사 선정 근거가 없습니다")
    if not isinstance(data.get("title"), str) or not data["title"].strip():
        raise ValueError("한국어 제목이 없습니다")
    if not has_body:
        data["summary"] = []
    lines = data.get("summary")
    if not isinstance(lines, list) or len(lines) > 2 or not all(isinstance(x, str) for x in lines):
        raise ValueError("추가 사실은 0~2줄이어야 합니다")
    if data["status"] != "included" and lines:
        raise ValueError("제외/검토 기사에는 요약을 작성하지 않습니다")
    return ReportArticle(
        status=data["status"],
        reason=strip_terminal_period(data["reason"]),
        title=strip_terminal_period(replace_names(data["title"])),
        summary="\n".join(normalize_summary([replace_names(x) for x in lines])),
    )


def analyze_article(title: str, article_text: str) -> ReportArticle:
    title = title.strip()
    # Stored BBC pages can contain a long unrelated recommendations footer.
    cleaned = article_text.split("Watch our pick of standout clips", 1)[0].strip()
    if not title and not cleaned:
        raise ValueError("분석할 기사 내용이 없습니다")
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY가 없습니다")
    client = OpenAI(api_key=api_key, timeout=90.0, max_retries=1)
    response = client.responses.create(
        model="gpt-5.5",
        instructions=REPORT_INSTRUCTIONS,
        input=json.dumps(
            {"source_title": title, "body": cleaned[:MAX_ARTICLE_LENGTH],
             "body_available": bool(cleaned)}, ensure_ascii=False
        ),
    )
    return parse_report(response.output_text.strip(), has_body=bool(cleaned))


def process_article(article_text: str) -> tuple[str, str]:
    """Compatibility helper; batch processing uses analyze_article for selection."""
    report = analyze_article("", article_text)
    return report.title, report.summary
