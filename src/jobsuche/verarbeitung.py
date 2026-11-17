"""Treffer aller Quellen zusammenführen: Duplikate entfernen, filtern, bewerten, sortieren."""

import re

from jobsuche.bewertung import berechne_einsteiger_score, ist_nicht_entwickler_stelle
from jobsuche.modell import Stelle


def normalisiere_titel(titel: str) -> str:
    """Titel vergleichbar machen: Klammerzusätze wie "(Berlin)" und "(m/w/d)" entfernen."""
    t = re.sub(r"\s*\([^)]*\)\s*", " ", titel)
    t = re.sub(r"\s*(m/w/d|m/f/d|w/m/d|gn)\s*", " ", t, flags=re.I)
    return " ".join(t.lower().split())


def dedupliziere(stellen: list[Stelle]) -> list[Stelle]:
    """Gleiche Stelle aus mehreren Quellen nur einmal behalten (erster Treffer gewinnt)."""
    gesehen: set[tuple[str, str]] = set()
    eindeutig: list[Stelle] = []
    for stelle in stellen:
        schluessel = (normalisiere_titel(stelle.titel), stelle.unternehmen.lower().strip())
        if schluessel not in gesehen:
            gesehen.add(schluessel)
            eindeutig.append(stelle)
    return eindeutig


def entferne_nicht_entwickler(stellen: list[Stelle]) -> list[Stelle]:
    return [s for s in stellen if not ist_nicht_entwickler_stelle(s)]


def bewerte(stellen: list[Stelle]) -> None:
    """Einsteiger-Score und Signale an jede Stelle schreiben."""
    for stelle in stellen:
        stelle.einsteiger_score, stelle.einsteiger_signale = berechne_einsteiger_score(stelle)


def sortiere(stellen: list[Stelle]) -> list[Stelle]:
    """Nach Einsteiger-Score absteigend, bei gleichem Score die neuesten zuerst.

    Zwei stabile Sortierungen: erst nach Datum (neu → alt, ohne Datum ans Ende),
    dann nach Score; die Datumsreihenfolge bleibt innerhalb gleicher Scores erhalten.
    """
    nach_datum = sorted(stellen, key=lambda s: s.veroeffentlicht, reverse=True)
    return sorted(nach_datum, key=lambda s: -s.einsteiger_score)
