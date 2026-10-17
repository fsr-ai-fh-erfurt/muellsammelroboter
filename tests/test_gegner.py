"""Die beiden Listen-Bots spielen ihre beworbene Strategie.

Der Lauerer soll das gegnerische Depot tatsächlich besetzen und rammen, der
Fassbluffer sein Fass nur noch bei Aussicht auf einen Angriff aufnehmen. Geprüft
wird das Verhalten, nicht die genauen Zahlen: fester Seed, lockere Schwellen.
Der Fassbluffer-Teil läuft ohne Bot-Prozesse, damit sich die Szene exakt stellen
lässt.
"""

import importlib.util
import os
import unittest

from engine import config as config_modul
from engine import spielleiter
from engine.world import Muell, Welt
from engine.zustand import Zustand
from tests.hilfen import config

BOT_ORDNER = spielleiter.BOT_ORDNER


def modul_laden(datei):
    """Lädt eine Bot-Datei im Testprozess — für gestellte Szenen."""
    pfad = os.path.join(BOT_ORDNER, datei)
    spec = importlib.util.spec_from_file_location("test_" + datei[:-3], pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def bot_laden(datei):
    return modul_laden(datei).Roboter()


class TestLauerer(unittest.TestCase):

    def zustand_mit_gegnern(self, anzahl_gegner):
        cfg = config()
        namen = ["Der Lauerer"] + ["Gegner %d" % i for i in range(anzahl_gegner)]
        welt = Welt(cfg, namen, seed=1)
        welt.muell.clear()
        return Zustand(welt.sicht(0))

    def test_wache_skaliert_mit_der_gegnerzahl(self):
        """Im Duell bleibt die Wachdauer, in der Vierergruppe wird sie geteilt."""
        modul = modul_laden("lauerer.py")
        bot = modul.Roboter()
        duell = self.zustand_mit_gegnern(1)
        self.assertEqual(bot._wache(duell), modul.WACHE,
                         "im Duell muss die Wache unverändert bleiben")
        gruppe = self.zustand_mit_gegnern(3)
        self.assertEqual(bot._wache(gruppe), modul.WACHE // 3,
                         "in der Vierergruppe muss die Wache kürzer sein")

    def test_lauerer_besetzt_den_posten_und_rammt(self):
        """Seed 7: Er kommt ans gegnerische Depot und rammt den Heimkehrer."""
        aufzeichnung = spielleiter.match(
            config_modul.lade(), [os.path.join(BOT_ORDNER, "lauerer.py"),
                                  os.path.join(BOT_ORDNER, "fleissig.py")], seed=7)

        statistik = aufzeichnung["ergebnis"]["roboter"][0]["statistik"]
        self.assertGreaterEqual(statistik["rammangriffe"], 1,
                                "der Lauerer hat kein einziges Mal gerammt")

        gegner_depot = aufzeichnung["spieler"][1]["depot"]
        nah = 0
        for tick in aufzeichnung["ticks"]:
            roboter = tick["roboter"][0]
            if (abs(roboter["x"] - gegner_depot[0])
                    + abs(roboter["y"] - gegner_depot[1]) <= 2):
                nah += 1
        self.assertGreaterEqual(
            nah, 1, "der Lauerer kam dem gegnerischen Depot nie nahe genug")


class TestFassbluffer(unittest.TestCase):

    def szene(self, gegner_ladung, fass=False, positives_teil=False):
        """Zwei Roboter samt Fass in Reichweite; der Gegner trägt `gegner_ladung`."""
        cfg = config()
        welt = Welt(cfg, ["Fassbluffer", "Gegner"], seed=1)
        welt.muell.clear()
        bluffer = welt.roboter[0]
        bluffer.x, bluffer.y = 5, 5
        if fass:
            bluffer.ladung.append({"sorte": "radioaktiv", "wert": cfg.radioaktiv.wert})
        if positives_teil:
            bluffer.ladung.append({"sorte": "papier", "wert": 20})
        gegner = welt.roboter[1]
        gegner.x, gegner.y = 10, 5        # in Sichtweite (Radius 6)
        gegner.ladung = [{"sorte": "papier", "wert": 20}
                         for _ in range(gegner_ladung)]
        welt.muell[(8, 5)] = Muell(8, 5, "radioaktiv", cfg.radioaktiv.wert, 0,
                                   radioaktiv=True)
        return Zustand(welt.sicht(0))

    def test_ohne_sichtbaren_gegner_bleibt_das_fass_liegen(self):
        bot = bot_laden("fassbluffer.py")
        bot.entscheide(self.szene(gegner_ladung=0))
        self.assertNotEqual(bot.modus, "besorgen",
                            "ohne Publikum darf der Bluffer kein Fass holen")

    def test_schwerer_gegner_in_reichweite_laesst_ihn_das_fass_holen(self):
        bot = bot_laden("fassbluffer.py")
        bot.entscheide(self.szene(gegner_ladung=5))
        self.assertEqual(bot.modus, "besorgen",
                         "mit beladenem Gegner in Reichweite lohnt der Bluff")

    def test_mit_fass_und_positivem_teil_blufft_er(self):
        """Erst Fass plus ein positives Teil ist dem Angreifer einen Ramm wert."""
        bot = bot_laden("fassbluffer.py")
        bot.entscheide(self.szene(gegner_ladung=5, fass=True, positives_teil=True))
        self.assertEqual(bot.modus, "bluffen",
                         "mit Fass und positivem Teil muss er bluffen")

    def test_nur_fass_ladung_blufft_nicht(self):
        bot = bot_laden("fassbluffer.py")
        bot.entscheide(self.szene(gegner_ladung=5, fass=True))
        self.assertNotEqual(bot.modus, "bluffen",
                            "ein einzelnes Fass lohnt den Angriff nicht")

    def test_geduld_beendet_das_nachstellen(self):
        """Nach GEDULD Ticks mit getragenem Fass gibt er den Bluff auf."""
        modul = modul_laden("fassbluffer.py")
        bot = modul.Roboter()
        zustand = self.szene(gegner_ladung=5, fass=True, positives_teil=True)
        for _ in range(modul.GEDULD):
            bot._bluff_verfolgen(zustand, True)
        self.assertFalse(bot.aufgegeben,
                         "genau GEDULD Ticks sind noch keine Aufgabe")
        bot._bluff_verfolgen(zustand, True)
        self.assertTrue(bot.aufgegeben,
                        "länger als GEDULD getragen muss der Bluff enden")
        bot.entscheide(zustand)
        self.assertEqual(bot.modus, "sammeln",
                         "nach der Geduld stellt er nicht mehr nach")


if __name__ == "__main__":
    unittest.main()
