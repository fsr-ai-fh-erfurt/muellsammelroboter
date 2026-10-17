"""Bot-Listen: Nur Dateien mit `entscheide` sind Roboter, Hilfsmodule nicht."""

import os
import tempfile
import unittest

from engine import spielleiter

BOT = ('class Roboter:\n'
       '    def entscheide(self, zustand):\n'
       '        return "warte"\n')
FUNKTION = 'def entscheide(zustand):\n    return "warte"\n'
HILFE = 'PUNKTE = 3\n\n\ndef hilfe():\n    return PUNKTE\n'


class TestBotListe(unittest.TestCase):

    def test_hilfsmodul_ist_kein_bot(self):
        with tempfile.TemporaryDirectory() as ordner:
            for name, inhalt in (("team.py", BOT), ("helfer.py", HILFE),
                                 ("funktion.py", FUNKTION)):
                with open(os.path.join(ordner, name), "w", encoding="utf-8") as datei:
                    datei.write(inhalt)
            dateien = [e["datei"] for e in spielleiter.bots_auflisten(ordner)]
        self.assertEqual(dateien, ["funktion.py", "team.py"])

    def test_mitgelieferte_gegner_sind_vollstaendig(self):
        dateien = [e["datei"] for e in spielleiter.mitgelieferte_gegner()]
        self.assertEqual(len(dateien), 5)
        for name in ("hausmeister.py", "fleissig.py", "lauerer.py", "fassbluffer.py"):
            self.assertIn(name, dateien)


if __name__ == "__main__":
    unittest.main()
