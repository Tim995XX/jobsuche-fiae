"""Gesamtablauf über die Kommandozeile, mit ersetzten Quellen statt Netzwerk."""

import csv

import pytest

from jobsuche import __main__ as cli
from jobsuche.modell import Stelle


@pytest.fixture
def quellen(monkeypatch):
    """Ersetzt alle Quellen; gibt ein Dict zurück, in das ein Test Treffer je Quelle legt."""
    treffer = {"ba": [], "arbeitnow": [], "indeed": [], "jobicy": [], "remotive": []}
    monkeypatch.setattr(cli.bundesagentur, "suche", lambda ort, umkreis: treffer["ba"])
    monkeypatch.setattr(cli.arbeitnow, "suche", lambda ort: treffer["arbeitnow"])
    monkeypatch.setattr(cli.indeed, "suche", lambda ort: treffer["indeed"])
    monkeypatch.setattr(cli.jobicy, "suche", lambda: treffer["jobicy"])
    monkeypatch.setattr(cli.remotive, "suche", lambda: treffer["remotive"])
    return treffer


def test_csv_enthaelt_bewertete_stellen_ohne_duplikate_und_vertrieb(quellen, tmp_path):
    quellen["ba"] = [Stelle(titel="Junior Softwareentwickler (m/w/d)", unternehmen="A", quelle="BA")]
    quellen["arbeitnow"] = [
        Stelle(titel="Junior Softwareentwickler", unternehmen="A", quelle="Arbeitnow"),  # Duplikat
        Stelle(titel="Sales Manager", unternehmen="B", quelle="Arbeitnow"),               # kein Entwickler
    ]
    ziel = tmp_path / "stellen.csv"

    assert cli.main(["--csv", str(ziel)]) == 0

    with open(ziel, encoding="utf-8-sig") as datei:
        zeilen = list(csv.DictReader(datei))
    assert len(zeilen) == 1
    assert zeilen[0]["quelle"] == "BA"
    assert "+Junior" in zeilen[0]["einsteiger_signale"]


def test_ohne_treffer_endet_mit_fehlercode(quellen, tmp_path):
    assert cli.main(["--csv", str(tmp_path / "x.csv")]) == 1
    assert not (tmp_path / "x.csv").exists()


def test_ungueltiger_umkreis_wird_abgelehnt():
    with pytest.raises(SystemExit):
        cli.lies_argumente(["--umkreis", "30"])
