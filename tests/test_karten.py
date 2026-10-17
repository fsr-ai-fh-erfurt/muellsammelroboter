"""Innenwände: Kartenwahl, Symmetrie, Blockade, Wegfindung, Aufzeichnung."""

import unittest

from engine import config as config_modul
from engine.game import Spiel
from engine.world import Welt
from engine.zustand import Zustand
from tests.hilfen import SkriptBot, config, lade, setze, spiel_bauen

WAND = [{"name": "Wand", "waende": [[7, 7]]}]


def karten_config(karten):
    return config(**{"spiel.karten": karten})


class TestKartenaufbau(unittest.TestCase):
    def test_wand_ist_bei_zwei_spielern_punktsymmetrisch(self):
        welt = Welt(karten_config(WAND), ["A", "B"], seed=1)
        self.assertEqual(welt.hindernisse, {(7, 7), (16, 16)})

    def test_wand_ist_bei_vier_spielern_drehsymmetrisch(self):
        welt = Welt(karten_config(WAND), ["A", "B", "C", "D"], seed=1)
        self.assertEqual(welt.hindernisse, {(7, 7), (16, 7), (16, 16), (7, 16)})

    def test_der_seed_waehlt_die_karte(self):
        karten = [{"name": "A", "waende": []}, {"name": "B", "waende": [[7, 7]]}]
        cfg = karten_config(karten)
        namen = [Welt(cfg, ["A", "B"], seed=s).karte_name for s in (0, 1, 2, 3)]
        self.assertEqual(namen, ["A", "B", "A", "B"])

    def test_nichts_liegt_auf_der_innenwand(self):
        for karte in config_modul.lade().spiel.karten:
            cfg = karten_config([karte])
            bots = [SkriptBot("A"), SkriptBot("B"), SkriptBot("C"), SkriptBot("D")]
            spiel = Spiel(cfg, bots, seed=1, spieler=4, aufzeichnen=False)
            for _ in range(50):
                spiel.schritt()
            self.assertEqual(set(spiel.welt.muell) & spiel.welt.hindernisse, set(),
                             "Müll auf einer Wand der Karte %r" % karte["name"])

    def test_sicht_und_abbild_enthalten_die_waende(self):
        spiel = spiel_bauen([["warte"], ["warte"]], cfg=karten_config(WAND))
        sicht = spiel.welt.sicht(0)
        self.assertEqual({(h["x"], h["y"]) for h in sicht["hindernisse"]}, {(7, 7), (16, 16)})
        self.assertEqual(spiel.welt.abbild()["hindernisse"], [[7, 7], [16, 16]])
        self.assertEqual(spiel.welt.abbild()["karte"], "Wand")


class TestBlockade(unittest.TestCase):
    def test_fahren_gegen_die_innenwand(self):
        spiel = spiel_bauen([["rechts"], ["warte"]], cfg=karten_config(WAND))
        setze(spiel, 0, 6, 7)
        setze(spiel, 1, 20, 20)
        spiel.schritt()
        self.assertEqual((spiel.welt.roboter[0].x, spiel.welt.roboter[0].y), (6, 7))

    def test_schub_gegen_die_innenwand_klaut_trotzdem(self):
        spiel = spiel_bauen([["rechts"], ["warte"]], cfg=karten_config(WAND))
        angreifer = setze(spiel, 0, 5, 7)
        opfer = setze(spiel, 1, 6, 7)
        lade(spiel, 1, [("metall", 80)])
        akku_vorher = (angreifer.akku, opfer.akku)
        spiel.schritt()
        self.assertEqual((opfer.x, opfer.y), (6, 7))       # nicht geschoben
        self.assertEqual(opfer.ladung, [])                  # aber bestohlen
        self.assertLess(angreifer.akku, akku_vorher[0])
        self.assertLess(opfer.akku, akku_vorher[1])

    def test_wegfindung_umfaehrt_die_innenwand(self):
        welt = Welt(karten_config(WAND), ["A", "B"], seed=1)
        welt.muell.clear()
        welt.roboter[0].x, welt.roboter[0].y = 6, 7
        welt.roboter[1].x, welt.roboter[1].y = 20, 20
        z = Zustand(welt.sicht(0))
        self.assertEqual(z.abstand_zu_feld(8, 7), 4)        # oben oder unten herum
        self.assertIn(z.fahre_zu_feld(8, 7), ("oben", "unten"))


class TestKartenpruefung(unittest.TestCase):
    def daten(self, karten):
        daten = config_modul.lade().als_dict()
        daten["spiel"]["karten"] = karten
        return daten

    def test_karten_fehlen(self):
        daten = config_modul.lade().als_dict()
        del daten["spiel"]["karten"]
        with self.assertRaises(ValueError) as gefangen:
            config_modul.pruefe(daten)
        self.assertIn("karten", str(gefangen.exception))

    def test_leere_kartenliste(self):
        with self.assertRaises(ValueError) as gefangen:
            config_modul.pruefe(self.daten([]))
        self.assertIn("mindestens eine Karte", str(gefangen.exception))

    def test_wand_neben_einem_depot(self):
        with self.assertRaises(ValueError) as gefangen:
            config_modul.pruefe(self.daten([{"name": "Ecke", "waende": [[2, 3]]}]))
        self.assertIn("Depot", str(gefangen.exception))

    def test_wand_auf_einem_depot(self):
        with self.assertRaises(ValueError) as gefangen:
            config_modul.pruefe(self.daten([{"name": "Ecke", "waende": [[2, 2]]}]))
        self.assertIn("Depot", str(gefangen.exception))

    def test_wand_ausserhalb_des_feldes(self):
        with self.assertRaises(ValueError) as gefangen:
            config_modul.pruefe(self.daten([{"name": "Rand", "waende": [[0, 5]]}]))
        self.assertIn("außerhalb", str(gefangen.exception))

    def test_zerrissenes_feld_wird_erkannt(self):
        from engine.config import _karte_verbunden_pruefen
        # Ein durchgehender Wall quer über das Feld trennt die Hälften.
        felder = {(x, 11) for x in range(1, 23)}
        with self.assertRaises(ValueError) as gefangen:
            _karte_verbunden_pruefen("Schnitt", 24, 24, felder)
        self.assertIn("zerreißt", str(gefangen.exception))


if __name__ == "__main__":
    unittest.main()
