"""Aufzeichnungsformat: schreiben, wieder lesen, verlustfrei."""

import os
import tempfile
import unittest

from engine import recording, spielleiter
from tests.hilfen import config


class TestAufzeichnung(unittest.TestCase):

    def spielen(self, ticks=20):
        bots = [os.path.join(spielleiter.BOT_ORDNER, "fleissig.py"),
                os.path.join(spielleiter.BOT_ORDNER, "rumpelstilzchen.py")]
        return spielleiter.match(config(), bots, seed=2, ticks=ticks)

    def test_speichern_und_laden_ist_verlustfrei(self):
        aufzeichnung = self.spielen()
        with tempfile.TemporaryDirectory() as ordner:
            pfad = os.path.join(ordner, "lauf.json")
            recording.speichern(pfad, aufzeichnung)
            zurueck = recording.laden(pfad)
        self.assertEqual(zurueck, aufzeichnung)

    def test_unbekannte_formatversion_wird_gemeldet(self):
        aufzeichnung = self.spielen()
        aufzeichnung["version"] = 99
        with tempfile.TemporaryDirectory() as ordner:
            pfad = os.path.join(ordner, "lauf.json")
            recording.speichern(pfad, aufzeichnung)
            with self.assertRaises(ValueError) as gefangen:
                recording.laden(pfad)
        self.assertIn("Formatversion", str(gefangen.exception))

    def test_format_version_und_ticks_sind_da(self):
        aufzeichnung = self.spielen()
        self.assertEqual(aufzeichnung["version"], recording.FORMAT_VERSION)
        self.assertIn("start", aufzeichnung)
        self.assertEqual(len(aufzeichnung["ticks"]), 20)
        self.assertEqual(aufzeichnung["ticks"][0]["tick"], 1)
        self.assertEqual(aufzeichnung["ticks"][-1]["tick"], 20)


if __name__ == "__main__":
    unittest.main()
