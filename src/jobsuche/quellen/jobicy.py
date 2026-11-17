"""Jobicy: RSS-Feeds mit Remote-Stellen."""

import logging
import xml.etree.ElementTree as ET

import requests

from jobsuche.bewertung import RELEVANTE_BERUFE_TITEL
from jobsuche.modell import Stelle
from jobsuche.text import kuerze, rss_datum, rss_feld, strip_html

log = logging.getLogger(__name__)

NAME = "Jobicy.com"
FEEDS = [
    "https://jobicy.com/?feed=job_feed&job_categories=devops-sysadmin&search_keywords=developer",
    "https://jobicy.com/?feed=job_feed&search_keywords=softwareentwickler",
    "https://jobicy.com/?feed=job_feed&search_keywords=anwendungsentwicklung",
    "https://jobicy.com/?feed=job_feed&search_keywords=junior+developer&job_types=full-time",
]


def suche() -> list[Stelle]:
    stellen: list[Stelle] = []
    gesehen: set[str] = set()
    for feed_url in FEEDS:
        try:
            antwort = requests.get(feed_url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            if antwort.status_code != 200:
                continue
            wurzel = ET.fromstring(antwort.content)
        except (requests.RequestException, ET.ParseError) as fehler:
            log.warning("Jobicy: %s", fehler)
            continue
        stellen.extend(parse_feed(wurzel, gesehen))
    return stellen


def parse_feed(wurzel: ET.Element, gesehen: set[str]) -> list[Stelle]:
    stellen = []
    for item in wurzel.iter("item"):
        titel = rss_feld(item, "title")
        link = rss_feld(item, "link")
        if link in gesehen:
            continue
        # Nur der Titel zählt: Fast jede Firmenbeschreibung erwähnt "developer",
        # auch bei Stellen im Marketing oder in der Buchhaltung.
        if not RELEVANTE_BERUFE_TITEL.search(titel):
            continue
        gesehen.add(link)
        stellen.append(Stelle(
            titel=titel,
            unternehmen=rss_feld(item, "author"),
            adresse="Remote (weltweit)",
            beschreibung=kuerze(strip_html(rss_feld(item, "description")), 300),
            remote=True,
            homeoffice="100% Remote",
            veroeffentlicht=rss_datum(rss_feld(item, "pubDate")),
            url=link,
            quelle=NAME,
        ))
    return stellen
