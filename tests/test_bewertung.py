import pytest

from jobsuche.bewertung import (
    RELEVANTE_BERUFE_TITEL,
    berechne_einsteiger_score,
    ist_nicht_entwickler_stelle,
)
from jobsuche.modell import Stelle


def test_junior_stelle_bekommt_positive_punkte():
    score, signale = berechne_einsteiger_score(Stelle(titel="Junior Softwareentwickler (m/w/d)"))
    assert score > 0
    assert "+Junior" in signale


def test_senior_mit_mehrjaehriger_erfahrung_ist_negativ():
    stelle = Stelle(titel="Senior Developer", beschreibung="mehrjährige Berufserfahrung in Java")
    score, signale = berechne_einsteiger_score(stelle)
    assert score == -7
    assert signale == ["-Senior", "-Mehrjährige Erfahrung"]


def test_junior_bis_senior_hebt_senior_abzug_auf():
    score, _ = berechne_einsteiger_score(Stelle(titel="Java-Entwickler (Junior bis Senior)"))
    assert score == 3 + 3 - 3  # Junior + "Junior bis Senior" - Senior


def test_ohne_signale_ist_neutral():
    assert berechne_einsteiger_score(Stelle(titel="Softwareentwickler")) == (0, [])


@pytest.mark.parametrize("titel", ["Sales Manager DACH", "Customer Success Lead", "Recruiter IT"])
def test_nicht_entwickler_stellen_werden_erkannt(titel):
    assert ist_nicht_entwickler_stelle(Stelle(titel=titel))


@pytest.mark.parametrize("titel", ["Fachinformatiker Anwendungsentwicklung", "Backend Developer", "Junior Dev (Python)"])
def test_entwicklertitel_sind_relevant(titel):
    assert RELEVANTE_BERUFE_TITEL.search(titel)


@pytest.mark.parametrize("titel", ["Credit Analyst", "Buchhalter", "Projektkoordinator"])
def test_fremde_titel_sind_nicht_relevant(titel):
    # Wortgrenzen: "it" in "Credit" darf nicht als IT zählen
    assert not RELEVANTE_BERUFE_TITEL.search(titel)
