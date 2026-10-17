"""Die mitgelieferten Gegner: alle laden, spielen und halten ihr Versprechen.

Der Kurzlauf deckt jeden der fünf Bots mit echten Prozessen ab — kein Fehler,
kein überzogener Zug. Dazu eine Aussage, die das Feld erst nützlich macht:
Rumpelstilzchen, der Zufallsbot, verliert gegen Fleißig.
"""

import os
import unittest

from engine import config as config_modul
from engine import spielleiter
from engine.game import Spiel
from engine.runner import Anschlussgruppe

PROJEKT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOT_ORDNER = os.path.join(PROJEKT, "bots")

ERWARTET = {"fassbluffer", "fleissig", "hausmeister", "lauerer", "rumpelstilzchen"}


def pfad(name):
    return os.path.join(BOT_ORDNER, name + ".py")


class TestGegner(unittest.TestCase):

    def test_alle_bots_sind_auflistbar(self):
        eintraege = spielleiter.mitgelieferte_gegner()
        self.assertEqual({e["datei"] for e in eintraege},
                         {name + ".py" for name in ERWARTET})
        for eintrag in eintraege:
            self.assertTrue(eintrag["name"], eintrag["datei"])
            self.assertTrue(eintrag["beschreibung"], eintrag["datei"])

    def test_jeder_bot_spielt_eine_kurze_runde(self):
        """Zwei Partien mit je vier Bots decken alle fünf ab."""
        cfg = config_modul.lade()
        pfade = sorted(pfad(name) for name in ERWARTET)
        for seed, gruppe in enumerate((pfade[:4], pfade[-4:]), start=1):
            with Anschlussgruppe(gruppe, cfg) as anschluesse:
                spiel = Spiel(cfg, anschluesse, seed=seed, spieler=4,
                              runden_laenge=100, aufzeichnen=False)
                spiel.spiele()
            for anschluss in anschluesse:
                self.assertEqual(anschluss.fehler, [], anschluss.name)
                self.assertEqual(anschluss.statistik["ueberzogen"], 0, anschluss.name)

    def test_zufallsbot_verliert_gegen_fleissig(self):
        cfg = config_modul.lade()
        siege = 0
        for seed in range(1, 5):
            ergebnis = spielleiter.nur_ergebnis(
                cfg, [pfad("fleissig"), pfad("rumpelstilzchen")], seed=seed)
            if ergebnis["sieger"] == 0:
                siege += 1
        self.assertGreaterEqual(siege, 3, "Rumpelstilzchen schlägt Fleißig zu oft")


if __name__ == "__main__":
    unittest.main()
