"""Ausgabe als farbige Tabelle im Terminal (rich) und als CSV für Excel/LibreOffice."""

import csv
from datetime import datetime
from pathlib import Path

from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

from jobsuche.modell import Stelle
from jobsuche.text import kuerze

CSV_FELDER = [
    "rang", "einsteiger_score", "einsteiger_signale",
    "titel", "unternehmen", "adresse",
    "beschreibung", "voraussetzungen", "gehalt",
    "remote", "homeoffice", "arbeitszeit",
    "veroeffentlicht", "quelle", "url",
]


def sterne(score: int) -> Text:
    if score >= 4:
        return Text("★★★", style="bold green")
    if score >= 2:
        return Text("★★☆", style="bold yellow")
    if score >= 0:
        return Text("★☆☆", style="yellow")
    return Text("✗", style="dim red")


def erstelle_tabelle(stellen: list[Stelle], titel: str) -> Table:
    tabelle = Table(
        title=f"{titel}\nStand: {datetime.now().strftime('%d.%m.%Y %H:%M')}  |  {len(stellen)} Stellen",
        caption="★★★ = sehr einsteigerfreundlich  ★★☆ = einsteigerfreundlich  ★☆☆ = neutral  ✗ = Erfahrung erwartet",
        box=box.ROUNDED,
        show_lines=True,
        expand=True,
    )
    tabelle.add_column("#", style="dim", width=3, justify="right")
    tabelle.add_column("Einstieg", width=8, justify="center")
    tabelle.add_column("Stelle\nUnternehmen", min_width=28)
    tabelle.add_column("Adresse / Ort", min_width=20)
    tabelle.add_column("Beschreibung", min_width=38)
    tabelle.add_column("Voraussetzungen\n/ Tags", min_width=24)
    tabelle.add_column("Gehalt", width=15)
    tabelle.add_column("Remote\n/ HO", width=11)
    tabelle.add_column("Arbeitszeit", width=13)
    tabelle.add_column("Veröff.", width=10)
    tabelle.add_column("Quelle", width=16)
    tabelle.add_column("URL", min_width=18)

    for nr, s in enumerate(stellen, 1):
        stelle_zelle = Text(s.titel or "–", style="bold")
        if s.unternehmen:
            stelle_zelle.append(f"\n{s.unternehmen}", style="cyan")

        if s.remote:
            remote_zelle = Text("✓ Remote", style="green")
            if s.homeoffice and s.homeoffice not in ("Ja", "100% Remote"):
                remote_zelle.append(f"\n{s.homeoffice}", style="dim green")
        elif s.homeoffice:
            remote_zelle = Text(f"HO: {s.homeoffice}", style="yellow")
        else:
            remote_zelle = Text("–", style="dim")

        tabelle.add_row(
            str(nr),
            sterne(s.einsteiger_score),
            stelle_zelle,
            s.adresse or "–",
            kuerze(s.beschreibung, 200) or "–",
            kuerze(s.voraussetzungen, 130) if s.voraussetzungen else "–",
            s.gehalt or "k.A.",
            remote_zelle,
            s.arbeitszeit or "–",
            s.veroeffentlicht or "–",
            s.quelle,
            s.url or "–",
        )
    return tabelle


def drucke_zusammenfassung(console: Console, stellen: list[Stelle]) -> None:
    console.print("\n[bold]Legende Einstiegsbewertung:[/bold]")
    console.print("  [bold green]★★★[/bold green]  Sehr einsteigerfreundlich  (Score ≥ 4)")
    console.print("  [bold yellow]★★☆[/bold yellow]  Einsteigerfreundlich       (Score 2–3)")
    console.print("  [yellow]★☆☆[/yellow]  Neutral / unklar           (Score 0–1)")
    console.print("  [dim red]✗[/dim red]    Erfahrung erwartet         (Score < 0)")

    console.print("\n[bold]Statistik:[/bold]")
    console.print(f"  Stellen gesamt:             {len(stellen)}")
    console.print(f"  Davon Remote/Homeoffice:    {sum(s.remote for s in stellen)}")
    console.print(f"  Einsteiger geeignet (≥★★☆): {sum(s.einsteiger_score >= 2 for s in stellen)}")
    console.print(f"  Top Einstieg (★★★):         {sum(s.einsteiger_score >= 4 for s in stellen)}")


def exportiere_csv(stellen: list[Stelle], pfad: Path) -> None:
    # utf-8-sig: mit BOM, damit Excel Umlaute richtig erkennt
    with open(pfad, "w", newline="", encoding="utf-8-sig") as datei:
        schreiber = csv.DictWriter(datei, fieldnames=CSV_FELDER)
        schreiber.writeheader()
        for rang, s in enumerate(stellen, 1):
            schreiber.writerow({
                "rang": rang,
                "einsteiger_score": s.einsteiger_score,
                "einsteiger_signale": " | ".join(s.einsteiger_signale),
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
