"""Bewegungsauflösung, SPEC §7. Jeder dort beschriebene Fall bekommt hier einen Test."""

import os
import unittest

from engine import config as config_modul
from engine.game import Spiel
from engine.runner import Anschlussgruppe
from engine.world import Muell
from tests.hilfen import auf_depot, config, lade, positionen, setze, spiel_bauen

BOT_ORDNER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bots")


def rammereignisse(tick):
    return [e for e in tick["ereignisse"] if e["art"] == "rammen"]


class TestAusweichen(unittest.TestCase):
    """Regression: Zwei Bots auf demselben Zwischenfeld hingen früher dauerhaft fest.

    Gemessen wird je Roboter die längste Serie aufeinanderfolgender Ticks, in denen
    er fahren wollte und doch stehen blieb. Gewolltes Warten zählt nicht: Seit der
    Akku-Regel (Ladung weg bei 0) wartet der Hausmeister in Seed 7 bewusst 36 Ticks
    in der Bonuszone auf Nachschub — das ist Strategie, kein Standstreit.
    Die 328 (Hausmeister/Lauerer), 136
    (Fassbluffer/Hausmeister) und 102 (Fleißig/Lauerer) Ticks stammen aus der
    Bot-Fassung vor dem Tuning und ohne Ausweichregel; mit den heutigen Bots und
    Ausweichen misst derselbe Test 12/10/12 Ticks.
    """

    def maximale_stillstandsserie(self, bot_a, bot_b, seed, ticks=400):
        cfg = config_modul.lade()
        pfade = [os.path.join(BOT_ORDNER, bot_a + ".py"),
                 os.path.join(BOT_ORDNER, bot_b + ".py")]
        with Anschlussgruppe(pfade, cfg) as anschluesse:
            spiel = Spiel(cfg, anschluesse, seed=seed, runden_laenge=ticks)
            spiel.spiele()
            for anschluss in anschluesse:
                self.assertEqual(anschluss.fehler, [],
                                 "%s lief nicht sauber: %s" % (anschluss.name,
                                                               anschluss.fehler[:1]))
        serien = [0] * len(spiel.welt.roboter)
        letzte = [None] * len(serien)
        lauf = [0] * len(serien)
        for tick in spiel.ticks:
            for i, r in enumerate(tick["roboter"]):
                pos = (r["x"], r["y"])
                will_fahren = tick["gewuenscht"][i] in ("oben", "unten", "links", "rechts")
                if pos == letzte[i] and will_fahren:
                    lauf[i] += 1
                else:
                    serien[i] = max(serien[i], lauf[i])
                    lauf[i] = 1
                    letzte[i] = pos
        return max(max(serien[i], lauf[i]) for i in range(len(serien)))

    def test_kein_dauerhafter_stillstand_durch_standstreit(self):
        faelle = [
            ("hausmeister", "lauerer", 7, 328),
            ("fassbluffer", "hausmeister", 103, 136),
            ("fleissig", "lauerer", 9, 102),
        ]
        for bot_a, bot_b, seed, vorher in faelle:
            with self.subTest(partie="%s-%s" % (bot_a, bot_b), seed=seed):
                serie = self.maximale_stillstandsserie(bot_a, bot_b, seed)
                self.assertLessEqual(
                    serie, 20,
                    "%s gegen %s, Seed %d: %d Ticks Stillstand (alte Bot-Fassung "
                    "ohne Ausweichregel: %d)" % (bot_a, bot_b, seed, serie, vorher))


class TestBewegung(unittest.TestCase):

    def test_wand_bremst_ohne_energieverlust(self):
        spiel = spiel_bauen([["links"], ["warte"]])
        setze(spiel, 0, 1, 5)
        akku_vorher = spiel.welt.roboter[0].akku
        spiel.schritt()
        self.assertEqual(positionen(spiel)[0], (1, 5))
        self.assertEqual(spiel.welt.roboter[0].akku, akku_vorher)

    def test_bewegung_kostet_energie(self):
        spiel = spiel_bauen([["rechts"], ["warte"]])
        setze(spiel, 0, 5, 5)
        setze(spiel, 1, 15, 15)
        akku_vorher = spiel.welt.roboter[0].akku
        spiel.schritt()
        self.assertEqual(positionen(spiel)[0], (6, 5))
        self.assertEqual(spiel.welt.roboter[0].akku,
                         akku_vorher - spiel.config.akku.kosten_bewegung)

    def test_gleiches_freies_feld_beide_bleiben_stehen(self):
        spiel = spiel_bauen([["rechts"], ["links"]])
        setze(spiel, 0, 5, 5)
        setze(spiel, 1, 7, 5)
        tick = spiel.schritt()
        self.assertEqual(positionen(spiel), [(5, 5), (7, 5)])
        self.assertEqual(rammereignisse(tick), [])

    def test_nachruecken_ohne_rammen(self):
        spiel = spiel_bauen([["rechts"], ["rechts"]])
        setze(spiel, 0, 5, 5)
        setze(spiel, 1, 6, 5)
        tick = spiel.schritt()
        self.assertEqual(positionen(spiel), [(6, 5), (7, 5)])
        self.assertEqual(rammereignisse(tick), [])

    def test_platztausch_gilt_als_rammen_fuer_beide(self):
        spiel = spiel_bauen([["rechts"], ["links"]])
        setze(spiel, 0, 5, 5)
        setze(spiel, 1, 6, 5)
        akku = [r.akku for r in spiel.welt.roboter]
        tick = spiel.schritt()
        self.assertEqual(positionen(spiel), [(5, 5), (6, 5)])
        ereignisse = rammereignisse(tick)
        self.assertEqual(len(ereignisse), 2)
        self.assertTrue(all(e["tausch"] and not e["geschoben"] for e in ereignisse))
        kosten = spiel.config.akku.kosten_rammen
        self.assertEqual([r.akku for r in spiel.welt.roboter],
                         [akku[0] - kosten, akku[1] - kosten])

    def test_rammen_schiebt_und_kostet_beide_energie(self):
        spiel = spiel_bauen([["rechts"], ["warte"]])
        setze(spiel, 0, 5, 5)
        setze(spiel, 1, 6, 5)
        akku = [r.akku for r in spiel.welt.roboter]
        tick = spiel.schritt()
        self.assertEqual(positionen(spiel), [(6, 5), (7, 5)])
        ereignis = rammereignisse(tick)[0]
        self.assertTrue(ereignis["geschoben"])
        cfg = spiel.config.akku
        self.assertEqual(spiel.welt.roboter[0].akku,
                         akku[0] - cfg.kosten_rammen - cfg.kosten_bewegung)
        self.assertEqual(spiel.welt.roboter[1].akku, akku[1] - cfg.kosten_rammen)

    def test_geschobener_roboter_zahlt_keine_bewegungsenergie(self):
        spiel = spiel_bauen([["rechts"], ["warte"]])
        setze(spiel, 0, 5, 5)
        setze(spiel, 1, 6, 5)
        akku_opfer = spiel.welt.roboter[1].akku
        spiel.schritt()
        self.assertEqual(spiel.welt.roboter[1].akku,
                         akku_opfer - spiel.config.akku.kosten_rammen)

    def test_rammen_an_der_wand_schiebt_nicht_klaut_aber(self):
        spiel = spiel_bauen([["rechts"], ["warte"]])
        setze(spiel, 0, 21, 5)
        setze(spiel, 1, 22, 5)
        lade(spiel, 1, [("papier", 10)])
        tick = spiel.schritt()
        self.assertEqual(positionen(spiel), [(21, 5), (22, 5)])
        ereignis = rammereignisse(tick)[0]
        self.assertFalse(ereignis["geschoben"])
        self.assertEqual(ereignis["geklaut"], "papier")
        self.assertEqual(len(spiel.welt.roboter[0].ladung), 1)
        self.assertEqual(len(spiel.welt.roboter[1].ladung), 0)

    def test_kein_kettenschub(self):
        spiel = spiel_bauen([["rechts"], ["warte"], ["warte"], ["warte"]])
        setze(spiel, 0, 5, 5)
        setze(spiel, 1, 6, 5)
        setze(spiel, 2, 7, 5)
        setze(spiel, 3, 15, 15)
        tick = spiel.schritt()
        self.assertEqual(positionen(spiel)[:3], [(5, 5), (6, 5), (7, 5)])
        self.assertFalse(rammereignisse(tick)[0]["geschoben"])

    def test_ring_loest_sich_nicht_auf(self):
        spiel = spiel_bauen([["rechts"], ["unten"], ["links"], ["oben"]])
        setze(spiel, 0, 5, 5)
        setze(spiel, 1, 6, 5)
        setze(spiel, 2, 6, 6)
        setze(spiel, 3, 5, 6)
        tick = spiel.schritt()
        self.assertEqual(positionen(spiel), [(5, 5), (6, 5), (6, 6), (5, 6)])
        self.assertEqual(rammereignisse(tick), [])

    def test_zwei_angreifer_auf_dasselbe_opfer_blockieren_sich(self):
        spiel = spiel_bauen([["rechts"], ["warte"], ["links"], ["warte"]])
        setze(spiel, 0, 5, 5)
        setze(spiel, 1, 6, 5)
        setze(spiel, 2, 7, 5)
        setze(spiel, 3, 15, 15)
        tick = spiel.schritt()
        self.assertEqual(positionen(spiel)[:3], [(5, 5), (6, 5), (7, 5)])
        self.assertEqual(rammereignisse(tick), [])

    def test_geschobener_roboter_nimmt_muell_auf(self):
        spiel = spiel_bauen([["rechts"], ["warte"]])
        setze(spiel, 0, 5, 5)
        setze(spiel, 1, 6, 5)
        spiel.welt.muell[(7, 5)] = Muell(7, 5, "metall", 40, 0)
        spiel.schritt()
        self.assertEqual(positionen(spiel)[1], (7, 5))
        self.assertEqual([t["sorte"] for t in spiel.welt.roboter[1].ladung], ["metall"])

    def test_voller_angreifer_schiebt_nur(self):
        spiel = spiel_bauen([["rechts"], ["warte"]])
        setze(spiel, 0, 5, 5)
        setze(spiel, 1, 6, 5)
        lade(spiel, 0, [("papier", 10)] * spiel.welt.kapazitaet)
        lade(spiel, 1, [("elektro", 80)])
        tick = spiel.schritt()
        self.assertIsNone(rammereignisse(tick)[0]["geklaut"])
        self.assertEqual(len(spiel.welt.roboter[1].ladung), 1)

    def test_besetztes_fremdes_depot_laesst_sich_raeumen(self):
        """Sonst wäre Depotbesetzen eine unschlagbare Spielverderber-Strategie."""
        spiel = spiel_bauen([["warte"], ["warte"]])
        depot = spiel.welt.roboter[1].depot
        setze(spiel, 0, depot[0], depot[1])          # Besetzer auf fremdem Depot
        for dx, dy, richtung in ((-1, 0, "rechts"), (1, 0, "links"),
                                 (0, -1, "unten"), (0, 1, "oben")):
            frisch = spiel_bauen([["warte"], [richtung]])
            setze(frisch, 0, depot[0], depot[1])
            setze(frisch, 1, depot[0] + dx, depot[1] + dy)
            frisch.schritt()
            self.assertEqual(positionen(frisch)[1], depot,
                             "aus Richtung %s ließ sich der Besetzer nicht verdrängen"
                             % richtung)

    def test_unsinnige_aktion_gilt_als_warte(self):
        spiel = spiel_bauen([["diagonal"], ["warte"]])
        setze(spiel, 0, 5, 5)
        spiel.schritt()
        self.assertEqual(positionen(spiel)[0], (5, 5))


if __name__ == "__main__":
    unittest.main()
