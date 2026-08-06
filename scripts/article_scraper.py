import re

import requests
from bs4 import BeautifulSoup


REQUEST_TIMEOUT = 15
MIN_PARAGRAPH_LENGTH = 40

# 기사 본문이 아닌 문구를 제거하기 위한 키워드
EXCLUDED_TEXTS = (
    "Copyright",
    "The BBC is not responsible",
    "Read about our approach",
    "Sign up",
    "Newsletter",
    "Get news",
    "Follow BBC",
    "Watch our pick",
    "Calls for information",
    "Related topics",
    "Related stories",
)


def clean_text(text: str) -> str:
    """불필요한 공백과 깨진 문자를 정리한다."""
    text = text.replace("\xa0", " ")
    text = text.replace("â", "-")
    text = text.replace("â", "'")
    text = text.replace("â", '"')
    text = text.replace("â", '"')

    return re.sub(r"\s+", " ", text).strip()


def is_valid_paragraph(text: str) -> bool:
    """기사 본문으로 사용할 문단인지 판단한다."""
    if len(text) < MIN_PARAGRAPH_LENGTH:
        return False

    if any(excluded in text for excluded in EXCLUDED_TEXTS):
        return False

    return True


def fetch_article_text(url: str) -> str:
    """기사 URL에서 본문 텍스트를 추출한다."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "Chrome/142.0 Safari/537.36"
        )
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # 기사와 무관한 영역 제거
    for element in soup(
        [
            "script",
            "style",
            "nav",
            "header",
            "footer",
            "aside",
            "form",
        ]
    ):
        element.decompose()

    paragraphs: list[str] = []

    for paragraph in soup.find_all("p"):
        text = clean_text(
            paragraph.get_text(" ", strip=True)
        )

        if is_valid_paragraph(text):
            paragraphs.append(text)

    # 중복 문단 제거
    unique_paragraphs = list(dict.fromkeys(paragraphs))

    return "\n\n".join(unique_paragraphs)


if __name__ == "__main__":
    test_url = (
        "https://www.bbc.co.uk/news/articles/"
        "c1m1xm8ykk2o"
    )

    article_text = fetch_article_text(test_url)

    print(article_text[:3000])
    print()
    print(f"본문 길이: {len(article_text)}자")