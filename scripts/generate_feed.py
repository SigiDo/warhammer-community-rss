
import os
import xml.etree.ElementTree as ET
from urllib.request import Request, urlopen
from email.utils import formatdate
from datetime import datetime, timezone
from html import unescape

SOURCE_URL = "https://pikeuk.azurewebsites.net/warcom.rss"
OUTPUT_FILE = "docs/feed.xml"
MAX_ITEMS = 50

def get_text(item, *names):
    for name in names:
        element = item.find(name)
        if element is not None and element.text:
            return element.text.strip()
    return ""

def main():
    request = Request(
        SOURCE_URL,
        headers={"User-Agent": "WarhammerCommunityRSS/1.0"}
    )

    with urlopen(request, timeout=30) as response:
        source = ET.fromstring(response.read())

    # Supporte les flux RSS 2.0 et Atom.
    items = source.findall(".//item")
    if not items:
        items = [
            element for element in source.iter()
            if element.tag.endswith("}entry")
            or element.tag == "entry"
        ]

    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = (
        "Warhammer Community — English News"
    )
    ET.SubElement(channel, "link").text = (
        "https://www.warhammer-community.com/en-gb/"
    )
    ET.SubElement(channel, "description").text = (
        "Latest English-language Warhammer Community articles."
    )
    ET.SubElement(channel, "lastBuildDate").text = formatdate(
        datetime.now(timezone.utc).timestamp(), usegmt=True
    )

    count = 0
    for item in items:
        title = get_text(item, "title")
        link = get_text(item, "link")
        guid = get_text(item, "guid", "id")
        description = get_text(item, "description", "summary", "content")

        # Atom utilise généralement un lien dans un attribut href.
        if not link:
            for element in item.iter():
                if element.tag.endswith("}link") or element.tag == "link":
                    link = element.attrib.get("href", "")
                    if link:
                        break

        if not title or not link:
            continue

        entry = ET.SubElement(channel, "item")
        ET.SubElement(entry, "title").text = unescape(title)
        ET.SubElement(entry, "link").text = link
        ET.SubElement(entry, "guid", isPermaLink="true").text = guid or link
        ET.SubElement(entry, "description").text = unescape(description)

        pub_date = get_text(
            item, "pubDate", "published", "updated", "date"
        )
        if pub_date:
            ET.SubElement(entry, "pubDate").text = pub_date

        count += 1
        if count >= MAX_ITEMS:
            break

    if count == 0:
        raise RuntimeError(
            "Aucun article trouvé. Vérifie le flux source et sa structure."
        )

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    ET.ElementTree(rss).write(
        OUTPUT_FILE, encoding="utf-8", xml_declaration=True
    )
    print(f"Flux généré : {count} articles.")

if __name__ == "__main__":
    main()
