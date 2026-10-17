"""Das Bot-Objekt: Wegfindung, Abstände, Sortennamen."""

import unittest

from engine import config as config_modul
from engine.world import Muell, Welt
from engine.zustand import Zustand, sorte_normal, UNERREICHBAR


def zustand_bauen(seed=1, ohne_muell=True):
    daten = config_modul.lade().als_dict()
    daten["spiel"]["karten"] = [{"name": "Testfläche", "waende": []}]
    welt = Welt(config_modul.aus_dict(daten), ["A", "B"], seed=seed)
    if ohne_muell:
        welt.muell.clear()
    return welt


class TestWegfindung(unittest.TestCase):
    def test_erste_richtung_stimmt(self):
        welt = zustand_bauen()
        welt.roboter[0].x, welt.roboter[0].y = 5, 5
        welt.roboter[1].x, welt.roboter[1].y = 20, 20
        z = Zustand(welt.sicht(0))
        self.assertEqual(z.fahre_zu_feld(8, 5), "rechts")
        self.assertEqual(z.fahre_zu_feld(5, 2), "oben")
        self.assertEqual(z.abstand_zu_feld(8, 5), 3)
        self.assertEqual(z.abstand_zu_feld(8, 8), 6)

    def test_ziel_auf_dem_eigenen_feld(self):
        welt = zustand_bauen()
        welt.roboter[0].x, welt.roboter[0].y = 5, 5
        z = Zustand(welt.sicht(0))
        self.assertEqual(z.fahre_zu_feld(5, 5), "warte")
        self.assertEqual(z.abstand_zu_feld(5, 5), 0)

    def test_gegner_sind_hindernisse_aber_erreichbar(self):
        welt = zustand_bauen()
        welt.roboter[0].x, welt.roboter[0].y = 5, 5
        welt.roboter[1].x, welt.roboter[1].y = 6, 5
        z = Zustand(welt.sicht(0))
        self.assertEqual(z.fahre_zu_gegner(), "rechts")
        self.assertEqual(z.abstand_zu_gegner(), 1)
        # Das Feld hinter dem Gegner wird umfahren, nicht durchfahren: 4 statt 2 Schritte.
        self.assertEqual(z.abstand_zu_feld(7, 5), 4)

    def test_unerreichbares_ziel_liefert_warte(self):
        welt = zustand_bauen()
        welt.roboter[0].x, welt.roboter[0].y = 5, 5
        z = Zustand(welt.sicht(0))
        self.assertEqual(z.fahre_zu_muell(), "warte")
        self.assertEqual(z.abstand_zu_muell(), UNERREICHBAR)
        self.assertEqual(z.unerriechbar, UNERREICHBAR)

    def test_naechster_muell_wird_gewaehlt(self):
        welt = zustand_bauen()
        welt.roboter[0].x, welt.roboter[0].y = 5, 5
        welt.roboter[1].x, welt.roboter[1].y = 20, 20
        welt.muell[(5, 9)] = Muell(5, 9, "papier", 10, 0)
        welt.muell[(5, 7)] = Muell(5, 7, "elektro", 80, 0)
        z = Zustand(welt.sicht(0))
        self.assertEqual(z.abstand_zu_muell(), 2)
        self.assertEqual(z.abstand_zu_muell(sorte="papier"), 4)
        self.assertEqual(z.fahre_zu_muell(sorte="papier"), "unten")

    def test_radioaktiv_wird_normal_ausgelassen(self):
        welt = zustand_bauen()
        welt.roboter[0].x, welt.roboter[0].y = 5, 5
        welt.roboter[1].x, welt.roboter[1].y = 20, 20
        welt.muell[(5, 6)] = Muell(5, 6, "radioaktiv", -120, 0, radioaktiv=True)
        welt.muell[(5, 9)] = Muell(5, 9, "papier", 10, 0)
        z = Zustand(welt.sicht(0))
        self.assertEqual(z.abstand_zu_muell(), 4)
        self.assertEqual(z.abstand_zu_muell(sorte="radioaktiv"), 1)

    def test_weg_von_gegner_vergroessert_den_abstand(self):
        welt = zustand_bauen()
        welt.roboter[0].x, welt.roboter[0].y = 5, 5
        welt.roboter[1].x, welt.roboter[1].y = 7, 5
        z = Zustand(welt.sicht(0))
        self.assertEqual(z.weg_von_gegner(), "links")
        welt.roboter[1].x, welt.roboter[1].y = 5, 3
        z = Zustand(welt.sicht(0))
        self.assertEqual(z.weg_von_gegner(), "unten")

    def test_blockiert_weicht_aus_und_bleibt_deterministisch(self):
        welt = zustand_bauen()
        welt.roboter[0].x, welt.roboter[0].y = 5, 5
        welt.roboter[1].x, welt.roboter[1].y = 8, 8
        z = Zustand(welt.sicht(0))
        self.assertFalse(z.blockiert)
        geradeaus = z.fahre_zu_feld(8, 5)
        self.assertEqual(geradeaus, "rechts")

        welt.roboter[0].blockiert = True
        a = Zustand(welt.sicht(0))
        b = Zustand(welt.sicht(0))
        self.assertTrue(a.blockiert)
        ausweich = a.fahre_zu_feld(8, 5)
        self.assertNotEqual(ausweich, geradeaus)
        dx, dy = {"oben": (0, -1), "unten": (0, 1),
                  "links": (-1, 0), "rechts": (1, 0)}[ausweich]
        self.assertTrue(a.begehbar(5 + dx, 5 + dy))
        self.assertEqual(ausweich, b.fahre_zu_feld(8, 5),
                         "gleicher Zustand muss dieselbe Ausweichrichtung ergeben")

        welt.roboter[0].blockiert = False
        self.assertEqual(Zustand(welt.sicht(0)).fahre_zu_feld(8, 5), geradeaus)

    def test_ausweichen_ohne_freie_nebenrichtung_wartet(self):
        welt = zustand_bauen()
        welt.roboter[0].x, welt.roboter[0].y = 5, 5
        welt.roboter[1].x, welt.roboter[1].y = 6, 5
        welt.hindernisse = {(5, 4), (5, 6), (4, 5)}
        welt.roboter[0].blockiert = True
        z = Zustand(welt.sicht(0))
        self.assertEqual(z.fahre_zu_feld(6, 5), "warte")

    def test_fahre_zu_gegner_weicht_nicht_aus(self):
        welt = zustand_bauen()
        welt.roboter[0].x, welt.roboter[0].y = 5, 5
        welt.roboter[1].x, welt.roboter[1].y = 6, 5
        welt.roboter[0].blockiert = True
        z = Zustand(welt.sicht(0))
        self.assertEqual(z.fahre_zu_gegner(), "rechts",
                         "das gewollte Rammen behält seine Paritäts-Pause")

    def test_zone_ziel(self):
        welt = zustand_bauen()
        welt.zone = (10, 10)
        welt.roboter[0].x, welt.roboter[0].y = 5, 12
        welt.roboter[1].x, welt.roboter[1].y = 1, 1
        z = Zustand(welt.sicht(0))
        self.assertEqual(z.fahre_zu_zone(), "rechts")
        self.assertEqual(z.abstand_zu_zone(), 5)
        welt.roboter[0].x = 11
        z = Zustand(welt.sicht(0))
        self.assertTrue(z.bin_in_zone)
        self.assertEqual(z.abstand_zu_zone(), 0)
        self.assertEqual(z.fahre_zu_zone(), "warte")


class TestRichtungUndObjekt(unittest.TestCase):
    def welt(self):
        welt = zustand_bauen()
        welt.roboter[0].x, welt.roboter[0].y = 5, 5
        welt.roboter[1].x, welt.roboter[1].y = 20, 20
        return welt

    def test_richtung_ist_der_naechste_schritt_von_fahre_zu(self):
        welt = self.welt()
        z = Zustand(welt.sicht(0))
        self.assertEqual(z.richtung_zu_feld(8, 5), z.fahre_zu_feld(8, 5))
        self.assertEqual(z.richtung_zu_feld(8, 5), "rechts")
        self.assertEqual(z.richtung_zu_depot(), z.fahre_zu_depot())

    def test_hier_und_keine(self):
        welt = self.welt()
        z = Zustand(welt.sicht(0))
        self.assertEqual(z.richtung_zu_feld(5, 5), "hier")
        self.assertEqual(z.richtung_zu_muell(), "keine")      # kein Müll auf dem Feld
        self.assertEqual(z.richtung_zu_gegner(), "keine")     # außer Sicht
        self.assertEqual(z.richtung_weg_von_gegner(), "keine")

    def test_richtung_zum_gegner_verbraucht_keinen_zufall(self):
        welt = self.welt()
        welt.roboter[1].x, welt.roboter[1].y = 8, 5
        z = Zustand(welt.sicht(0))
        self.assertEqual(z.richtung_zu_gegner(), "rechts")
        self.assertIsNone(z._zufall)

    def test_objekt_in_richtung(self):
        welt = self.welt()
        welt.roboter[1].x, welt.roboter[1].y = 5, 6
        welt.muell[(6, 5)] = Muell(6, 5, "radioaktiv", -240, 0)
        welt.muell[(4, 5)] = Muell(4, 5, "metall", 80, 0)
        z = Zustand(welt.sicht(0))
        self.assertEqual(z.objekt_in_richtung("rechts"), "radioaktiv")
        self.assertEqual(z.objekt_in_richtung("links"), "metall")
        self.assertEqual(z.objekt_in_richtung("unten"), "gegner")
        self.assertEqual(z.objekt_in_richtung("oben"), "frei")
        self.assertEqual(z.objekt_in_richtung("hier"), "frei")

    def test_wand_und_depot(self):
        welt = self.welt()
        welt.roboter[0].x, welt.roboter[0].y = 1, 5
        z = Zustand(welt.sicht(0))
        self.assertEqual(z.objekt_in_richtung("links"), "wand")
        dx, dy = welt.roboter[0].depot
        welt.roboter[0].x, welt.roboter[0].y = dx + 1, dy
        z = Zustand(welt.sicht(0))
        self.assertEqual(z.objekt_in_richtung("links"), "depot")


class TestAbfragen(unittest.TestCase):
    def test_ladungsabfragen(self):
        welt = zustand_bauen()
        welt.roboter[0].ladung = [{"sorte": "metall", "wert": 40}]
        z = Zustand(welt.sicht(0))
        self.assertEqual(z.ladung, 1)
        self.assertFalse(z.ladung_ist_voll)
        self.assertFalse(z.ladung_ist_leer)
        self.assertTrue(z.habe("metall"))
        self.assertTrue(z.habe("Metallschrott"))
        self.assertFalse(z.habe("elektro"))
        welt.roboter[0].ladung = [{"sorte": "papier", "wert": 1}] * welt.kapazitaet
        z = Zustand(welt.sicht(0))
        self.assertTrue(z.ladung_ist_voll)

    def test_muell_in_zone_zaehlt_nur_was_noch_etwas_wert_ist(self):
        """Sonst trifft `IF muell_in_zone THEN fahre_zu naechster_muell(in_zone)` zu,
        ohne dass die Fahrt ein Ziel findet — der Roboter wartet bis Rundenende."""
        welt = zustand_bauen()
        zx, zy = welt.zone
        alt = welt.tick - 2 * welt.config.muell.verfall_ticks
        welt.muell[(zx, zy)] = Muell(zx, zy, "papier", 20, alt)
        z = Zustand(welt.sicht(0))
        self.assertFalse(z.muell_in_zone)
        self.assertEqual(z.fahre_zu_muell(nur_in_zone=True), "warte")
        welt.muell[(zx, zy)] = Muell(zx, zy, "papier", 20, welt.tick)
        self.assertTrue(Zustand(welt.sicht(0)).muell_in_zone)

    def test_sortennamen_werden_vereinheitlicht(self):
        self.assertEqual(sorte_normal("Papiermüll"), "papier")
        self.assertEqual(sorte_normal("  ELEKTROSCHROTT "), "elektro")
        self.assertEqual(sorte_normal("Fass"), "radioaktiv")
        self.assertIsNone(sorte_normal(None))

    def test_zufall_ist_reproduzierbar(self):
        welt = zustand_bauen()
        a = Zustand(welt.sicht(0))
        b = Zustand(welt.sicht(0))
        self.assertEqual([a.zufall_zahl(100) for _ in range(10)],
                         [b.zufall_zahl(100) for _ in range(10)])


if __name__ == "__main__":
    unittest.main()
