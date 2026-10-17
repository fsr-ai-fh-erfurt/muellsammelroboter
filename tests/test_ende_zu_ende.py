"""Vom Pseudocode bis zum gespielten Match — der Weg, den ein Team in der Werkstatt geht."""

import os
import tempfile
import unittest

from engine import spielleiter
from language.compiler import uebersetzen
from tests.hilfen import config

PSEUDOCODE = """\
IF ladung_ist_voll THEN fahre_zu depot
IF akku < 25 THEN fahre_zu depot
IF gegner_sichtbar AND gegner_ladung >= 4 THEN ramme gegner
IF muell_in_zone THEN fahre_zu naechster_muell(in_zone)
ELSE fahre_zu naechster_muell
"""

AUTOMAT = """\
LET heimkehr = 25

STATE sammeln
  IF restliche_ticks < heimkehr THEN GOTO heimweg
  IF ladung_ist_voll THEN GOTO heimweg
  IF akku < 30 THEN GOTO heimweg
  ELSE fahre_zu BEST muell BY wert * bonus - 3 * abstand

STATE heimweg
  IF ladung_ist_leer AND restliche_ticks > heimkehr THEN GOTO sammeln
  ELSE fahre_zu depot
"""


class TestEndeZuEnde(unittest.TestCase):
    def test_erzeugter_bot_spielt_ein_ganzes_match(self):
        ergebnis = uebersetzen(PSEUDOCODE, "Team Testlauf", "Ende-zu-Ende")
        self.assertTrue(ergebnis["gueltig"], ergebnis["fehler"])
        with tempfile.TemporaryDirectory() as ordner:
            pfad = os.path.join(ordner, "team_testlauf.py")
            with open(pfad, "w", encoding="utf-8") as datei:
                datei.write(ergebnis["quelle"])
            cfg = config()
            aufzeichnung = spielleiter.match(
                cfg, [pfad, os.path.join(spielleiter.BOT_ORDNER, "fleissig.py")],
                seed=3, ticks=120)

        self.assertEqual(aufzeichnung["spieler"][0]["name"], "Team Testlauf")
        self.assertEqual(len(aufzeichnung["ticks"]), 120)
        self.assertIsNotNone(aufzeichnung["ergebnis"])
        for bot in aufzeichnung["bots"]:
            self.assertEqual(bot["fehler"], [], "der erzeugte Bot lief nicht sauber")
        self.assertGreater(
            aufzeichnung["ergebnis"]["roboter"][0]["statistik"]["aufgenommen"], 0,
            "der erzeugte Bot hat nichts eingesammelt")

    def test_automat_spielt_ein_ganzes_match(self):
        """Ein Roboter mit Modi muss dieselbe Strecke laufen wie einer ohne."""
        ergebnis = uebersetzen(AUTOMAT, "Team Automat", "Zustandsautomat")
        self.assertTrue(ergebnis["gueltig"], ergebnis["fehler"])
        with tempfile.TemporaryDirectory() as ordner:
            pfad = os.path.join(ordner, "team_automat.py")
            with open(pfad, "w", encoding="utf-8") as datei:
                datei.write(ergebnis["quelle"])
            aufzeichnung = spielleiter.match(
                config(), [pfad, os.path.join(spielleiter.BOT_ORDNER, "fleissig.py")],
                seed=3, ticks=200)

        for bot in aufzeichnung["bots"]:
            self.assertEqual(bot["fehler"], [], "der Automat lief nicht sauber")
        statistik = aufzeichnung["ergebnis"]["roboter"][0]["statistik"]
        self.assertGreater(statistik["aufgenommen"], 0, "der Automat hat nichts gesammelt")
        self.assertGreater(statistik["abgeliefert_stueck"], 0,
                           "der Automat ist nie heimgefahren — der Moduswechsel greift nicht")

    def test_rest_durch_null_laesst_den_bot_weiterlaufen(self):
        quelltext = ("LET null = 0\n"
                     "IF 100 % null > 1 THEN warte\n"
                     "ELSE fahre_zu naechster_muell")
        ergebnis = uebersetzen(quelltext, "Team Rest")
        self.assertTrue(ergebnis["gueltig"], ergebnis["fehler"])
        with tempfile.TemporaryDirectory() as ordner:
            pfad = os.path.join(ordner, "team_rest.py")
            with open(pfad, "w", encoding="utf-8") as datei:
                datei.write(ergebnis["quelle"])
            aufzeichnung = spielleiter.match(
                config(), [pfad, os.path.join(spielleiter.BOT_ORDNER, "fleissig.py")],
                seed=3, ticks=40)
        self.assertEqual(aufzeichnung["bots"][0]["fehler"], [])
        self.assertGreater(
            aufzeichnung["ergebnis"]["roboter"][0]["statistik"]["aufgenommen"], 0)

    def test_greifende_regel_wird_aufgezeichnet(self):
        ergebnis = uebersetzen(PSEUDOCODE, "Team Regelanzeige")
        with tempfile.TemporaryDirectory() as ordner:
            pfad = os.path.join(ordner, "team.py")
            with open(pfad, "w", encoding="utf-8") as datei:
                datei.write(ergebnis["quelle"])
            aufzeichnung = spielleiter.match(
                config(), [pfad, os.path.join(spielleiter.BOT_ORDNER, "fleissig.py")],
                seed=3, ticks=40)
        regeln = {tick["regeln"][0] for tick in aufzeichnung["ticks"]}
        self.assertTrue(regeln - {None},
                        "es wurde nie festgehalten, welche Regel gegriffen hat")


if __name__ == "__main__":
    unittest.main()
