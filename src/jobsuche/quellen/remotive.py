"""Remotive: API für Remote-Stellen, gefiltert auf Deutschland/Europa/weltweit."""

import logging
import re

import requests

from jobsuche.bewertung import RELEVANTE_BERUFE
from jobsuche.modell import Stelle
from jobsuche.text import kuerze, strip_html

log = logging.getLogger(__name__)

API_URL = "https://remotive.com/api/remote-jobs"
NAME = "Remotive.com"
SUCHBEGRIFFE = [
    "software developer", "softwareentwickler", "anwendungsentwicklung",
    "junior developer", "fachinformatiker",
]

# Bewerberstandort, den die Stelle verlangt: nur DE/EU/weltweit
STANDORT_OK = re.compile(
    r"(germany|deutschland|europe|eu\b|worldwide|anywhere|global"
    r"|remote|latin america|emea|international)",
    re.IGNORECASE,
)


def suche() -> list[Stelle]:
    stellen: list[Stelle] = []
    gesehen: set[str] = set()
    for begriff in SUCHBEGRIFFE:
        try:
            antwort = requests.get(
                API_URL, params={"category": "software-dev", "search": begriff, "limit": 50}, timeout=20,
            )
            antwort.raise_for_status()
            jobs = antwort.json().get("jobs", [])
        except (requests.RequestException, ValueError) as fehler:
            log.warning("Remotive '%s': %s", begriff, fehler)
            continue
        stellen.extend(parse_jobs(jobs, gesehen))
    return stellen


def parse_jobs(jobs: list[dict], gesehen: set[str]) -> list[Stelle]:
    stellen = []
    for job in jobs:
        job_id = str(job.get("id", ""))
        if job_id in gesehen:
            continue
        if not RELEVANTE_BERUFE.search(f'{job.get("title", "")} {job.get("description", "")}'.lower()):
            continue
        standort = job.get("candidate_required_location", "") or ""
        if standort and not STANDORT_OK.search(standort):
            continue

        gesehen.add(job_id)
        beschreibung = strip_html(job.get("description", ""))
        stellen.append(Stelle(
            titel=job.get("title", ""),
            unternehmen=job.get("company_name", ""),
            adresse=f'{job.get("company_name", "")} – {standort or "Remote"}',
            beschreibung=kuerze(beschreibung, 300),
            voraussetzungen=kuerze(beschreibung, 400),
            gehalt=job.get("salary", "k.A.") or "k.A.",
            remote=True,
            homeoffice=f"100% Remote ({standort})" if standort else "100% Remote",
            arbeitszeit=job.get("job_type", ""),
            veroeffentlicht=(job.get("publication_date", "") or "")[:10],
            url=job.get("url", ""),
            quelle=NAME,
        ))
    return stellen
