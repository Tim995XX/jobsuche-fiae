"""Kommandozeile: python -m jobsuche [--ort Leipzig] [--umkreis 25] [--csv stellen.csv]"""

import argparse
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

from jobsuche import ausgabe, verarbeitung
from jobsuche.modell import Stelle
from jobsuche.quellen import arbeitnow, bundesagentur, jobicy, remotive

TITEL = "Stellenangebote: Fachinformatiker Anwendungsentwicklung"


def lies_argumente(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="jobsuche",
        description="Sucht Stellen für Fachinformatiker/innen Anwendungsentwicklung in mehreren Jobbörsen.",
    )
    parser.add_argument("--ort", default="Leipzig", help="Ort für die Umkreissuche (Standard: Leipzig)")
    parser.add_argument("--umkreis", type=int, default=25, choices=bundesagentur.ERLAUBTE_UMKREISE,
                        help="Umkreis in km (Standard: 25)")
    parser.add_argument("--csv", type=Path, default=Path("stellen.csv"), help="Zieldatei für den CSV-Export")
    return parser.parse_args(argv)


def sammle(console: Console, ort: str, umkreis: int) -> list[Stelle]:
    """Alle Quellen nacheinander abfragen; eine ausgefallene Quelle stoppt die anderen nicht."""
    quellen = [
        ("Bundesagentur für Arbeit", lambda: bundesagentur.suche(ort, umkreis)),
        ("Arbeitnow.com", lambda: arbeitnow.suche(ort)),
        ("Jobicy.com (RSS Remote)", jobicy.suche),
        ("Remotive.com (Remote DE/EU/Worldwide)", remotive.suche),
    ]
    alle: list[Stelle] = []
    for nr, (name, abfrage) in enumerate(quellen, 1):
        console.print(f"[bold]{nr}. {name}[/bold]")
        treffer = abfrage()
        console.print(f"  [green]✓ {len(treffer)} Stellen[/green]")
        if name.startswith("Bundesagentur") and not treffer:
            console.print("  [yellow]⚠ BA API nicht erreichbar. Direkte Browser-Links:[/yellow]")
            for begriff in bundesagentur.SUCHBEGRIFFE[:2]:
                console.print(f"    {bundesagentur.direktlink(begriff, ort, umkreis)}")
        alle.extend(treffer)
    return alle


def main(argv: list[str] | None = None) -> int:
    args = lies_argumente(argv)
    console = Console(width=230)
    logging.basicConfig(level=logging.WARNING, format="%(message)s",
                        handlers=[RichHandler(console=console, show_time=False, show_path=False)])

    titel = f"{TITEL} – {args.ort} & Remote"
    console.rule(f"[bold blue]{titel}[/bold blue]")

    stellen = sammle(console, args.ort, args.umkreis)
    console.print(f"\n[dim]Vor Deduplizierung: {len(stellen)}[/dim]")
    stellen = verarbeitung.dedupliziere(stellen)
    console.print(f"[dim]Nach Deduplizierung: {len(stellen)}[/dim]")
    anzahl = len(stellen)
    stellen = verarbeitung.entferne_nicht_entwickler(stellen)
    console.print(f"[dim]Nicht-Entwicklerstellen entfernt: {anzahl - len(stellen)}[/dim]")

    if not stellen:
        console.print("\n[bold red]Keine Stellen gefunden. Internetverbindung oder API-Verfügbarkeit prüfen.[/bold red]")
        return 1

    verarbeitung.bewerte(stellen)
    stellen = verarbeitung.sortiere(stellen)

    console.print()
    console.print(ausgabe.erstelle_tabelle(stellen, titel))
    ausgabe.drucke_zusammenfassung(console, stellen)
    ausgabe.exportiere_csv(stellen, args.csv)
    console.print(f"\n[green]✓ CSV exportiert:[/green] {args.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
