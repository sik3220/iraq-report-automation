import os

from dotenv import load_dotenv
from openai import OpenAI

# .env 읽기
load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


def summarize_article(article: str):
    response = client.responses.create(
        model="gpt-5.5",
        input=f"""
다음 기사를 한국어로 한 문장으로 요약해.

기사:
{article}
"""
    )

    return response.output_text


if __name__ == "__main__":
    article = """
Donald Trump said negotiations with Iran will resume next week.
"""

    result = summarize_article(article)

    print(result)