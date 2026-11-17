"""Fachliche Regeln: Ist eine Stelle relevant, und wie einsteigerfreundlich ist sie?

Alle Regeln sind reguläre Ausdrücke mit Wortgrenzen (\\b), damit z. B. "it" nicht in
"Credit" gefunden wird. Die Punkte sind Erfahrungswerte und bewusst einfach gehalten.
"""

import re

from jobsuche.modell import Stelle

# (Muster, Punkte, Bezeichnung)
POSITIV_SIGNALE = [
    (r"\bberufseinsteiger\b",                4, "Berufseinsteiger"),
    (r"\beinsteiger(position)?\b",           3, "Einsteiger"),
    (r"\bjunior\b",                          3, "Junior"),
    (r"\bohne\b.{0,30}\bberufserfahrung\b",  4, "Ohne Erfahrung"),
    (r"\babsolvent(in)?\b",                  3, "Absolvent/in"),
    (r"\bberufsanf[äa]nger\b",               4, "Berufsanfänger"),
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
    # "Junior bis Senior", "Junior/Senior": gleicht den Senior-Abzug aus,
    # weil Einsteiger ausdrücklich angesprochen werden
    (r"\bjunior\b.{0,12}\bsenior\b",         3, "Junior bis Senior"),
]

NEGATIV_SIGNALE = [
    (r"\bsenior\b",                                           3, "Senior"),
    (r"\bmehrj[äa]hrige.{0,20}(berufserfahrung|erfahrung)\b", 4, "Mehrjährige Erfahrung"),
    (r"\bmindestens [3-9] jahre?\b",                          4, "Min. 3+ Jahre"),
    (r"\b[3-9]\+\s*jahre?\b",                                 4, "3+ Jahre"),
    (r"\b(lead|principal|head of|architect)\b",               3, "Leitungsposition"),
    (r"\bteam.?lead\b",                                       3, "Team Lead"),
    (r"\bteamleiter\b",                                       3, "Teamleiter"),
    (r"\berfahrener?\s+(entwickler|softwareentwickler)\b",    3, "Erfahrener Entwickler"),
    (r"\b(experte|expert)\b",                                 2, "Experte erwartet"),
    (r"\b5\+\s*jahre?\b",                                     4, "5+ Jahre"),
    (r"\bmindestens\s+5\b",                                   4, "Min. 5 Jahre"),
]

# Stellen ohne Entwicklungsbezug (Vertrieb, Kundenbetreuung, Recruiting …) – nur der Titel zählt
NICHT_ENTWICKLER_TITEL = re.compile(
    r"(\bsales\b|vertrieb|account\s*(manager|executive)|business\s+development"
    r"|customer\s+success|kundenbetreu|kundenberat|customer\s+support"
    r"|\brecruit|talent\s+acquisition|\bmarketing\b|sales\s+development)",
    re.IGNORECASE,
)

# Enger Filter auf den Titel: Es muss eine Entwicklungsstelle sein
RELEVANTE_BERUFE_TITEL = re.compile(
    r"(softwareentwickl|anwendungsentwickl|fachinformatik|applikationsentwickl"
    r"|web\s*(develop|entwickl)|backend\s+(develop|entwickl)|frontend\s+(develop|entwickl)"
    r"|fullstack|full.?stack"
    r"|mobile\s+(develop|entwickl)|android\s+(develop|entwickl)"
    r"|ios\s+(develop|entwickl)|app\s+(develop|entwickl)"
    r"|fiae\b|fisi\b|\bit.?entwickl|\bit-entwickl"
    r"|\bentwickler\b|\bdeveloper\b|\bprogrammierer\b"
    r"|software\s*engineer"
    r"|\bcoding\b|\bdevops\b|data\s+engineer|cloud\s+engineer"
    r"|junior.{1,12}\b(dev|software|entwickl|programmer|coder)"
    r"|\bjunior\b.{1,5}\b(entwickler|developer|softwareentwickler|anwendungsentwickler)"
    r"|\bweb\s*developer\b|\bwebentwickler\b"
    r"|\bbackend\b|\bfrontend\b)",
    re.IGNORECASE,
)

# Breiter Filter auf Titel + Beschreibung (Sprachen, Frameworks, Berufsbezeichnungen)
RELEVANTE_BERUFE = re.compile(
    r"(softwareentwickl|anwendungsentwickl|fachinformatik|applikationsentwickl"
    r"|programmer|web\s*develop|backend|frontend|fullstack|full.?stack"
    r"|java\b|python\b|kotlin\b|c#\b|\.net\b|php\b|javascript|typescript"
    r"|mobile\s+develop|android\s+develop|ios\s+develop|app\s+develop"
    r"|fiae|fisi|it.{0,10}entwickl|entwickler|developer)",
    re.IGNORECASE,
)


def ist_nicht_entwickler_stelle(stelle: Stelle) -> bool:
    return bool(NICHT_ENTWICKLER_TITEL.search(stelle.titel or ""))


def berechne_einsteiger_score(stelle: Stelle) -> tuple[int, list[str]]:
    """Punktzahl und gefundene Signale ("+Junior", "-Senior") für Titel, Beschreibung, Voraussetzungen."""
    text = f"{stelle.titel} {stelle.beschreibung} {stelle.voraussetzungen}".lower()
    score = 0
    signale = []
    for muster, punkte, bezeichnung in POSITIV_SIGNALE:
        if re.search(muster, text, re.IGNORECASE):
            score += punkte
            signale.append(f"+{bezeichnung}")
    for muster, punkte, bezeichnung in NEGATIV_SIGNALE:
        if re.search(muster, text, re.IGNORECASE):
            score -= punkte
            signale.append(f"-{bezeichnung}")
    return score, signale
