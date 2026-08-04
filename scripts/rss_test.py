import feedparser

RSS_URL = "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml"

feed = feedparser.parse(RSS_URL)

print("기사 수:", len(feed.entries))

for article in feed.entries[:5]:
    print("-" * 60)
    print("제목:", article.get("title", "제목 없음"))
    print("링크:", article.get("link", "링크 없음"))
    