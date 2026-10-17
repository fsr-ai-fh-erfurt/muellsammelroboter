"""Golden Tests. Schlagen sie an, war es eine bewusste Regeländerung oder ein Fehler."""

import json
import os
import unittest

from engine import config as config_modul
from tests import golden_hilfe


def testfall_bauen(szenario):
    def test(self):
        pfad = golden_hilfe.datei_von(szenario["name"])
        self.assertTrue(
            os.path.exists(pfad),
            "Golden-Datei fehlt. Aufnehmen mit: python3 -m tests.run --golden-neu")
        with open(pfad, "r", encoding="utf-8") as datei:
            inhalt = json.load(datei)
        config = config_modul.aus_dict(inhalt["config"])
        spiel = golden_hilfe.spielen(inhalt["szenario"], config)
        jetzt = golden_hilfe.erwartung(spiel)
        erwartet = inhalt["erwartet"]
        for feld in ("punkte", "akku", "abgeliefert", "positionen", "sieger",
                     "unentschieden"):
            self.assertEqual(jetzt[feld], erwartet[feld],
                             "Golden-Szenario %r: %s weicht ab"
                             % (szenario["name"], feld))
        self.assertEqual(
            jetzt["pruefsumme"], erwartet["pruefsumme"],
            "Golden-Szenario %r: der Spielverlauf hat sich geändert, auch wenn der "
            "Endstand gleich blieb." % szenario["name"])
    return test


class TestGolden(unittest.TestCase):
    pass


for _szenario in golden_hilfe.szenarien():
    setattr(TestGolden, "test_" + _szenario["name"], testfall_bauen(_szenario))


class TestPresseSzenario(unittest.TestCase):
    """Das Presse-Szenario soll nicht nur so heißen — es muss wirklich pressen."""

    def test_der_lauf_enthaelt_mehrere_pressen(self):
        name = "presse_testbot_gegen_sich_selbst"
        with open(golden_hilfe.datei_von(name), "r", encoding="utf-8") as datei:
            inhalt = json.load(datei)
        config = config_modul.aus_dict(inhalt["config"])
        spiel = golden_hilfe.spielen(inhalt["szenario"], config)
        anzahl = sum(1 for tick in spiel.ticks for e in tick["ereignisse"]
                     if e["art"] == "presse")
        self.assertGreaterEqual(anzahl, 10)


if __name__ == "__main__":
    unittest.main()
