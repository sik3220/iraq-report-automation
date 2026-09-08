import re

import requests
from bs4 import BeautifulSoup


REQUEST_TIMEOUT = 15
MIN_PARAGRAPH_LENGTH = 40
MIN_ARTICLE_LENGTH = 200

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
    "ليصلك المزيد من الأخبار",
    "اشترك بقناتنا",
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
        ),
        "Accept-Language": "ar,en;q=0.9",
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
    used_story_fallback = False

    for paragraph in soup.find_all("p"):
        text = clean_text(
            paragraph.get_text(" ", strip=True)
        )

        if is_valid_paragraph(text):
            paragraphs.append(text)

    # INA 기사 중 일부는 일반적인 <p> 문단 대신
    # `.box.story.fullstory` 컨테이너 안에 텍스트 블록을 직접 둔다.
    # 해당 컨테이너가 있고 기존 추출 결과가 짧을 때만 보조 경로로 사용한다.
    if len("\n\n".join(paragraphs)) < MIN_ARTICLE_LENGTH:
        story = soup.select_one(".box.story.fullstory")
        if story:
            used_story_fallback = True
            for line in story.get_text("\n", strip=True).splitlines():
                text = clean_text(line)
                if is_valid_paragraph(text):
                    paragraphs.append(text)

    # 중복 문단 제거
    unique_paragraphs = list(dict.fromkeys(paragraphs))

    article_text = "\n\n".join(unique_paragraphs)
    minimum_length = 80 if used_story_fallback else MIN_ARTICLE_LENGTH
    if len(article_text) < minimum_length:
        raise ValueError("기사 본문을 충분히 확보하지 못함")
    return article_text


if __name__ == "__main__":
    test_url = (
        "https://www.bbc.co.uk/news/articles/"
        "c1m1xm8ykk2o"
    )

    article_text = fetch_article_text(test_url)

    print(article_text[:3000])
    print()
    print(f"본문 길이: {len(article_text)}자")