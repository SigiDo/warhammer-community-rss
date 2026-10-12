
import json
import os
import re
import xml.etree.ElementTree as ET

from datetime import datetime, timezone
from email.utils import format_datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen


API_URL = "https://www.warhammer-community.com/api/search/news/"
SITE_URL = "https://www.warhammer-community.com/"
OUTPUT_FILE = "docs/feed.xml"
MAX_ITEMS = 30
MAX_PAGES = 3


def fetch_json(page):
    params = urlencode({
        "page": page,
        "sortby": "date_desc",
    })

    url = API_URL + "?" + params

    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(compatible; WarhammerCommunityRSS/1.0)"
            ),
            "Accept": "application/json",
            "Accept-Language": "en-GB,en;q=0.9",
        },
    )

    print("API request:", url)

    with urlopen(request, timeout=30) as response:
        body = response.read().decode(
            "utf-8",
            errors="replace",
        )

        print("HTTP status:", response.status)
        print("Content-Type:", response.headers.get("Content-Type"))

    try:
        return json.loads(body)
    except json.JSONDecodeError as error:
        print("API response is not valid JSON.")
        print("Response preview:", body[:1000])
        raise RuntimeError(
            "The Warhammer Community API did not return JSON."
        ) from error


def find_article_objects(data):
    """Find article-like objects anywhere in the API response."""
    found = []

    def walk(value):
        if isinstance(value, dict):
            title = (
                value.get("title")
                or value.get("headline")
            )

            raw_url = (
                value.get("uri")
                or value.get("url")
                or value.get("link")
                or value.get("path")
            )

            if isinstance(title, str) and isinstance(raw_url, str):
                title = " ".join(title.split())
                link = urljoin(SITE_URL, raw_url.strip())

                if (
                    title
                    and link.startswith("https://")
                    and "warhammer-community.com" in link
                    and "/articles/" in link
                ):
                    found.append({
                        "title": title,
                        "link": link,
                        "date": (
                            value.get("datePublished")
                            or value.get("publishedAt")
                            or value.get("published_at")
                            or value.get("date")
                            or value.get("created_at")
                            or value.get("createdAt")
                        ),
                        "description": (
                            value.get("excerpt")
                            or value.get("description")
                            or value.get("summary")
                            or ""
                        ),
                    })

            for child in value.values():
                if isinstance(child, (dict, list)):
                    walk(child)

        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(data)
    return found


def parse_date(value):
    if not value:
        return None

    try:
        text = str(value).strip()

        if text.endswith("Z"):
            text = text[:-1] + "+00:00"

        result = datetime.fromisoformat(text)

        if result.tzinfo is None:
            result = result.replace(tzinfo=timezone.utc)

        return result.astimezone(timezone.utc)

    except (ValueError, TypeError):
        return None


def clean_description(value):
    if not isinstance(value, str):
        return ""

    value = re.sub(r"<[^>]+>", " ", value)
    value = " ".join(value.split())
    return value[:2000]


def main():
    articles = []
    seen = set()

    for page in range(1, MAX_PAGES + 1):
        try:
            data = fetch_json(page)
        except (HTTPError, URLError, TimeoutError) as error:
            if page == 1:
                raise RuntimeError(
                    f"Could not access the news API: {error}"
                ) from error

            print("Could not fetch page", page, ":", error)
            break

        page_articles = find_article_objects(data)
        new_count = 0

        for article in page_articles:
            link = article["link"]

            if link not in seen:
                seen.add(link)
                articles.append(article)
                new_count += 1

        print(
            f"Page {page}: "
            f"{len(page_articles)} detected, "
            f"{new_count} new articles"
        )

        if new_count == 0:
            break

        if len(articles) >= MAX_ITEMS:
            break

    if not articles:
        raise RuntimeError(
            "No articles were detected in the API response. "
            "The API structure may have changed. "
            "Check the diagnostic messages above."
        )

    # Sort by publication date when available.
    articles.sort(
        key=lambda item: parse_date(item["date"])
        or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text = (
        "Warhammer Community - Actualités"
    )
    ET.SubElement(channel, "link").text = (
        "https://www.warhammer-community.com/en-gb/"
    )
    ET.SubElement(channel, "description").text = (
        "Dernières actualités de Warhammer Community."
    )
    ET.SubElement(channel, "language").text = "en-gb"
    ET.SubElement(channel, "lastBuildDate").text = (
        format_datetime(datetime.now(timezone.utc))
    )

    for article in articles[:MAX_ITEMS]:
        item = ET.SubElement(channel, "item")

        ET.SubElement(item, "title").text = article["title"]
        ET.SubElement(item, "link").text = article["link"]
        ET.SubElement(item, "guid", isPermaLink="true").text = (
            article["link"]
        )

        description = clean_description(article["description"])
        if description:
            ET.SubElement(item, "description").text = description

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
    print("Articles written:", min(len(articles), MAX_ITEMS))
    print("Output file:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
