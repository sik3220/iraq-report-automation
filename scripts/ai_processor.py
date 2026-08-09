import os

from dotenv import load_dotenv
from openai import OpenAI
from name_mapper import replace_names


load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")

if not API_KEY:
    raise ValueError(
        "OPENAI_API_KEY가 없습니다. 프로젝트 루트의 .env 파일을 확인하세요."
    )

client = OpenAI(api_key=API_KEY)

# 한 기사당 API 비용과 불필요한 입력을 줄이기 위한 제한
MAX_ARTICLE_LENGTH = 12000


def process_article(article_text: str) -> tuple[str, str]:
    """기사 본문을 한국어 정보보고 형식으로 요약한다."""

    cleaned_text = article_text.strip()

    if not cleaned_text:
        raise ValueError("요약할 기사 내용이 없습니다.")

    # 지나치게 긴 기사는 앞부분을 기준으로 처리
    cleaned_text = cleaned_text[:MAX_ARTICLE_LENGTH]

    response = client.responses.create(
        model="gpt-5.5",
instructions="""
너는 대한민국 정부의 중동 담당 정보분석관이다.

입력된 기사 원문을 주간정보보고에 바로 사용할 수 있는 형식으로 한국어로 요약하라.

[작성 원칙]

1. 기사의 핵심 사실만 요약한다.
2. 기사에 없는 내용은 절대 추측하지 않는다.
3. 반복되는 내용은 제거한다.
4. 기자의 표현(언급했다, 설명했다, 전했다, 보도했다)은 사용하지 않는다.
5. 가장 중요한 사건을 먼저 작성하고, 인물보다 사건 중심으로 작성한다. 
6. 문장은 짧고 명확하게 작성한다.
7. 보고서 문체(~함, ~추진, ~발표, ~확인)를 사용한다.
8. 인명, 기관명, 국가명, 수치는 유지한다.
9. 핵심 내용을 1~2줄로 작성한다. 핵심만 전달 가능한 경우 한 줄만 작성한다.
10. 기사에 명확한 전망이 있을 경우에만 마지막 줄에 ☞ 로 작성한다.
11. 한국어 보고서 제목을 한 줄 작성한다.
12. 제목은 "주체 + 핵심 행위/결과" 중심으로 간결하게 작성한다.
13. 제목은 40자 내외로 작성한다.
14. 제목에는 기사에 없는 내용을 추가하지 않는다.
15. 주요 인물은 정해진 직책 표기를 사용한다.
16. "~가능성 있음" 대신 문맥에 따라 "~가능성 시사" 또는 "~가능성 고조" 로 작성한다.
17. 제목에 인물명이 포함된 경우, 핵심 내용에서는 해당 인물명을 반복하지 않는다.
18. 서로 다른 핵심 사실은 한 문장에 합치지 않고 각각 별도의 핵심 내용으로 작성한다.
19. "~됨", "~되었음" 등 수동형 종결 표현은 사용하지 않고 "~취소", "~추진", "~합의", "~발표" 등 명사형으로 간결하게 작성한다.
20. 제목에 이미 포함된 사실은 핵심 내용에서 반복하지 않는다. 핵심 내용에는 제목에 없는 추가 정보만 작성한다.

[출력 형식]

TITLE: 한국어 보고서 제목
SUMMARY:
* 핵심 내용
* 핵심 내용(필요한 경우)
""",
    input=f"""
아래 기사 원문을 정보보고 형식으로 요약하라.

[기사 원문]
{cleaned_text}
""",
    )

    result = response.output_text.strip()

    if not result:
        raise ValueError("AI가 빈 결과를 반환했습니다.")

    if "TITLE:" not in result or "SUMMARY:" not in result:
        raise ValueError("AI 출력 형식이 올바르지 않습니다.")

    title_part, summary_part = result.split("SUMMARY:", 1)

    ai_title = title_part.replace("TITLE:", "").strip()
    summary = summary_part.strip()

    ai_title = replace_names(ai_title)
    summary = replace_names(summary)

    return ai_title, summary


if __name__ == "__main__":
    test_article = """
Donald Trump said negotiations with Iran could resume next week.
He added that planned military strikes had been cancelled while talks
on a new agreement were progressing.
"""

    ai_title, summary = process_article(test_article)

    print("제목:", ai_title)
    print("요약:")
    print(summary)