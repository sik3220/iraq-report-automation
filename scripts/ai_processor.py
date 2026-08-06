import os

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")

if not API_KEY:
    raise ValueError(
        "OPENAI_API_KEY가 없습니다. 프로젝트 루트의 .env 파일을 확인하세요."
    )

client = OpenAI(api_key=API_KEY)

# 한 기사당 API 비용과 불필요한 입력을 줄이기 위한 제한
MAX_ARTICLE_LENGTH = 12000


def summarize_article(article_text: str) -> str:
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
11. 제목은 작성하지 않는다.
12. 한 문장은 40자 내외로 작성한다.
13. "언급", "설명", "전했다", "밝혔다"와 같은 전달 표현을 사용하지 않는다.
14. 주어를 반복하지 말고 사건 중심으로 작성한다.

[출력 형식]

* 핵심 내용
* 핵심 내용
""",
    input=f"""
아래 기사 원문을 정보보고 형식으로 요약하라.

[기사 원문]
{cleaned_text}
""",
    )

    summary = response.output_text.strip()

    if not summary:
        raise ValueError("AI가 빈 요약을 반환했습니다.")

    return summary


if __name__ == "__main__":
    test_article = """
Donald Trump said negotiations with Iran could resume next week.
He added that planned military strikes had been cancelled while talks
on a new agreement were progressing.
"""

    result = summarize_article(test_article)
    print(result)