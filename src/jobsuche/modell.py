"""Das gemeinsame Datenmodell: Jede Quelle liefert ihre Treffer als Liste von `Stelle`."""

from dataclasses import dataclass, field


@dataclass
class Stelle:
    titel: str = ""
    unternehmen: str = ""
    adresse: str = ""
    beschreibung: str = ""
    voraussetzungen: str = ""
    gehalt: str = "k.A."
    remote: bool = False
    homeoffice: str = ""
    arbeitszeit: str = ""
    veroeffentlicht: str = ""  # ISO-Datum "JJJJ-MM-TT" oder leer
    url: str = ""
    quelle: str = ""
    einsteiger_score: int = 0
    # Gefundene Signale mit Vorzeichen, z. B. ["+Junior", "-Senior"]
    einsteiger_signale: list[str] = field(default_factory=list)
