import unittest

from engine.world import Welt, SORTE_RADIOAKTIV
from tests.hilfen import config


class TestAufbau(unittest.TestCase):
    def test_depots_symmetrisch_duell(self):
        cfg = config()
        w = Welt(cfg, ["A", "B"], seed=1)
        a = cfg.spiel.depot_abstand
        self.assertEqual(w.depot_positionen(),
                         [(a, a), (cfg.spiel.breite - 1 - a, cfg.spiel.hoehe - 1 - a)])

    def test_depots_symmetrisch_vierer(self):
        cfg = config()
        w = Welt(cfg, ["A", "B", "C", "D"], seed=1)
        a = cfg.spiel.depot_abstand
        rand = cfg.spiel.breite - 1 - a
        self.assertEqual(w.depot_positionen(),
                         [(a, a), (rand, a), (rand, rand), (a, rand)])

    def test_depots_haben_luft_zur_wand(self):
        """Sonst könnte ein Roboter ein fremdes Depot unvertreibbar besetzen."""
        cfg = config()
        for spieler in (2, 4):
            w = Welt(cfg, ["A", "B", "C", "D"][:spieler], seed=1)
            for x, y in w.depot_positionen():
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    self.assertFalse(w.ist_wand(x + dx, y + dy),
                                     "Depot %s klebt an der Wand" % ((x, y),))

    def test_muell_liegt_punktsymmetrisch(self):
        w = Welt(config(), ["A", "B"], seed=17)
        for (x, y), stueck in w.muell.items():
            spiegel = (w.breite - 1 - x, w.hoehe - 1 - y)
            self.assertIn(spiegel, w.muell, "Spiegelfeld %s fehlt" % (spiegel,))
            self.assertEqual(w.muell[spiegel].sorte, stueck.sorte)

    def test_muell_liegt_drehsymmetrisch_bei_vier(self):
        w = Welt(config(), ["A", "B", "C", "D"], seed=17)
        for (x, y), stueck in w.muell.items():
            for feld in w.bahn(x, y):
                self.assertIn(feld, w.muell)
                self.assertEqual(w.muell[feld].sorte, stueck.sorte)

    def test_kein_muell_auf_depots_oder_waenden(self):
        for seed in range(1, 15):
            w = Welt(config(), ["A", "B"], seed=seed)
            for (x, y) in w.muell:
                self.assertFalse(w.ist_wand(x, y))
                self.assertFalse(w.ist_depot(x, y))

    def test_nachschub_meidet_felder_mit_robotern(self):
        w = Welt(config(), ["A", "B"], seed=4)
        w.muell.clear()
        feld = (5, 5)
        w.roboter[0].x, w.roboter[0].y = feld
        self.assertFalse(w._feld_frei(*feld))
        w._muell_streuen(8)
        self.assertNotIn(feld, w.muell)

    def test_faesser_anzahl_und_symmetrie(self):
        w = Welt(config(), ["A", "B"], seed=3)
        faesser = sorted(p for p, m in w.muell.items() if m.radioaktiv)
        self.assertEqual(len(faesser), 2)
        x, y = faesser[0]
        self.assertIn((w.breite - 1 - x, w.hoehe - 1 - y), faesser)

    def test_max_auf_feld_wird_nicht_ueberschritten(self):
        """Auch eine volle Symmetriebahn muss vor der Obergrenze Halt machen."""
        grenze = 21
        for spieler in (2, 4):
            for seed in range(1, 6):
                w = Welt(config(**{"muell.max_auf_feld": grenze}),
                         ["A", "B", "C", "D"][:spieler], seed=seed)
                self.assertLessEqual(
                    len(w.muell), grenze,
                    "%d Spieler, Seed %d: %d Stücke > max_auf_feld"
                    % (spieler, seed, len(w.muell)))

    def test_zone_liegt_vollstaendig_im_feld(self):
        for seed in range(1, 40):
            w = Welt(config(), ["A", "B"], seed=seed)
            g = w.config.zone.groesse
            zx, zy = w.zone
            self.assertGreaterEqual(zx, 1)
            self.assertGreaterEqual(zy, 1)
            self.assertLessEqual(zx + g - 1, w.breite - 2)
            self.assertLessEqual(zy + g - 1, w.hoehe - 2)


class TestWerte(unittest.TestCase):
    def test_verfall_linear_bis_null(self):
        cfg = config()
        w = Welt(cfg, ["A", "B"], seed=1)
        w.muell.clear()
        from engine.world import Muell
        stueck = Muell(5, 5, "papier", 10, 0)
        w.muell[(5, 5)] = stueck
        w.tick = 0
        self.assertEqual(w.wert_von(stueck), 10)
        w.tick = cfg.muell.verfall_ticks // 2
        self.assertEqual(w.wert_von(stueck), 5)
        w.tick = cfg.muell.verfall_ticks
        self.assertEqual(w.wert_von(stueck), 0)

    def test_verfall_wird_negativ_und_gedeckelt(self):
        cfg = config()
        w = Welt(cfg, ["A", "B"], seed=1)
        from engine.world import Muell
        stueck = Muell(5, 5, "elektro", cfg.muell.sorten.elektro.wert, 0)
        w.tick = cfg.muell.verfall_ticks * 3
        self.assertEqual(w.wert_von(stueck), -cfg.muell.verfall_strafe_max)

    def test_radioaktiv_altert_nicht(self):
        cfg = config()
        w = Welt(cfg, ["A", "B"], seed=1)
        fass = [m for m in w.muell.values() if m.radioaktiv][0]
        w.tick = 0
        self.assertEqual(w.wert_von(fass), cfg.radioaktiv.wert)
        w.tick = 5000
        self.assertEqual(w.wert_von(fass), cfg.radioaktiv.wert)

    def test_zonenbonus_verdoppelt_beim_aufnehmen(self):
        cfg = config()
        w = Welt(cfg, ["A", "B"], seed=1)
        from engine.world import Muell
        zx, zy = w.zone
        stueck = Muell(zx, zy, "metall", cfg.muell.sorten.metall.wert, 0)
        self.assertEqual(w.aufnahme_wert(stueck),
                         cfg.muell.sorten.metall.wert * cfg.zone.faktor)

    def test_radioaktiv_bekommt_keinen_zonenbonus(self):
        cfg = config()
        w = Welt(cfg, ["A", "B"], seed=1)
        from engine.world import Muell
        zx, zy = w.zone
        fass = Muell(zx, zy, SORTE_RADIOAKTIV, cfg.radioaktiv.wert, 0, radioaktiv=True)
        self.assertEqual(w.aufnahme_wert(fass), cfg.radioaktiv.wert)


class TestSicht(unittest.TestCase):
    def test_gegner_nur_im_radius(self):
        cfg = config()
        w = Welt(cfg, ["A", "B"], seed=1)
        w.roboter[0].x, w.roboter[0].y = 5, 5
        w.roboter[1].x, w.roboter[1].y = 5, 5 + cfg.spiel.sicht_radius
        self.assertEqual(len(w.sicht(0)["gegner"]), 1)
        w.roboter[1].y = 5 + cfg.spiel.sicht_radius + 1
        self.assertEqual(len(w.sicht(0)["gegner"]), 0)

    def test_gegner_zeigt_nur_anzahl_keine_sorten(self):
        cfg = config()
        w = Welt(cfg, ["A", "B"], seed=1)
        w.roboter[0].x, w.roboter[0].y = 5, 5
        w.roboter[1].x, w.roboter[1].y = 6, 5
        w.roboter[1].ladung = [{"sorte": SORTE_RADIOAKTIV, "wert": -120}]
        gegner = w.sicht(0)["gegner"][0]
        self.assertEqual(gegner["ladung"], 1)
        self.assertEqual(sorted(gegner.keys()), ["ladung", "x", "y"])

    def test_eigener_muell_ist_immer_sichtbar(self):
        cfg = config()
        w = Welt(cfg, ["A", "B"], seed=2)
        self.assertEqual(len(w.sicht(0)["muell"]), len(w.muell))


if __name__ == "__main__":
    unittest.main()
