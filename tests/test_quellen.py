"""Die parse-Funktionen jeder Quelle mit festen Beispielantworten (kein Netzwerk)."""

import xml.etree.ElementTree as ET

from jobsuche.quellen import arbeitnow, bundesagentur, indeed, jobicy, remotive

# ─── Bundesagentur ───────────────────────────────────────────────────────────

BA_ANTWORT = {
    "ergebnisliste": [
        {
            "stellenangebotsTitel": "Fachinformatiker Anwendungsentwicklung (m/w/d)",
            "firma": "Beispiel GmbH",
            "stellenlokationen": [{"adresse": {"strasse": "Hauptstr. 1", "plz": "04109", "ort": "Leipzig"}}],
            "gehaltsspanneVon": 42000, "gehaltsspanneBis": 50000,
            "veroeffentlichungszeitraum": {"von": "2026-11-10T00:00:00"},
            "arbeitszeitVollzeit": True,
            "quereinstiegGeeignet": True,
            "referenznummer": "10001-123",
        },
        {
            "stellenangebotsTitel": "Softwareentwickler",
            "firma": "Ohne Adresse AG",
            "stellenlokationen": [{"adresse": {"strasse": "null", "plz": "", "ort": "Halle"}}],
            "datumErsteVeroeffentlichung": "2026-11-01",
        },
    ]
}


def test_ba_parse_vollstaendiger_eintrag():
    stelle = bundesagentur.parse_ergebnisse(BA_ANTWORT, ist_remote=False)[0]
    assert stelle.adresse == "Beispiel GmbH, Hauptstr. 1, 04109 Leipzig"
    assert stelle.gehalt == "42.000 - 50.000 €"
    assert stelle.veroeffentlicht == "2026-11-10"
    assert stelle.arbeitszeit == "Vollzeit"
    assert stelle.voraussetzungen == "Quereinstieg geeignet"
    assert stelle.url.endswith("/jobdetail/10001-123")
    assert not stelle.remote


def test_ba_parse_fehlende_felder_und_strasse_null():
    stelle = bundesagentur.parse_ergebnisse(BA_ANTWORT, ist_remote=True)[1]
    assert stelle.adresse == "Ohne Adresse AG, Halle"
    assert stelle.gehalt == "k.A."
    assert stelle.veroeffentlicht == "2026-11-01"
    assert stelle.arbeitszeit == "Teilzeit"
    assert stelle.remote and stelle.homeoffice == "Homeoffice möglich"


def test_ba_leere_antwort():
    assert bundesagentur.parse_ergebnisse({}, ist_remote=False) == []


# ─── Arbeitnow ───────────────────────────────────────────────────────────────

def _arbeitnow_job(**felder):
    job = {"slug": "a", "title": "Backend Developer", "company_name": "X", "location": "Leipzig",
           "remote": False, "description": "<p>Python</p>", "tags": ["Python"], "job_types": ["fulltime"],
           "created_at": 0, "url": "https://example.org/a"}
    job.update(felder)
    return job


def test_arbeitnow_filtert_titel_ort_und_doppelte_slugs():
    jobs = [
        _arbeitnow_job(slug="a"),
        _arbeitnow_job(slug="a"),                                  # doppelt
        _arbeitnow_job(slug="b", title="Office Manager"),          # kein Entwicklertitel
        _arbeitnow_job(slug="c", location="Paris, France"),        # falscher Ort, nicht remote
        _arbeitnow_job(slug="d", location="Paris, France", remote=True),  # remote: Ort egal
    ]
    gesehen: set[str] = set()
    stellen = arbeitnow.parse_jobs(jobs, gesehen)
    assert [s.adresse for s in stellen] == ["X, Leipzig", "X, Paris, France"]
    assert gesehen == {"a", "d"}
    assert stellen[0].beschreibung == "Python"


# ─── RSS (Jobicy, Indeed) ────────────────────────────────────────────────────

def _rss(*items: str) -> ET.Element:
    return ET.fromstring(f"<rss><channel>{''.join(items)}</channel></rss>")


def test_jobicy_parse_feed():
    wurzel = _rss(
        "<item><title>Python Developer</title><link>https://j/1</link><author>ACME</author>"
        "<description>&lt;p&gt;Remote Python&lt;/p&gt;</description>"
        "<pubDate>Mon, 03 Nov 2026 10:00:00 +0000</pubDate></item>",
        "<item><title>Python Developer</title><link>https://j/1</link></item>",  # doppelt
    )
    stellen = jobicy.parse_feed(wurzel, set())
    assert len(stellen) == 1
    assert stellen[0].unternehmen == "ACME"
    assert stellen[0].veroeffentlicht == "2026-11-03"
    assert stellen[0].beschreibung == "Remote Python"


def test_indeed_trennt_firma_vom_titel():
    wurzel = _rss("<item><title>Junior Developer - Beispiel AG</title><link>https://i/1</link></item>")
    stelle = indeed.parse_feed(wurzel, set(), standard_ort="Leipzig")[0]
    assert (stelle.titel, stelle.unternehmen, stelle.adresse) == ("Junior Developer", "Beispiel AG", "Beispiel AG, Leipzig")


# ─── Remotive ────────────────────────────────────────────────────────────────

def test_remotive_filtert_standort():
    jobs = [
        {"id": 1, "title": "Python Developer", "description": "", "candidate_required_location": "Europe"},
        {"id": 2, "title": "Python Developer", "description": "", "candidate_required_location": "USA only"},
        {"id": 3, "title": "Python Developer", "description": "", "candidate_required_location": ""},
    ]
    stellen = remotive.parse_jobs(jobs, set())
    assert [s.homeoffice for s in stellen] == ["100% Remote (Europe)", "100% Remote"]
