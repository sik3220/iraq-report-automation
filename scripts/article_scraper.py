import requests
from bs4 import BeautifulSoup


def fetch_article_text(url: str) -> str:
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
        timeout=15,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    paragraphs = soup.find_all("p")

    article_text = "\n".join(
        paragraph.get_text(" ", strip=True)
        for paragraph in paragraphs
        if paragraph.get_text(" ", strip=True)
    )

    return article_text


if __name__ == "__main__":
    test_url = (
        "https://www.bbc.co.uk/news/articles/"
        "c1m1xm8ykk2o"
    )

    text = fetch_article_text(test_url)

    print(text[:2000])