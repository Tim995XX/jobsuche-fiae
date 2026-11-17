"""Bundesagentur für Arbeit: Jobsuche-API (REST, JSON).

Die API ist öffentlich; der Schlüssel "jobboerse-jobsuche" ist im Web-Portal der BA
eingebettet, OAuth ist nicht nötig. `page` beginnt bei 1, nicht bei 0.
"""

import logging
import time
from urllib.parse import urlencode

import requests

from jobsuche.modell import Stelle

log = logging.getLogger(__name__)

API_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs"
API_HEADERS = {"X-API-Key": "jobboerse-jobsuche", "Accept": "application/json"}
NAME = "Bundesagentur f. Arbeit"

SUCHBEGRIFFE = [
    "Fachinformatiker Anwendungsentwicklung",
    "Softwareentwickler",
    "Anwendungsentwickler",
]
MAX_ERGEBNISSE = 100
ERLAUBTE_UMKREISE = (5, 10, 25, 50, 100, 150, 200)  # andere Werte lehnt die API ab


def suche(ort: str, umkreis_km: int) -> list[Stelle]:
    """Alle Suchbegriffe im Umkreis des Orts, dazu Homeoffice-Stellen deutschlandweit."""
    stellen: list[Stelle] = []
    for begriff in SUCHBEGRIFFE:
        params = {
            "was": begriff, "wo": ort, "umkreis": umkreis_km,
            "angebotsart": 1,  # 1 = Arbeitsstelle
            "page": 1, "size": MAX_ERGEBNISSE,
        }
        stellen.extend(_abfrage(params, ist_remote=False))
        time.sleep(0.4)  # höflicher Abstand zwischen Anfragen

    params = {
        "was": "Fachinformatiker Anwendungsentwicklung",
        "angebotsart": 1, "arbeitszeit": "ho",  # ho = Homeoffice
        "page": 1, "size": MAX_ERGEBNISSE,
    }
    stellen.extend(_abfrage(params, ist_remote=True))
    return stellen


def _abfrage(params: dict, ist_remote: bool) -> list[Stelle]:
    try:
        antwort = requests.get(API_URL, params=params, headers=API_HEADERS, timeout=25)
        antwort.raise_for_status()
        daten = antwort.json()
    except (requests.RequestException, ValueError) as fehler:
        log.warning("BA API: %s", fehler)
        return []
    return parse_ergebnisse(daten, ist_remote)


def parse_ergebnisse(daten: dict, ist_remote: bool) -> list[Stelle]:
    """Antwort der API (v6) in Stellen umwandeln."""
    return [_parse_eintrag(eintrag, ist_remote) for eintrag in daten.get("ergebnisliste", [])]


def _parse_eintrag(eintrag: dict, ist_remote: bool) -> Stelle:
    # v6: "firma" ist ein String, der Ort steht unter stellenlokationen[0].adresse
    unternehmen = eintrag.get("firma", "") or ""
    lokationen = eintrag.get("stellenlokationen") or [{}]
    adresse_roh = lokationen[0].get("adresse", {}) or {}

    strasse = adresse_roh.get("strasse", "") or ""
    if strasse.lower() in ("null", "none", ""):
        strasse = ""
    plz_ort = f'{adresse_roh.get("plz", "")} {adresse_roh.get("ort", "")}'.strip()

    gehalt = "k.A."
    von, bis = eintrag.get("gehaltsspanneVon"), eintrag.get("gehaltsspanneBis")
    if von and bis:
        gehalt = f"{von:,.0f} - {bis:,.0f} €".replace(",", ".")

    veroeffentlicht = (
        eintrag.get("veroeffentlichungszeitraum", {}).get("von", "")
        or eintrag.get("datumErsteVeroeffentlichung", "")
        or ""
    )[:10]

    return Stelle(
        titel=eintrag.get("stellenangebotsTitel", ""),
        unternehmen=unternehmen,
        adresse=", ".join(filter(None, [unternehmen, strasse, plz_ort])),
        beschreibung="→ Volltext: Arbeitsagentur-Website (URL)",
        voraussetzungen="Quereinstieg geeignet" if eintrag.get("quereinstiegGeeignet") else "",
        gehalt=gehalt,
        remote=ist_remote,
        homeoffice="Homeoffice möglich" if ist_remote else "",
        arbeitszeit="Vollzeit" if eintrag.get("arbeitszeitVollzeit") else "Teilzeit",
        veroeffentlicht=veroeffentlicht,
        url=f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{eintrag.get('referenznummer', '')}",
        quelle=NAME,
    )


def direktlink(suchbegriff: str, ort: str, umkreis_km: int) -> str:
    """Link auf die Suche im Browser, falls die API nicht erreichbar ist."""
    params = {"was": suchbegriff, "wo": ort, "umkreis": umkreis_km}
    return f"https://www.arbeitsagentur.de/jobsuche/suche?{urlencode(params)}"
