from jobsuche.modell import Stelle
from jobsuche.verarbeitung import dedupliziere, entferne_nicht_entwickler, normalisiere_titel, sortiere


def test_normalisiere_titel_entfernt_klammern_und_geschlecht():
    assert normalisiere_titel("Softwareentwickler (m/w/d) (Leipzig)") == "softwareentwickler"
    assert normalisiere_titel("Java  Developer m/f/d") == "java developer"


def test_dedupliziere_erkennt_gleiche_stelle_aus_zwei_quellen():
    stellen = [
        Stelle(titel="Softwareentwickler (m/w/d)", unternehmen="ACME GmbH", quelle="BA"),
        Stelle(titel="Softwareentwickler", unternehmen="acme gmbh ", quelle="Arbeitnow"),
        Stelle(titel="Softwareentwickler", unternehmen="Andere AG", quelle="BA"),
    ]
    ergebnis = dedupliziere(stellen)
    assert [s.quelle for s in ergebnis] == ["BA", "BA"]
    assert ergebnis[1].unternehmen == "Andere AG"


def test_entferne_nicht_entwickler():
    stellen = [Stelle(titel="Account Manager"), Stelle(titel="Python Developer")]
    assert [s.titel for s in entferne_nicht_entwickler(stellen)] == ["Python Developer"]


def test_sortiere_nach_score_dann_neueste_zuerst():
    stellen = [
        Stelle(titel="alt", einsteiger_score=2, veroeffentlicht="2026-10-01"),
        Stelle(titel="ohne Datum", einsteiger_score=2, veroeffentlicht=""),
        Stelle(titel="neu", einsteiger_score=2, veroeffentlicht="2026-11-15"),
        Stelle(titel="bester Score", einsteiger_score=5, veroeffentlicht="2026-01-01"),
    ]
    assert [s.titel for s in sortiere(stellen)] == ["bester Score", "neu", "alt", "ohne Datum"]
