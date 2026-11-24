# Jobsuche Fachinformatiker Anwendungsentwicklung

Ein Kommandozeilenwerkzeug, das mehrere Jobbörsen gleichzeitig nach Stellen für
Fachinformatiker/innen Anwendungsentwicklung durchsucht, Duplikate zusammenführt, fachfremde
Stellen aussortiert und jede Stelle danach bewertet, wie einsteigerfreundlich sie ist.
Das Ergebnis erscheint als Tabelle im Terminal und als CSV für Excel oder LibreOffice.

Entstanden aus der eigenen Bewerbungsphase: Statt vier Portale einzeln zu durchsuchen,
landen alle Treffer sortiert in einer Liste, die passendsten oben.

## Ablauf

```
Bundesagentur für Arbeit (REST/JSON) ─┐
Arbeitnow (REST/JSON) ────────────────┤   parse → Stelle    ┌ Duplikate entfernen (Titel + Firma normalisiert)
Jobicy (RSS/XML) ─────────────────────┼──────────────────▶  ├ Vertrieb, Recruiting … aussortieren
Remotive (REST/JSON) ─────────────────┘                     ├ Einsteiger-Score berechnen
                                                            └ sortieren → Tabelle + CSV
```

**Einsteiger-Score:** Regeln mit regulären Ausdrücken auf Titel und Beschreibung. Hinweise wie
„Junior“, „Berufseinsteiger“ oder „ohne Berufserfahrung“ geben Pluspunkte, „Senior“,
„mehrjährige Erfahrung“ oder „Teamleiter“ Abzüge. „Junior bis Senior“ gleicht den Senior-Abzug
wieder aus. Alle Muster nutzen Wortgrenzen, damit z. B. „it“ nicht in „Credit“ gefunden wird.

| Score | Anzeige | Bedeutung |
|---|---|---|
| ≥ 4 | ★★★ | sehr einsteigerfreundlich |
| 2–3 | ★★☆ | einsteigerfreundlich |
| 0–1 | ★☆☆ | neutral |
| < 0 | ✗ | Erfahrung erwartet |

## Aufbau

```
src/jobsuche/
  __main__.py        Kommandozeile, Ablaufsteuerung
  modell.py          Datenklasse Stelle
  quellen/           je Jobbörse ein Modul: suche() mit Netzwerk und Fehlerbehandlung,
                     parse_…() als reine Funktion ohne Netzwerk
  bewertung.py       Relevanzfilter und Einsteiger-Score
  verarbeitung.py    Deduplizieren, filtern, bewerten, sortieren
  ausgabe.py         Terminal-Tabelle (rich) und CSV-Export
  text.py            HTML entfernen, kürzen, RSS-Felder lesen
tests/               pytest, komplett ohne Netzwerk
```

Entwurfsentscheidungen:

- **Abruf und Auswertung getrennt.** Die `parse`-Funktionen bekommen fertige JSON- bzw.
  XML-Daten. So lassen sie sich mit festen Beispielantworten testen, und ein Ausfall einer
  Quelle betrifft nur deren `suche()`.
- **Eine ausgefallene Quelle stoppt die anderen nicht.** Fehler werden gezielt abgefangen
  (`requests.RequestException`, ungültiges JSON/XML) und als Warnung ausgegeben.
- **Darstellung getrennt von Daten.** Die Bewertung speichert neutrale Signale wie `+Junior`;
  Farben und Sterne entstehen erst in der Ausgabe.

## Installation und Nutzung

Voraussetzung: Python ≥ 3.10.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

jobsuche                                   # Leipzig, 25 km, Ergebnis in stellen.csv
jobsuche --ort Dresden --umkreis 50 --csv dresden.csv
pytest                                     # Tests
```

Erlaubte Umkreise (Vorgabe der BA-API): 5, 10, 25, 50, 100, 150, 200 km.
Remote-Stellen werden unabhängig vom Ort immer mit gesucht.

## Wie der Umbau geprüft wurde

Das Projekt begann als ein einzelnes Skript (erster Commit). Vor der Aufteilung in Module
wurden alle HTTP-Antworten eines echten Laufs aufgezeichnet und anschließend für alten und
neuen Code wiedergegeben: Die erzeugte CSV war byte-genau identisch. Erst danach wurden
Fehler behoben, jeweils mit Regressionstest (siehe Git-Historie):

- Sortierung: Bei gleichem Score standen die ältesten Stellen oben.
- Jobicy: Ein Feed fragte die Marketing-Kategorie ab, und der Filter prüfte die ganze
  Beschreibung. Dadurch landeten z. B. „Junior Campaign Manager“ oder „Senior AP Accountant“
  in der Liste.
- Der Titelfilter kannte „Software Engineer“ nicht.
- Indeed wurde entfernt, weil der RSS-Dienst keine Treffer mehr liefert.

## Grenzen

- Die Bundesagentur liefert über die API nur Kurzangaben; die volle Beschreibung steht auf
  der verlinkten Seite. Der Score stützt sich bei BA-Stellen daher fast nur auf den Titel.
- Der Score ist eine Heuristik mit festen Punktwerten, kein trainiertes Modell.
- Jobicy und Remotive sind internationale Remote-Börsen; viele Treffer sind englischsprachig.

## Hinweis

Dieses Projekt wurde mithilfe von Claude (Anthropic) erstellt.

## Lizenz

MIT, siehe [LICENSE](LICENSE).
