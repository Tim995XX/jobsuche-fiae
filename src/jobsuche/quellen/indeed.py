"""Indeed Deutschland: RSS-Feeds je Suchanfrage."""

import logging
import time
import xml.etree.ElementTree as ET
from urllib.parse import urlencode

import requests

from jobsuche.bewertung import RELEVANTE_BERUFE_TITEL
from jobsuche.modell import Stelle
from jobsuche.text import kuerze, rss_datum, rss_feld, strip_html

log = logging.getLogger(__name__)

NAME = "Indeed.de"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}


def suche(ort: str) -> list[Stelle]:
    suchen = [
        {"q": "Fachinformatiker Anwendungsentwicklung", "l": ort, "radius": 30},
        {"q": "Softwareentwickler", "l": ort, "radius": 30},
        {"q": "Junior Entwickler", "l": ort, "radius": 30},
        {"q": "Anwendungsentwickler", "l": ort, "radius": 30},
        {"q": "Fachinformatiker Anwendungsentwicklung remote", "l": ""},
        {"q": "Junior Developer remote Deutschland", "l": ""},
    ]
    stellen: list[Stelle] = []
    gesehen: set[str] = set()
    for anfrage in suchen:
        params = {
            "q": anfrage["q"], "l": anfrage.get("l", ""), "radius": anfrage.get("radius", 0),
            "sort": "date", "limit": 25, "fromage": 60,  # höchstens 60 Tage alt
        }
        params = {k: v for k, v in params.items() if v}
        try:
            antwort = requests.get(f"https://de.indeed.com/rss?{urlencode(params)}", timeout=20, headers=HEADERS)
            if antwort.status_code != 200:
                continue
            wurzel = ET.fromstring(antwort.content)
        except (requests.RequestException, ET.ParseError) as fehler:
            log.warning("Indeed '%s': %s", anfrage["q"], fehler)
            continue
        stellen.extend(parse_feed(wurzel, gesehen, standard_ort=anfrage.get("l", "Remote")))
        time.sleep(0.5)
    return stellen


def parse_feed(wurzel: ET.Element, gesehen: set[str], standard_ort: str) -> list[Stelle]:
    stellen = []
    for item in wurzel.iter("item"):
        link = rss_feld(item, "link") or rss_feld(item, "guid")
        titel = rss_feld(item, "title")
        if not link or link in gesehen or not RELEVANTE_BERUFE_TITEL.search(titel):
            continue
        gesehen.add(link)
        ort = rss_feld(item, "source") or standard_ort
        beschreibung = strip_html(rss_feld(item, "description"))

        # Indeed schreibt die Firma oft in den Titel: "Titel - Firma"
        unternehmen = ""
        if " - " in titel:
            titel, unternehmen = (teil.strip() for teil in titel.rsplit(" - ", 1))

        ist_remote = "remote" in f"{titel} {beschreibung}".lower()
        stellen.append(Stelle(
            titel=titel,
            unternehmen=unternehmen,
            adresse=f"{unternehmen}, {ort}" if unternehmen else ort,
            beschreibung=kuerze(beschreibung, 300),
            remote=ist_remote,
            homeoffice="Remote möglich" if ist_remote else "",
            veroeffentlicht=rss_datum(rss_feld(item, "pubDate")),
            url=link,
            quelle=NAME,
        ))
    return stellen
