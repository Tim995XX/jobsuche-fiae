"""Arbeitnow: Job-Board-API (REST, JSON), seitenweise abgerufen."""

import logging
import re
from datetime import datetime

import requests

from jobsuche.bewertung import RELEVANTE_BERUFE_TITEL
from jobsuche.modell import Stelle
from jobsuche.text import kuerze, strip_html

log = logging.getLogger(__name__)

API_URL = "https://www.arbeitnow.com/api/job-board-api"
NAME = "Arbeitnow.com"
MAX_SEITEN = 4

# Standorte, die für die Suche in Frage kommen (Stellen ohne Remote)
RELEVANTE_ORTE = re.compile(
    r"(germany|deutschland|leipzig|berlin|dresden|halle|sachsen"
    r"|worldwide|remote|europe|eu\b|global|international|\bde\b)",
    re.IGNORECASE,
)


def suche(ort: str) -> list[Stelle]:
    """Stellen am Ort und Remote-Stellen, ohne doppelte Einträge (gleicher Slug)."""
    stellen: list[Stelle] = []
    gesehen: set[str] = set()
    for filter_params in ({"location": ort}, {"remote": "true"}):
        for seite in range(1, MAX_SEITEN + 1):
            try:
                antwort = requests.get(API_URL, params={"page": seite, **filter_params}, timeout=20)
                antwort.raise_for_status()
                jobs = antwort.json().get("data", [])
            except (requests.RequestException, ValueError) as fehler:
                log.warning("Arbeitnow S.%d: %s", seite, fehler)
                break
            if not jobs:
                break
            stellen.extend(parse_jobs(jobs, gesehen))
    return stellen


def parse_jobs(jobs: list[dict], gesehen: set[str]) -> list[Stelle]:
    """Relevante Jobs einer Seite umwandeln; `gesehen` sammelt die Slugs über alle Seiten."""
    stellen = []
    for job in jobs:
        slug = job.get("slug", "")
        if slug in gesehen:
            continue
        if not RELEVANTE_BERUFE_TITEL.search(job.get("title", "")):
            continue
        ort = job.get("location", "")
        ist_remote = bool(job.get("remote"))
        if not ist_remote and not RELEVANTE_ORTE.search(ort):
            continue

        gesehen.add(slug)
        zeitstempel = job.get("created_at", 0)
        stellen.append(Stelle(
            titel=job.get("title", ""),
            unternehmen=job.get("company_name", ""),
            adresse=f'{job.get("company_name", "")}, {ort}',
            beschreibung=kuerze(strip_html(job.get("description", "")), 300),
            voraussetzungen=", ".join(job.get("tags", [])[:10]),
            remote=ist_remote,
            homeoffice="Ja" if ist_remote else "",
            arbeitszeit=", ".join(job.get("job_types", [])),
            veroeffentlicht=datetime.fromtimestamp(zeitstempel).strftime("%Y-%m-%d") if zeitstempel else "",
            url=job.get("url", ""),
            quelle=NAME,
        ))
    return stellen
