
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.parse import urljoin
from datetime import datetime, timezone
from email.utils import format_datetime
import os
import xml.etree.ElementTree as ET

SOURCE_URL = (
    "https://www.warhammer-community.com/en-gb/"
    "all-news-and-features/?page=1&sortby=date_desc"
)
OUTPUT_FILE = "docs/feed.xml"
MAX_ITEMS = 30


class ArticleParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.articles = []
        self.current_href = None
        self.current_text = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            attributes = dict(attrs)
            href = attributes.get("href")

            if href:
                self.current_href = href
                self.current_text = []

    def handle_data(self, data):
        if self.current_href is not None:
            self.current_text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.current_href:
            title = " ".join("".join(self.current_text).split())
            link = urljoin(SOURCE_URL, self.current_href)

            if (
                "/en-gb/articles/" in link
                and title
                and title.lower() != "image"
            ):
                self.articles.append((title, link))

            self.current_href = None
            self.current_text = []


def main():
    print("Fetching:", SOURCE_URL)

    request = Request(
        SOURCE_URL,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; CommunityRSS/1.0)",
            "Accept-Language": "en-GB,en;q=0.9",
        },
    )

    with urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8", errors="replace")
        print("HTTP status:", response.status)
        print("Final URL:", response.geturl())

    print("HTML length:", len(html))

    parser = ArticleParser()
    parser.feed(html)

    print("First 20 detected links:")
    for title, link in parser.articles[:20]:
        print(repr(title), link)

    # Supprimer les doublons en conservant le premier titre trouvé.
    unique_articles = []
    seen_links = set()

    for title, link in parser.articles:
        if link not in seen_links:
            seen_links.add(link)
            unique_articles.append((title, link))

    articles = unique_articles[:MAX_ITEMS]

    if not articles:
        raise RuntimeError(
            "No articles detected. Check the HTML output: "
            "the site may require JavaScript or may have changed."
        )

    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text = (
        "Warhammer Community - English News"
    )
    ET.SubElement(channel, "link").text = (
        "https://www.warhammer-community.com/en-gb/"
    )
    ET.SubElement(channel, "description").text = (
        "Articles detected on the official Warhammer Community website."
    )
    ET.SubElement(channel, "lastBuildDate").text = format_datetime(
        datetime.now(timezone.utc)
    )

    for title, link in articles:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = title
        ET.SubElement(item, "link").text = link
        ET.SubElement(item, "guid", isPermaLink="true").text = link

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    ET.ElementTree(rss).write(
        OUTPUT_FILE,
        encoding="utf-8",
        xml_declaration=True,
    )

    print(f"RSS generated successfully: {len(articles)} articles.")


if __name__ == "__main__":
    main()
