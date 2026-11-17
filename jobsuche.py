#!/usr/bin/env python3
"""
Jobsuche: Fachinformatiker Anwendungsentwicklung – Leipzig & Remote
Quellen: Bundesagentur für Arbeit (API), Arbeitnow (API), Jobicy (RSS), Remotive (API)
"""

import csv
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from urllib.parse import urlencode

import requests
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich import box

console = Console(width=230)

# ─── Konfiguration ────────────────────────────────────────────────────────────

ORT_LEIPZIG   = "Leipzig"
UMKREIS_KM    = 25   # BA API erlaubt nur: 5, 10, 25, 50, 100, 150, 200
MAX_ERGEBNISSE = 100
CSV_DATEI     = "stellen.csv"

BA_SUCHBEGRIFFE = [
    "Fachinformatiker Anwendungsentwicklung",
    "Softwareentwickler",
    "Anwendungsentwickler",
]

# ─── Datenmodell ─────────────────────────────────────────────────────────────

@dataclass
class Stelle:
    titel: str = ""
    unternehmen: str = ""
    adresse: str = ""
    beschreibung: str = ""
    voraussetzungen: str = ""
    gehalt: str = "k.A."
    remote: bool = False
    homeoffice: str = ""
    arbeitszeit: str = ""
    veroeffentlicht: str = ""
    url: str = ""
    quelle: str = ""
    einsteiger_score: int = 0
    einsteiger_tags: List[str] = field(default_factory=list)

# ─── Einsteiger-Bewertung ────────────────────────────────────────────────────

POSITIV_SIGNALE = [
    (r"\bberufseinsteiger\b",                4, "Berufseinsteiger"),
    (r"\beinsteiger(position)?\b",           3, "Einsteiger"),
    (r"\bjunior\b",                          3, "Junior"),
    (r"\bohne\b.{0,30}\bberufserfahrung\b",  4, "Ohne Erfahrung"),
    (r"\babsolvent(in)?\b",                  3, "Absolvent/in"),
    (r"\bberufsanf[äa]nger\b",              4, "Berufsanfänger"),
    (r"\bquereinsteig(er|ung)?\b",           2, "Quereinsteiger"),
    (r"\berste.{0,10}erfahrung(en)?\b",      2, "Erste Erfahrungen ok"),
    (r"\btrainee(programm)?\b",              2, "Trainee"),
    (r"\bfrisch.{0,30}ausgebild",            4, "Frisch ausgebildet"),
    (r"\bauch.{0,20}ohne erfahrung\b",       4, "Auch ohne Erfahrung"),
    (r"\bnachwuchs(kraft)?\b",               2, "Nachwuchs"),
    (r"\b0[-–]2 jahre?\b",                   2, "0–2 Jahre"),
    (r"\bausbildungsabschluss\b",            2, "Ausbildungsabschluss"),
    (r"\bwir bilden aus\b",                  2, "Bildet aus"),
    (r"\beinstieg.*willkommen\b",            3, "Einstieg willkommen"),
    (r"\bjob.?entry\b",                      2, "Entry-Level"),
    (r"\bentry.?level\b",                    2, "Entry-Level"),
    (r"\bgraduate\b",                        2, "Graduate"),
    (r"\bjunior.?developer\b",               3, "Junior Developer"),
    (r"\bjunior.?entwickler\b",              3, "Junior Entwickler"),
    # "Junior bis Senior", "Junior/Senior", "Junior – Senior": hebt den
    # Senior-Abzug wieder auf, da Einsteiger explizit angesprochen werden
    (r"\bjunior\b.{0,12}\bsenior\b",         3, "Junior bis Senior"),
]

# Stellen ohne Entwicklungsbezug (Vertrieb, Kundenbetreuung, Recruiting …)
# werden nach dem Sammeln komplett verworfen – nur der Titel zählt.
NICHT_ENTWICKLER_TITEL = re.compile(
    r"(\bsales\b|vertrieb|account\s*(manager|executive)|business\s+development"
    r"|customer\s+success|kundenbetreu|kundenberat|customer\s+support"
    r"|\brecruit|talent\s+acquisition|\bmarketing\b|sales\s+development)",
    re.IGNORECASE,
)


def ist_nicht_entwickler_stelle(stelle: "Stelle") -> bool:
    return bool(NICHT_ENTWICKLER_TITEL.search(stelle.titel or ""))

NEGATIV_SIGNALE = [
    (r"\bsenior\b",                                     3, "Senior"),
    (r"\bmehrj[äa]hrige.{0,20}(berufserfahrung|erfahrung)\b", 4, "Mehrjährige Erfahrung"),
    (r"\bmindestens [3-9] jahre?\b",                    4, "Min. 3+ Jahre"),
    (r"\b[3-9]\+\s*jahre?\b",                           4, "3+ Jahre"),
    (r"\b(lead|principal|head of|architect)\b",         3, "Leitungsposition"),
    (r"\bteam.?lead\b",                                 3, "Team Lead"),
    (r"\bteamleiter\b",                                 3, "Teamleiter"),
    (r"\berfahrener?\s+(entwickler|softwareentwickler)\b", 3, "Erfahrener Entwickler"),
    (r"\b(experte|expert)\b",                           2, "Experte erwartet"),
    (r"\b5\+\s*jahre?\b",                               4, "5+ Jahre"),
    (r"\bmindestens\s+5\b",                             4, "Min. 5 Jahre"),
]


def berechne_einsteiger_score(stelle: Stelle) -> tuple:
    text = f"{stelle.titel} {stelle.beschreibung} {stelle.voraussetzungen}".lower()
    score = 0
    tags = []
    for muster, punkte, label in POSITIV_SIGNALE:
        if re.search(muster, text, re.IGNORECASE):
            score += punkte
            tags.append(f"[green]+{label}[/green]")
    for muster, punkte, label in NEGATIV_SIGNALE:
        if re.search(muster, text, re.IGNORECASE):
            score -= punkte
            tags.append(f"[red]-{label}[/red]")
    return score, tags


def strip_html(text: str) -> str:
    text = re.sub(r"<br\s*/?>|</p>|</li>|</div>|</h[1-6]>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    for ent, rep in [("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'")]:
        text = text.replace(ent, rep)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def kuerze(text: str, n: int = 200) -> str:
    text = " ".join(text.split())
    return text[:n].rsplit(" ", 1)[0] + " …" if len(text) > n else text


# ─── 1. Bundesagentur für Arbeit ─────────────────────────────────────────────

BA_API_HEADERS = {
    # Öffentlicher API-Key der BA Jobsuche (eingebettet im Web-Portal)
    "X-API-Key": "jobboerse-jobsuche",
    "Accept": "application/json",
}


def suche_ba_stellen() -> List[Stelle]:
    """Stellen über die BA Jobsuche-API (v4) suchen.

    Nutzt den öffentlichen X-API-Key des Portals – kein OAuth nötig.
    Wichtig: page ist 1-indexiert (nicht 0).
    """
    alle: List[Stelle] = []
    headers = BA_API_HEADERS

    # Suchen in Leipzig (25 km Umkreis)
    for begriff in BA_SUCHBEGRIFFE:
        params = {
            "was": begriff, "wo": ORT_LEIPZIG, "umkreis": UMKREIS_KM,
            "angebotsart": 1,
            "page": 1, "size": MAX_ERGEBNISSE,  # BA API: page ist 1-indexiert!
        }
        alle.extend(_ba_request(params, headers, ist_remote=False))
        time.sleep(0.4)

    # Remote/Homeoffice deutschlandweit
    params = {
        "was": "Fachinformatiker Anwendungsentwicklung",
        "angebotsart": 1, "arbeitszeit": "ho",
        "page": 1, "size": MAX_ERGEBNISSE,
    }
    alle.extend(_ba_request(params, headers, ist_remote=True))
    return alle


def _ba_request(params: dict, headers: dict = BA_API_HEADERS, ist_remote: bool = False) -> List[Stelle]:
    try:
        r = requests.get(
            "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs",
            params=params, headers=headers, timeout=25,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        console.print(f"    [yellow]⚠ BA API: {e}[/yellow]")
        return []

    stellen = []
    for item in data.get("ergebnisliste", []):
        # API v6: firma ist ein String, Ort liegt unter stellenlokationen[0].adresse
        unternehmen = item.get("firma", "") or ""
        lokationen = item.get("stellenlokationen") or [{}]
        ao = lokationen[0].get("adresse", {}) or {}

        strasse = ao.get("strasse", "") or ""
        if strasse.lower() in ("null", "none", ""):
            strasse = ""
        ort_str = f'{ao.get("plz", "")} {ao.get("ort", "")}'.strip()

        adresse = ", ".join(filter(None, [unternehmen, strasse, ort_str]))

        gehalt = "k.A."
        von, bis = item.get("gehaltsspanneVon"), item.get("gehaltsspanneBis")
        if von and bis:
            gehalt = f"{von:,.0f} - {bis:,.0f} €".replace(",", ".")

        veroeff = (
            item.get("veroeffentlichungszeitraum", {}).get("von", "")
            or item.get("datumErsteVeroeffentlichung", "")
            or ""
        )[:10]

        refnr = item.get("referenznummer", "")
        stelle = Stelle(
            titel=item.get("stellenangebotsTitel", ""),
            unternehmen=unternehmen,
            adresse=adresse,
            beschreibung="→ Volltext: Arbeitsagentur-Website (URL)",
            voraussetzungen="Quereinstieg geeignet" if item.get("quereinstiegGeeignet") else "",
            gehalt=gehalt,
            remote=ist_remote,
            homeoffice="Homeoffice möglich" if ist_remote else "",
            arbeitszeit="Vollzeit" if item.get("arbeitszeitVollzeit") else "Teilzeit",
            veroeffentlicht=veroeff,
            url=f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{refnr}",
            quelle="Bundesagentur f. Arbeit",
        )
        stellen.append(stelle)
    return stellen


def ba_direktlink(suchbegriff: str, ort: str) -> str:
    params = {"was": suchbegriff, "wo": ort, "umkreis": UMKREIS_KM}
    return f"https://www.arbeitsagentur.de/jobsuche/suche?{urlencode(params)}"


# ─── 2. Arbeitnow ────────────────────────────────────────────────────────────

# Relevante Berufsbezeichnungen für den Titel-Filter (eng)
# Wichtig: Wortgrenzen (\b) nutzen um Falsch-Positive zu vermeiden (z.B. "it" in "Credit")
RELEVANTE_BERUFE_TITEL = re.compile(
    r"(softwareentwickl|anwendungsentwickl|fachinformatik|applikationsentwickl"
    r"|web\s*(develop|entwickl)|backend\s+(develop|entwickl)|frontend\s+(develop|entwickl)"
    r"|fullstack|full.?stack"
    r"|mobile\s+(develop|entwickl)|android\s+(develop|entwickl)"
    r"|ios\s+(develop|entwickl)|app\s+(develop|entwickl)"
    r"|fiae\b|fisi\b|\bit.?entwickl|\bit-entwickl"
    r"|\bentwickler\b|\bdeveloper\b|\bprogrammierer\b"
    r"|\bcoding\b|\bdevops\b|data\s+engineer|cloud\s+engineer"
    r"|junior.{1,12}\b(dev|software|entwickl|programmer|coder)"
    r"|\bjunior\b.{1,5}\b(entwickler|developer|softwareentwickler|anwendungsentwickler)"
    r"|\bweb\s*developer\b|\bwebentwickler\b"
    r"|\bbackend\b|\bfrontend\b)",
    re.IGNORECASE,
)

# Breiter Filter für Beschreibungs-Relevanzcheck (nur als zweite Ebene)
RELEVANTE_BERUFE = re.compile(
    r"(softwareentwickl|anwendungsentwickl|fachinformatik|applikationsentwickl"
    r"|programmer|web\s*develop|backend|frontend|fullstack|full.?stack"
    r"|java\b|python\b|kotlin\b|c#\b|\.net\b|php\b|javascript|typescript"
    r"|mobile\s+develop|android\s+develop|ios\s+develop|app\s+develop"
    r"|fiae|fisi|it.{0,10}entwickl|entwickler|developer)",
    re.IGNORECASE,
)

# Orte, die für uns interessant sind
RELEVANTE_ORTE = re.compile(
    r"(germany|deutschland|leipzig|berlin|dresden|halle|sachsen"
    r"|worldwide|remote|europe|eu\b|global|international|\bde\b)",
    re.IGNORECASE,
)


def suche_arbeitnow_stellen() -> List[Stelle]:
    console.print("  [cyan]→ Arbeitnow.com API…[/cyan]")
    stellen: List[Stelle] = []
    gesehen: set = set()

    for kombi in [{"wo": "Leipzig"}, {"remote": True}]:
        params: dict = {"page": 1}
        if "wo" in kombi:
            params["location"] = kombi["wo"]
        else:
            params["remote"] = "true"

        for seite in range(1, 5):
            params["page"] = seite
            try:
                r = requests.get(
                    "https://www.arbeitnow.com/api/job-board-api",
                    params=params, timeout=20,
                )
                r.raise_for_status()
                jobs = r.json().get("data", [])
            except Exception as e:
                console.print(f"    [yellow]⚠ Arbeitnow S.{seite}: {e}[/yellow]")
                break

            if not jobs:
                break

            for job in jobs:
                slug = job.get("slug", "")
                if slug in gesehen:
                    continue

                volltext = (
                    job.get("title", "") + " " + job.get("description", "")
                ).lower()

                # Relevanzfilter: Titel muss IT-Beruf enthalten (streng)
                titel_raw = job.get("title", "")
                if not RELEVANTE_BERUFE_TITEL.search(titel_raw):
                    continue

                ort_raw = job.get("location", "")
                ist_remote = bool(job.get("remote"))
                if not ist_remote and not RELEVANTE_ORTE.search(ort_raw):
                    continue

                gesehen.add(slug)
                beschreibung = strip_html(job.get("description", ""))
                tags = job.get("tags", [])
                ts = job.get("created_at", 0)

                stellen.append(Stelle(
                    titel=job.get("title", ""),
                    unternehmen=job.get("company_name", ""),
                    adresse=f'{job.get("company_name", "")}, {ort_raw}',
                    beschreibung=kuerze(beschreibung, 300),
                    voraussetzungen=", ".join(tags[:10]),
                    remote=ist_remote,
                    homeoffice="Ja" if ist_remote else "",
                    arbeitszeit=", ".join(job.get("job_types", [])),
                    veroeffentlicht=datetime.fromtimestamp(ts).strftime("%Y-%m-%d") if ts else "",
                    url=job.get("url", ""),
                    quelle="Arbeitnow.com",
                ))

    console.print(f"    [green]✓ {len(stellen)} relevante Stellen[/green]")
    return stellen


# ─── 3. Indeed RSS ───────────────────────────────────────────────────────────

def suche_indeed_stellen() -> List[Stelle]:
    """Stellen über Indeed Deutschland RSS-Feeds (Leipzig + Remote)."""
    console.print("  [cyan]→ Indeed.de (RSS)…[/cyan]")
    stellen: List[Stelle] = []
    gesehen: set = set()

    # Indeed RSS-Feed-URLs für verschiedene Suchkombinationen
    suchen = [
        {"q": "Fachinformatiker Anwendungsentwicklung", "l": "Leipzig", "radius": 30},
        {"q": "Softwareentwickler", "l": "Leipzig", "radius": 30},
        {"q": "Junior Entwickler", "l": "Leipzig", "radius": 30},
        {"q": "Anwendungsentwickler", "l": "Leipzig", "radius": 30},
        {"q": "Fachinformatiker Anwendungsentwicklung remote", "l": ""},
        {"q": "Junior Developer remote Deutschland", "l": ""},
    ]

    for suche in suchen:
        params = {
            "q": suche["q"],
            "l": suche.get("l", ""),
            "radius": suche.get("radius", 0),
            "sort": "date",
            "limit": 25,
            "fromage": 60,   # max 60 Tage alt
        }
        params = {k: v for k, v in params.items() if v}

        rss_url = f"https://de.indeed.com/rss?{urlencode(params)}"

        try:
            r = requests.get(
                rss_url,
                timeout=20,
                headers={
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
                },
            )
            if r.status_code != 200:
                continue
            root = ET.fromstring(r.content)
        except Exception as e:
            console.print(f"    [yellow]⚠ Indeed '{suche['q']}': {e}[/yellow]")
            continue

        for item in root.iter("item"):
            def tag(name: str) -> str:
                el = item.find(name)
                return (el.text or "").strip() if el is not None else ""

            link   = tag("link") or tag("guid")
            titel  = tag("title")
            if not link or link in gesehen:
                continue
            if not RELEVANTE_BERUFE_TITEL.search(titel):
                continue

            gesehen.add(link)
            ort_raw   = tag("source") or suche.get("l", "Remote")
            beschr    = strip_html(tag("description"))
            pub_raw   = tag("pubDate")
            pub = ""
            if pub_raw:
                try:
                    pub = datetime.strptime(pub_raw[:25], "%a, %d %b %Y %H:%M:%S").strftime("%Y-%m-%d")
                except Exception:
                    pub = pub_raw[:10]

            unternehmen = ""
            # Indeed kodiert Firma manchmal im Titel als "Titel - Firma"
            if " - " in titel:
                parts = titel.rsplit(" - ", 1)
                if len(parts) == 2:
                    titel, unternehmen = parts[0].strip(), parts[1].strip()

            ist_remote = "remote" in (titel + " " + beschr).lower()

            stellen.append(Stelle(
                titel=titel,
                unternehmen=unternehmen,
                adresse=f'{unternehmen}, {ort_raw}' if unternehmen else ort_raw,
                beschreibung=kuerze(beschr, 300),
                remote=ist_remote,
                homeoffice="Remote möglich" if ist_remote else "",
                veroeffentlicht=pub,
                url=link,
                quelle="Indeed.de",
            ))

        time.sleep(0.5)

    console.print(f"    [green]✓ {len(stellen)} Stellen[/green]")
    return stellen


# ─── 4. Jobicy (RSS – Remote Dev Jobs) ───────────────────────────────────────

def suche_jobicy_stellen() -> List[Stelle]:
    """Remote-Entwicklerjobs über jobicy.com RSS-Feed."""
    console.print("  [cyan]→ Jobicy.com (RSS Remote-Jobs)…[/cyan]")
    stellen: List[Stelle] = []

    feeds = [
        "https://jobicy.com/?feed=job_feed&job_categories=smm&job_types=full-time&search_keywords=developer",
        "https://jobicy.com/?feed=job_feed&job_categories=devops-sysadmin&search_keywords=developer",
        "https://jobicy.com/?feed=job_feed&search_keywords=softwareentwickler",
        "https://jobicy.com/?feed=job_feed&search_keywords=anwendungsentwicklung",
        "https://jobicy.com/?feed=job_feed&search_keywords=junior+developer&job_types=full-time",
    ]
    gesehen: set = set()

    for feed_url in feeds:
        try:
            r = requests.get(feed_url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                continue
            root = ET.fromstring(r.content)
        except Exception:
            continue

        ns = {"content": "http://purl.org/rss/1.0/modules/content/"}
        for item in root.iter("item"):
            def tag(name: str) -> str:
                el = item.find(name)
                return el.text.strip() if el is not None and el.text else ""

            titel  = tag("title")
            link   = tag("link")
            if link in gesehen:
                continue

            volltext = (titel + " " + tag("description")).lower()
            if not RELEVANTE_BERUFE.search(volltext):
                continue

            gesehen.add(link)
            beschreibung = strip_html(tag("description"))

            pub_raw = tag("pubDate")
            pub = ""
            if pub_raw:
                try:
                    pub = datetime.strptime(pub_raw[:25], "%a, %d %b %Y %H:%M:%S").strftime("%Y-%m-%d")
                except Exception:
                    pub = pub_raw[:10]

            stellen.append(Stelle(
                titel=titel,
                unternehmen=tag("author") or "",
                adresse="Remote (weltweit)",
                beschreibung=kuerze(beschreibung, 300),
                remote=True,
                homeoffice="100% Remote",
                veroeffentlicht=pub,
                url=link,
                quelle="Jobicy.com",
            ))

    console.print(f"    [green]✓ {len(stellen)} Stellen[/green]")
    return stellen


# ─── 4. Remotive ─────────────────────────────────────────────────────────────

# Locations, die auf Deutschland/Europa/Global hinweisen
REMOTIVE_LOC_OK = re.compile(
    r"(germany|deutschland|europe|eu\b|worldwide|anywhere|global"
    r"|remote|latin america|emea|international)",
    re.IGNORECASE,
)


def suche_remotive_stellen() -> List[Stelle]:
    """Remote-Dev-Stellen via Remotive API – gefiltert auf Europa/Worldwide."""
    console.print("  [cyan]→ Remotive.com (Remote API)…[/cyan]")
    stellen: List[Stelle] = []
    gesehen: set = set()

    suchbegriffe = [
        "software developer", "softwareentwickler", "anwendungsentwicklung",
        "junior developer", "fachinformatiker",
    ]

    for begriff in suchbegriffe:
        try:
            r = requests.get(
                "https://remotive.com/api/remote-jobs",
                params={"category": "software-dev", "search": begriff, "limit": 50},
                timeout=20,
            )
            r.raise_for_status()
            jobs = r.json().get("jobs", [])
        except Exception as e:
            console.print(f"    [yellow]⚠ Remotive '{begriff}': {e}[/yellow]")
            continue

        for job in jobs:
            job_id = str(job.get("id", ""))
            if job_id in gesehen:
                continue

            volltext = (job.get("title", "") + " " + job.get("description", "")).lower()
            if not RELEVANTE_BERUFE.search(volltext):
                continue

            # Standort-Filter: nur DE/EU/worldwide
            kandidaten_loc = job.get("candidate_required_location", "") or ""
            if kandidaten_loc and not REMOTIVE_LOC_OK.search(kandidaten_loc):
                continue

            gesehen.add(job_id)
            beschreibung = strip_html(job.get("description", ""))
            gehalt = job.get("salary", "k.A.") or "k.A."
            pub = (job.get("publication_date", "") or "")[:10]

            stellen.append(Stelle(
                titel=job.get("title", ""),
                unternehmen=job.get("company_name", ""),
                adresse=f'{job.get("company_name", "")} – {kandidaten_loc or "Remote"}',
                beschreibung=kuerze(beschreibung, 300),
                voraussetzungen=kuerze(beschreibung, 400),
                gehalt=gehalt,
                remote=True,
                homeoffice=f"100% Remote ({kandidaten_loc})" if kandidaten_loc else "100% Remote",
                arbeitszeit=job.get("job_type", ""),
                veroeffentlicht=pub,
                url=job.get("url", ""),
                quelle="Remotive.com",
            ))

    console.print(f"    [green]✓ {len(stellen)} relevante Stellen[/green]")
    return stellen


# ─── Deduplizierung ───────────────────────────────────────────────────────────

def _norm_titel(titel: str) -> str:
    """Normalisiert Titel: Orts-Klammern und Sonderzeichen entfernen."""
    t = re.sub(r"\s*\([^)]*\)\s*", " ", titel)      # "(Berlin)" entfernen
    t = re.sub(r"\s*(m/w/d|m/f/d|w/m/d|gn)\s*", " ", t, flags=re.I)
    return " ".join(t.lower().split())


def dedupliziere(stellen: List[Stelle]) -> List[Stelle]:
    gesehen: set = set()
    unique: List[Stelle] = []
    for s in stellen:
        key = (_norm_titel(s.titel), s.unternehmen.lower().strip())
        if key not in gesehen:
            gesehen.add(key)
            unique.append(s)
    return unique


# ─── Ausgabe ─────────────────────────────────────────────────────────────────

def erstelle_tabelle(stellen: List[Stelle]) -> Table:
    tabelle = Table(
        title=(
            f"Stellenangebote: Fachinformatiker Anwendungsentwicklung – Leipzig & Remote\n"
            f"Stand: {datetime.now().strftime('%d.%m.%Y %H:%M')}  |  {len(stellen)} Stellen"
        ),
        caption="★★★ = sehr einsteigerfreundlich  ★★☆ = einsteigerfreundlich  ★☆☆ = neutral  ✗ = Erfahrung erwartet",
        box=box.ROUNDED,
        show_lines=True,
        expand=True,
    )

    tabelle.add_column("#",              style="dim", width=3, justify="right")
    tabelle.add_column("Einstieg",       width=8,  justify="center")
    tabelle.add_column("Stelle\nUnternehmen", min_width=28)
    tabelle.add_column("Adresse / Ort",  min_width=20)
    tabelle.add_column("Beschreibung",   min_width=38)
    tabelle.add_column("Voraussetzungen\n/ Tags", min_width=24)
    tabelle.add_column("Gehalt",         width=15)
    tabelle.add_column("Remote\n/ HO",   width=11)
    tabelle.add_column("Arbeitszeit",    width=13)
    tabelle.add_column("Veröff.",        width=10)
    tabelle.add_column("Quelle",         width=16)
    tabelle.add_column("URL",            min_width=18)

    for i, s in enumerate(stellen, 1):
        if s.einsteiger_score >= 4:
            ampel = Text("★★★", style="bold green")
        elif s.einsteiger_score >= 2:
            ampel = Text("★★☆", style="bold yellow")
        elif s.einsteiger_score >= 0:
            ampel = Text("★☆☆", style="yellow")
        else:
            ampel = Text("✗", style="dim red")

        titel_cell = Text()
        titel_cell.append(s.titel or "–", style="bold")
        if s.unternehmen:
            titel_cell.append(f"\n{s.unternehmen}", style="cyan")

        if s.remote:
            ho_cell = Text("✓ Remote", style="green")
            if s.homeoffice and s.homeoffice not in ("Ja", "100% Remote"):
                ho_cell.append(f"\n{s.homeoffice}", style="dim green")
        elif s.homeoffice:
            ho_cell = Text(f"HO: {s.homeoffice}", style="yellow")
        else:
            ho_cell = Text("–", style="dim")

        tabelle.add_row(
            str(i),
            ampel,
            titel_cell,
            s.adresse or "–",
            kuerze(s.beschreibung, 200) or "–",
            kuerze(s.voraussetzungen, 130) if s.voraussetzungen else "–",
            s.gehalt or "k.A.",
            ho_cell,
            s.arbeitszeit or "–",
            s.veroeffentlicht or "–",
            s.quelle,
            s.url or "–",
        )

    return tabelle


def exportiere_csv(stellen: List[Stelle]):
    felder = [
        "rang", "einsteiger_score", "einsteiger_signale",
        "titel", "unternehmen", "adresse",
        "beschreibung", "voraussetzungen", "gehalt",
        "remote", "homeoffice", "arbeitszeit",
        "veroeffentlicht", "quelle", "url",
    ]
    with open(CSV_DATEI, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=felder)
        w.writeheader()
        for i, s in enumerate(stellen, 1):
            sauber = re.sub(r"\[.*?\]", "", " | ".join(s.einsteiger_tags))
            w.writerow({
                "rang": i,
                "einsteiger_score": s.einsteiger_score,
                "einsteiger_signale": sauber,
                "titel": s.titel,
                "unternehmen": s.unternehmen,
                "adresse": s.adresse,
                "beschreibung": s.beschreibung,
                "voraussetzungen": s.voraussetzungen,
                "gehalt": s.gehalt,
                "remote": "Ja" if s.remote else "Nein",
                "homeoffice": s.homeoffice,
                "arbeitszeit": s.arbeitszeit,
                "veroeffentlicht": s.veroeffentlicht,
                "quelle": s.quelle,
                "url": s.url,
            })


# ─── Hauptprogramm ────────────────────────────────────────────────────────────

def main():
    console.print()
    console.rule("[bold blue]Jobsuche: Fachinformatiker Anwendungsentwicklung – Leipzig & Remote[/bold blue]")
    console.print()

    alle: List[Stelle] = []

    # 1 ─ Bundesagentur für Arbeit
    console.print("[bold]1. Bundesagentur für Arbeit[/bold]")
    console.print(f"  [cyan]→ Leipzig ({UMKREIS_KM} km) + Remote/Homeoffice…[/cyan]")
    ba_stellen = suche_ba_stellen()
    if ba_stellen:
        console.print(f"  [green]✓ {len(ba_stellen)} Stellen aus der BA API[/green]")
        alle.extend(ba_stellen)
    else:
        console.print("  [yellow]⚠  BA API nicht erreichbar. Direkte Browser-Links:[/yellow]")
        for begriff in BA_SUCHBEGRIFFE[:2]:
            console.print(f"    {ba_direktlink(begriff, ORT_LEIPZIG)}")

    # 2 ─ Arbeitnow
    console.print("\n[bold]2. Arbeitnow.com[/bold]")
    alle.extend(suche_arbeitnow_stellen())

    # 3 ─ Indeed
    console.print("\n[bold]3. Indeed.de (RSS)[/bold]")
    alle.extend(suche_indeed_stellen())

    # 4 ─ Jobicy
    console.print("\n[bold]4. Jobicy.com (RSS Remote)[/bold]")
    alle.extend(suche_jobicy_stellen())

    # 5 ─ Remotive
    console.print("\n[bold]5. Remotive.com (Remote DE/EU/Worldwide)[/bold]")
    alle.extend(suche_remotive_stellen())

    # Deduplizieren
    console.print(f"\n[dim]Vor Deduplizierung: {len(alle)}[/dim]")
    alle = dedupliziere(alle)
    console.print(f"[dim]Nach Deduplizierung: {len(alle)}[/dim]")

    # Vertrieb / Customer Success / Recruiting o.ä. aussortieren
    vorher = len(alle)
    alle = [s for s in alle if not ist_nicht_entwickler_stelle(s)]
    console.print(f"[dim]Nicht-Entwicklerstellen entfernt: {vorher - len(alle)}[/dim]")

    if not alle:
        console.print("\n[bold red]Keine Stellen gefunden. Internetverbindung oder API-Verfügbarkeit prüfen.[/bold red]")
        sys.exit(1)

    # Einsteiger-Scoring
    for s in alle:
        score, tags = berechne_einsteiger_score(s)
        s.einsteiger_score = score
        s.einsteiger_tags = tags

    # Sortierung: Einsteiger-Score absteigend, dann Datum absteigend
    alle.sort(key=lambda s: (-s.einsteiger_score, s.veroeffentlicht or ""), reverse=False)
    alle.sort(key=lambda s: (-s.einsteiger_score, s.veroeffentlicht))

    # Tabelle
    console.print()
    console.print(erstelle_tabelle(alle))

    # Legende
    console.print("\n[bold]Legende Einstiegsbewertung:[/bold]")
    console.print("  [bold green]★★★[/bold green]  Sehr einsteigerfreundlich  (Score ≥ 4)")
    console.print("  [bold yellow]★★☆[/bold yellow]  Einsteigerfreundlich       (Score 2–3)")
    console.print("  [yellow]★☆☆[/yellow]  Neutral / unklar           (Score 0–1)")
    console.print("  [dim red]✗[/dim red]    Erfahrung erwartet         (Score < 0)")

    # Statistik
    n_remote    = sum(1 for s in alle if s.remote)
    n_gut       = sum(1 for s in alle if s.einsteiger_score >= 2)
    n_sehr_gut  = sum(1 for s in alle if s.einsteiger_score >= 4)

    console.print(f"\n[bold]Statistik:[/bold]")
    console.print(f"  Stellen gesamt:            {len(alle)}")
    console.print(f"  Davon Remote/Homeoffice:   {n_remote}")
    console.print(f"  Einsteiger geeignet (≥★★☆): {n_gut}")
    console.print(f"  Top Einstieg (★★★):         {n_sehr_gut}")

    # CSV
    exportiere_csv(alle)
    console.print(f"\n[green]✓ CSV exportiert:[/green] {CSV_DATEI}")
    console.print("[dim]  → Öffnen in LibreOffice Calc / Excel für weitere Filterung[/dim]\n")


if __name__ == "__main__":
    main()
