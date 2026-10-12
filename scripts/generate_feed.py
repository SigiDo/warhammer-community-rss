
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.parse import urljoin
from datetime import datetime, timezone
from email.utils import format_datetime
import os
import xml.etree.ElementTree as ET

SOURCE_URL = "https://www.warhammer-community.com/en-gb/"
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
            attrs = dict(attrs)
            self.current_href = attrs.get("href")
            self.current_text = []

    def handle_data(self, data):
        if self.current_href is not None:
            self.current_text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.current_href:
            href = urljoin(SOURCE_URL, self.current_href)
            title = " ".join("".join(self.current_text).split())

            if (
                "/en-gb/articles/" in href
                and title
                and title.lower() != "image"
            ):
                self.articles.append((title, href))

            self.current_href = None
            self.current_text = []


def main():
    request = Request(
        SOURCE_URL,
        headers={"User-Agent": "Mozilla/5.0 (compatible; CommunityRSS/1.0)"}
    )

    with urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8", errors="replace")

    parser = ArticleParser()
    parser.feed(html)

    # Supprime les doublons en conservant le premier titre trouvé.
    unique = []
    seen = set()

    for title, link in parser.articles:
        if link not in seen:
            seen.add(link)
            unique.append((title, link))

    unique = unique[:MAX_ITEMS]

    if not unique:
        raise RuntimeError(
            "Aucun article détecté sur le site officiel. "
            "La structure HTML a peut-être changé."
        )

    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text = (
        "Warhammer Community - English News"
    )
    ET.SubElement(channel, "link").text = SOURCE_URL
    ET.SubElement(channel, "description").text = (
        "Latest articles detected on the official Warhammer Community website."
    )
    ET.SubElement(channel, "lastBuildDate").text = format_datetime(
        datetime.now(timezone.utc)
    )

    for title, link in unique:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = title
        ET.SubElement(item, "link").text = link
        ET.SubElement(item, "guid", isPermaLink="true").text = link

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    ET.ElementTree(rss).write(
        OUTPUT_FILE,
        encoding="utf-8",
        xml_declaration=True
    )

    print(f"RSS generated successfully: {len(unique)} articles.")


if __name__ == "__main__":
    main()
