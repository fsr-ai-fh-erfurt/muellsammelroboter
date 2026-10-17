"""Hilfen für die Tests.

`SkriptBot` läuft absichtlich im selben Prozess: für Tests der Bewegungsauflösung
brauchen wir exakt vorgegebene Aktionen, nicht die Prozessschicht. Die Prozessschicht
selbst wird in test_runner.py geprüft, die Golden Tests laufen ebenfalls über sie.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import config as config_modul   # noqa: E402
from engine.game import Spiel               # noqa: E402


class SkriptBot:
    """Spielt eine feste Folge von Aktionen ab, danach immer `warte`."""

    def __init__(self, name, aktionen=()):
        self.name = name
        self.aktionen = list(aktionen)
        self.index = 0

    def frage(self, sicht):
        if self.index < len(self.aktionen):
            aktion = self.aktionen[self.index]
        else:
            aktion = "warte"
        self.index += 1
        return (aktion, None)


def config(**aenderungen):
    """Config laden, optional einzelne Abschnitte überschreiben.

    Ohne Angabe gilt die leere Karte: Tests der Bewegung und Wegfindung setzen
    Roboter und Müll auf feste Felder — die dürfen nicht zufällig auf einer
    Innenwand der seed-gewählten Karte landen. Kartentests übergeben `karten=...`.
    """
    daten = config_modul.lade().als_dict()
    daten["spiel"]["karten"] = [{"name": "Testfläche", "waende": []}]
    for pfad, wert in aenderungen.items():
        teile = pfad.split(".")
        ziel = daten
        for teil in teile[:-1]:
            ziel = ziel[teil]
        ziel[teile[-1]] = wert
    return config_modul.aus_dict(daten)


def spiel_bauen(aktionen_je_bot, seed=1, ticks=20, cfg=None, ohne_muell=True):
    cfg = cfg or config()
    bots = [SkriptBot("B%d" % i, a) for i, a in enumerate(aktionen_je_bot)]
    spiel = Spiel(cfg, bots, seed=seed, runden_laenge=ticks)
    if ohne_muell:
        spiel.welt.muell.clear()
    return spiel


def setze(spiel, index, x, y):
    r = spiel.welt.roboter[index]
    r.x, r.y = x, y
    return r


def depot(spiel, index):
    return spiel.welt.roboter[index].depot


def auf_depot(spiel, index):
    r = spiel.welt.roboter[index]
    r.x, r.y = r.depot
    return r


def positionen(spiel):
    return [(r.x, r.y) for r in spiel.welt.roboter]


def lade(spiel, index, teile):
    """teile: Liste aus (sorte, wert) oder fertigen Ladungs-Dicts (z.B. Ballen)."""
    ladung = []
    for teil in teile:
        if isinstance(teil, dict):
            ladung.append(dict(teil))
        else:
            sorte, wert = teil
            ladung.append({"sorte": sorte, "wert": wert})
    spiel.welt.roboter[index].ladung = ladung
