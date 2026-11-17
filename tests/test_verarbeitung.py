from jobsuche.modell import Stelle
from jobsuche.verarbeitung import dedupliziere, entferne_nicht_entwickler, normalisiere_titel


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
