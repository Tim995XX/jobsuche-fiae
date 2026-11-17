"""Kleine Textwerkzeuge: HTML entfernen, kürzen, RSS-Felder und -Datumsangaben lesen."""

import re
import xml.etree.ElementTree as ET
from datetime import datetime

_HTML_ENTITAETEN = [
    ("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'"),
]


def strip_html(text: str) -> str:
    """HTML in lesbaren Text umwandeln; Block-Elemente werden zu Zeilenumbrüchen."""
    text = re.sub(r"<br\s*/?>|</p>|</li>|</div>|</h[1-6]>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    for entitaet, zeichen in _HTML_ENTITAETEN:
        text = text.replace(entitaet, zeichen)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def kuerze(text: str, n: int = 200) -> str:
    """Leerraum zusammenfassen und auf höchstens n Zeichen an einer Wortgrenze kürzen."""
    text = " ".join(text.split())
    return text[:n].rsplit(" ", 1)[0] + " …" if len(text) > n else text


def rss_feld(item: ET.Element, name: str) -> str:
    """Text eines Kindelements eines RSS-<item>, leer wenn es fehlt."""
    element = item.find(name)
    return (element.text or "").strip() if element is not None else ""


def rss_datum(pub_date: str) -> str:
    """RSS-pubDate ("Mon, 03 Nov 2026 10:00:00 +0000") als "2026-11-03"."""
    if not pub_date:
        return ""
    try:
        return datetime.strptime(pub_date[:25], "%a, %d %b %Y %H:%M:%S").strftime("%Y-%m-%d")
    except ValueError:
        return pub_date[:10]
