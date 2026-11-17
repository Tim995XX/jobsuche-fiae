from jobsuche.text import kuerze, rss_datum, strip_html


def test_strip_html_macht_bloecke_zu_zeilen_und_ersetzt_entitaeten():
    html = "<p>Wir suchen&nbsp;dich</p><ul><li>Python &amp; SQL</li></ul>"
    assert strip_html(html) == "Wir suchen dich\nPython & SQL"


def test_strip_html_fasst_viele_leerzeilen_zusammen():
    assert strip_html("a<br><br><br><br>b") == "a\n\nb"


def test_kuerze_schneidet_an_wortgrenze():
    assert kuerze("eins zwei drei vier", 12) == "eins zwei …"


def test_kuerze_laesst_kurzen_text_unveraendert_und_normalisiert_leerraum():
    assert kuerze("  kurz \n text ", 50) == "kurz text"


def test_rss_datum():
    assert rss_datum("Mon, 03 Nov 2026 10:00:00 +0000") == "2026-11-03"
    assert rss_datum("") == ""
    assert rss_datum("2026-11-03T10:00:00") == "2026-11-03"  # unbekanntes Format: erste 10 Zeichen
