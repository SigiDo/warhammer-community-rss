
import json
import os
import re
import xml.etree.ElementTree as ET

from datetime import datetime, timezone
from email.utils import format_datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_URL = "https://www.warhammer-community.com/api/search/news/"
OUTPUT_FILE = "docs/feed.xml"
MAX_ITEMS = 30
PAGE_SIZE = 16
MAX_PAGES = 3


def fetch_news(page):
    payload = {
        "sortBy": "date_desc",
        "category": "",
        "collections": ["articles"],
        "game_systems": [],
        "index": "news",
        "locale": "en-gb",
        "page": page,
        "perPage": PAGE_SIZE,
        "topics": [],
    }

    body = json.dumps(payload).encode("utf-8")

    request = Request(
        API_URL,
        data=body,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": "https://www.warhammer-community.com",
            "Referer": (
                "https://www.warhammer-community.com/"
                "en-gb/all-news-and-features/"
            ),
        },
        method="POST",
    )

    print(f"Requesting API page {page}...")

    with urlopen(request, timeout=30) as response:
        raw = response.read().decode(
            "utf-8",
            errors="replace",
        )
        print("HTTP status:", response.status)
        print("Content-Type:", response.headers.get("Content-Type"))

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        print("Response preview:", raw[:1000])
        raise RuntimeError(
            "The API response was not valid JSON."
        ) from error

    if not isinstance(data, dict):
        raise RuntimeError(
            "Unexpected API response: expected a JSON object."
        )

    news = data.get("news")

    if not isinstance(news, list):
        print("API response keys:", list(data.keys()))
        print("Response preview:", json.dumps(data)[:1500])
        raise RuntimeError(
            "The API response does not contain the expected 'news' list."
        )

    print(f"Articles returned on page {page}: {len(news)}")
    return news


def parse_date(value):
    if not value:
        return None

    value = str(value).strip()

    # The API may return dates such as "08 Sep 25".
    for date_format in ("%d %b %y", "%d %b %Y"):
        try:
            parsed = datetime.strptime(value, date_format)
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    try:
        iso_value = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(iso_value)

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def clean_text(value):
    if not isinstance(value, str):
        return ""

    value = re.sub(r"<[^>]*>", " ", value)
    return " ".join(value.split())


def main():
    articles = []
    seen_links = set()

    for page in range(MAX_PAGES):
        try:
            news = fetch_news(page)
        except (HTTPError, URLError, TimeoutError) as error:
            raise RuntimeError(
                f"Could not retrieve API page {page}: {error}"
            ) from error

        if not news:
            print("No more articles available.")
            break

        for entry in news:
            if not isinstance(entry, dict):
                continue

            title = clean_text(entry.get("title"))
            uri = entry.get("uri")

            if not title or not isinstance(uri, str):
                continue

            if not uri.startswith("/articles/"):
                continue

            link = "https://www.warhammer-community.com" + uri

            if link in seen_links:
                continue

            seen_links.add(link)

            articles.append({
                "title": title,
                "link": link,
                "date": entry.get("date", ""),
                "description": clean_text(
                    entry.get("excerpt", "")
                ),
            })

        if len(articles) >= MAX_ITEMS:
            break

    if not articles:
        raise RuntimeError(
            "No articles were found. Check the API response above."
        )

    articles.sort(
        key=lambda article: parse_date(article["date"])
        or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    articles = articles[:MAX_ITEMS]

    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text = (
        "Warhammer Community - News"
    )
    ET.SubElement(channel, "link").text = (
        "https://www.warhammer-community.com/en-gb/"
        "all-news-and-features/"
    )
    ET.SubElement(channel, "description").text = (
        "Latest Warhammer Community articles."
    )
    ET.SubElement(channel, "language").text = "en-gb"
    ET.SubElement(channel, "lastBuildDate").text = (
        format_datetime(datetime.now(timezone.utc))
    )

    for article in articles:
        item = ET.SubElement(channel, "item")

        ET.SubElement(item, "title").text = article["title"]
        ET.SubElement(item, "link").text = article["link"]
        ET.SubElement(item, "guid", isPermaLink="true").text = (
            article["link"]
        )

        if article["description"]:
            ET.SubElement(item, "description").text = (
                article["description"]
            )

        published = parse_date(article["date"])
        if published:
            ET.SubElement(item, "pubDate").text = (
                format_datetime(published)
            )

    os.makedirs("docs", exist_ok=True)

    ET.ElementTree(rss).write(
        OUTPUT_FILE,
        encoding="utf-8",
        xml_declaration=True,
    )

    print()
    print("SUCCESS: RSS feed generated.")
    print("Articles written:", len(articles))
    print("Output file:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
