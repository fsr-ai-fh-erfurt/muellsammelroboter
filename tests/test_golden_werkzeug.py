"""Das Aufnehmen der Golden Tests: ein unbekannter Name ist ein Fehler, und ein
Fehler beim Aufnehmen darf keine halb geschriebenen Dateien hinterlassen."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from contextlib import ExitStack
from unittest import mock

from engine import config as config_modul
from tests import golden_hilfe, run


class TestUnbekannterName(unittest.TestCase):
    def test_aufnehmen_meldet_den_unbekannten_namen(self):
        with mock.patch.object(golden_hilfe, "szenarien", return_value=[]):
            with self.assertRaises(ValueError) as kontext:
                golden_hilfe.aufnehmen(nur="gibtsnicht")
        self.assertIn("gibtsnicht", str(kontext.exception))

    def test_run_bricht_mit_fehlercode_ab(self):
        fehler = io.StringIO()
        with contextlib.redirect_stderr(fehler):
            with self.assertRaises(SystemExit) as kontext:
                run.main(["--golden-neu", "--nur", "gibtsnicht"])
        self.assertNotEqual(kontext.exception.code, 0)
        self.assertIn("gibtsnicht", fehler.getvalue())


class TestAtomaresAufnehmen(unittest.TestCase):
    def szenarien(self):
        return [
            {"name": "eins", "seed": 1, "ticks": 1, "spieler": 2,
             "bots": ["a.py", "b.py"]},
            {"name": "zwei", "seed": 2, "ticks": 1, "spieler": 2,
             "bots": ["a.py", "b.py"]},
        ]

    def patcher(self, ordner, szenarien, spielen):
        return [
            mock.patch.object(golden_hilfe, "ORDNER", ordner),
            mock.patch.object(golden_hilfe, "szenarien", return_value=szenarien),
            mock.patch.object(golden_hilfe, "spielen", side_effect=spielen),
            mock.patch.object(golden_hilfe, "erwartung", return_value={}),
        ]

    def test_fehler_beim_aufnehmen_laesst_die_dateien_unberuehrt(self):
        with tempfile.TemporaryDirectory() as ordner:
            alt = json.dumps({"config": config_modul.lade().als_dict()},
                             ensure_ascii=False, indent=2, sort_keys=True)
            zieldatei = os.path.join(ordner, "eins.json")
            with open(zieldatei, "w", encoding="utf-8") as datei:
                datei.write(alt)

            def spielen(szenario, config):
                if szenario["name"] == "zwei":
                    raise RuntimeError("absichtlich kaputt")
                return object()

            with ExitStack() as stapel:
                for pflaster in self.patcher(ordner, self.szenarien(), spielen):
                    stapel.enter_context(pflaster)
                with self.assertRaises(RuntimeError):
                    golden_hilfe.aufnehmen()

            with open(zieldatei, "r", encoding="utf-8") as datei:
                self.assertEqual(datei.read(), alt)
            self.assertEqual(sorted(os.listdir(ordner)), ["eins.json"])

    def test_geschrieben_wird_erst_nach_allen_spielen(self):
        with tempfile.TemporaryDirectory() as ordner:
            gesehen = []

            def spielen(szenario, config):
                gesehen.append(sorted(os.listdir(ordner)))
                return object()

            with ExitStack() as stapel:
                for pflaster in self.patcher(ordner, self.szenarien(), spielen):
                    stapel.enter_context(pflaster)
                namen = golden_hilfe.aufnehmen()

            self.assertEqual(namen, ["eins", "zwei"])
            self.assertEqual(gesehen, [[], []])
            self.assertEqual(sorted(os.listdir(ordner)), ["eins.json", "zwei.json"])

    def test_nur_waehlt_genau_ein_szenario(self):
        with tempfile.TemporaryDirectory() as ordner:
            with ExitStack() as stapel:
                for pflaster in self.patcher(ordner, self.szenarien(),
                                             lambda szenario, config: object()):
                    stapel.enter_context(pflaster)
                namen = golden_hilfe.aufnehmen(nur="zwei")

            self.assertEqual(namen, ["zwei"])
            self.assertEqual(sorted(os.listdir(ordner)), ["zwei.json"])
            with open(os.path.join(ordner, "zwei.json"), "r", encoding="utf-8") as datei:
                self.assertEqual(json.load(datei)["szenario"]["name"], "zwei")


if __name__ == "__main__":
    unittest.main()
