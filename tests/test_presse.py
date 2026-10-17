"""Die Presse: drei gleiche Teile, zwei Züge, ein Ballen — und der Abbruch beim Klauen."""

import unittest

from engine.world import SORTE_RADIOAKTIV
from engine.zustand import Zustand
from tests.hilfen import lade, setze, spiel_bauen


def presse_spiel(aktionen, ticks=6):
    return spiel_bauen(aktionen, ticks=ticks)


class TestPresse(unittest.TestCase):
    def test_ohne_drei_gleiche_passiert_nichts(self):
        spiel = presse_spiel([["presse", "warte"], ["warte", "warte"]])
        setze(spiel, 0, 5, 5)
        setze(spiel, 1, 20, 20)
        lade(spiel, 0, [("papier", 20), ("papier", 20), ("metall", 80)])
        spiel.schritt()
        self.assertEqual(spiel.welt.roboter[0].presse_ticks, 0)
        self.assertEqual(len(spiel.welt.roboter[0].ladung), 3)

    def test_presse_dauert_zwei_ticks(self):
        spiel = presse_spiel([["presse", "warte", "warte"], ["warte"] * 3])
        setze(spiel, 0, 5, 5)
        setze(spiel, 1, 20, 20)
        lade(spiel, 0, [("papier", 20)] * 3)
        spiel.schritt()
        self.assertEqual(spiel.welt.roboter[0].presse_ticks, 1)
        self.assertEqual(len(spiel.welt.roboter[0].ladung), 3)   # noch nichts passiert
        spiel.schritt()
        ladung = spiel.welt.roboter[0].ladung
        self.assertEqual(len(ladung), 1)
        self.assertEqual(ladung[0]["sorte"], "ballen")
        self.assertEqual(ladung[0]["wert"], 48)                  # 60 minus 20 %
        self.assertTrue(ladung[0]["gepresst"])

    def test_pressen_bewegt_den_roboter_nicht(self):
        spiel = presse_spiel([["presse", "rechts"], ["warte", "warte"]])
        setze(spiel, 0, 5, 5)
        setze(spiel, 1, 20, 20)
        lade(spiel, 0, [("metall", 80)] * 3)
        spiel.schritt()
        self.assertEqual((spiel.welt.roboter[0].x, spiel.welt.roboter[0].y), (5, 5))

    def test_die_billigsten_teile_werden_gepresst(self):
        spiel = presse_spiel([["presse", "warte", "warte"], ["warte"] * 3])
        setze(spiel, 0, 5, 5)
        setze(spiel, 1, 20, 20)
        lade(spiel, 0, [("papier", 5), ("papier", 10), ("papier", 20), ("papier", 30)])
        spiel.schritt()
        spiel.schritt()
        werte = sorted((t["sorte"], t["wert"]) for t in spiel.welt.roboter[0].ladung)
        self.assertEqual(werte, [("ballen", 28), ("papier", 30)])

    def test_abgewertete_teile_lassen_sich_nicht_pressen(self):
        spiel = presse_spiel([["presse", "warte", "warte"], ["warte"] * 3])
        setze(spiel, 0, 5, 5)
        setze(spiel, 1, 20, 20)
        lade(spiel, 0, [("papier", 0), ("papier", -10), ("papier", -20)])
        self.assertFalse(Zustand(spiel.welt.sicht(0)).kann_pressen)
        spiel.schritt()
        self.assertEqual(spiel.welt.roboter[0].presse_ticks, 0)
        spiel.schritt()
        self.assertEqual(spiel.welt.roboter[0].presse_ticks, 0)
        werte = [(t["sorte"], t["wert"]) for t in spiel.welt.roboter[0].ladung]
        self.assertEqual(werte, [("papier", 0), ("papier", -10), ("papier", -20)])

    def test_negative_teile_bleiben_bei_der_presse_liegen(self):
        spiel = presse_spiel([["presse", "warte", "warte"], ["warte"] * 3])
        setze(spiel, 0, 5, 5)
        setze(spiel, 1, 20, 20)
        lade(spiel, 0, [("papier", 10), ("papier", -5), ("papier", 20),
                        ("papier", -15), ("papier", 30)])
        self.assertTrue(Zustand(spiel.welt.sicht(0)).kann_pressen)
        spiel.schritt()
        spiel.schritt()
        werte = sorted((t["sorte"], t["wert"]) for t in spiel.welt.roboter[0].ladung)
        self.assertEqual(werte, [("ballen", 48), ("papier", -15), ("papier", -5)])

    def test_abgewertetes_teil_bricht_die_presse_ab(self):
        spiel = presse_spiel([["presse", "warte", "warte"], ["warte"] * 3])
        setze(spiel, 0, 5, 5)
        setze(spiel, 1, 20, 20)
        lade(spiel, 0, [("papier", 20)] * 3)
        spiel.schritt()
        self.assertEqual(spiel.welt.roboter[0].presse_ticks, 1)
        spiel.welt.roboter[0].ladung[0]["wert"] = 0
        spiel._presse_pruefen(spiel.welt.roboter[0])
        self.assertEqual(spiel.welt.roboter[0].presse_ticks, 0)
        self.assertIsNone(spiel.welt.roboter[0].presse_sorte)
        spiel.schritt()
        werte = [(t["sorte"], t["wert"]) for t in spiel.welt.roboter[0].ladung]
        self.assertEqual(werte, [("papier", 0), ("papier", 20), ("papier", 20)])

    def test_abschluss_ohne_drei_positive_teile_laesst_keinen_ballen_entstehen(self):
        spiel = presse_spiel([["presse", "warte", "warte"], ["warte"] * 3])
        setze(spiel, 0, 5, 5)
        setze(spiel, 1, 20, 20)
        lade(spiel, 0, [("papier", 20)] * 3)
        spiel.schritt()
        spiel.welt.roboter[0].ladung[0]["wert"] = 0
        spiel.schritt()
        self.assertEqual(spiel.welt.roboter[0].presse_ticks, 0)
        werte = [(t["sorte"], t["wert"]) for t in spiel.welt.roboter[0].ladung]
        self.assertEqual(werte, [("papier", 0), ("papier", 20), ("papier", 20)])

    def test_ballen_wird_nicht_erneut_gepresst(self):
        spiel = presse_spiel([["presse", "warte", "presse", "warte"], ["warte"] * 4])
        setze(spiel, 0, 5, 5)
        setze(spiel, 1, 20, 20)
        lade(spiel, 0, [("papier", 20)] * 3)
        spiel.schritt()
        spiel.schritt()
        self.assertEqual(len(spiel.welt.roboter[0].ladung), 1)
        spiel.schritt()
        self.assertEqual(spiel.welt.roboter[0].presse_ticks, 0)
        self.assertEqual(spiel.welt.roboter[0].ladung[0]["sorte"], "ballen")

    def test_diebstahl_bricht_die_presse_ab(self):
        spiel = presse_spiel([["presse", "warte", "warte"], ["unten", "warte", "warte"]])
        opfer = setze(spiel, 0, 5, 5)
        setze(spiel, 1, 5, 4)
        lade(spiel, 0, [("papier", 20)] * 3)
        spiel.schritt()                       # Presse beginnt, der Gegner rammt im selben Tick
        self.assertEqual(opfer.presse_ticks, 0)
        self.assertEqual(len(opfer.ladung), 2)   # eins geklaut, kein Ballen
        self.assertTrue(all(t["sorte"] == "papier" for t in opfer.ladung))

    def test_schubsen_bricht_die_presse_nicht_ab(self):
        """SPEC §5a: Nur Diebstahl bricht ab — ein voller Angreifer kann nichts klauen."""
        spiel = presse_spiel([["presse", "warte", "warte"], ["rechts", "warte", "warte"]])
        opfer = setze(spiel, 0, 5, 5)
        setze(spiel, 1, 4, 5)
        lade(spiel, 0, [("papier", 20)] * 3)
        lade(spiel, 1, [("papier", 10)] * spiel.welt.kapazitaet)
        spiel.schritt()
        self.assertEqual((opfer.x, opfer.y), (6, 5), "geschubst werden gehört dazu")
        self.assertEqual(opfer.presse_ticks, 1)
        self.assertEqual(len(opfer.ladung), 3)   # nichts geklaut
        spiel.schritt()
        self.assertEqual(opfer.presse_ticks, 0)
        self.assertEqual([t["sorte"] for t in opfer.ladung], ["ballen"])

    def test_kann_pressen_flagge(self):
        spiel = presse_spiel([["warte"], ["warte"]])
        setze(spiel, 0, 5, 5)
        setze(spiel, 1, 20, 20)
        lade(spiel, 0, [("papier", 20), ("papier", 20), ("metall", 80)])
        self.assertFalse(Zustand(spiel.welt.sicht(0)).kann_pressen)
        lade(spiel, 0, [("papier", 20), ("papier", 20), ("papier", 20)])
        self.assertTrue(Zustand(spiel.welt.sicht(0)).kann_pressen)
        lade(spiel, 0, [{"sorte": "ballen", "wert": 48, "gepresst": True}] * 3)
        self.assertFalse(Zustand(spiel.welt.sicht(0)).kann_pressen)

    def test_radioaktiver_abfall_laesst_sich_nicht_pressen(self):
        spiel = presse_spiel([["presse", "presse", "warte"], ["warte"] * 3])
        setze(spiel, 0, 5, 5)
        setze(spiel, 1, 20, 20)
        lade(spiel, 0, [(SORTE_RADIOAKTIV, -240)] * 3)
        self.assertFalse(Zustand(spiel.welt.sicht(0)).kann_pressen)
        spiel.schritt()
        self.assertEqual(spiel.welt.roboter[0].presse_ticks, 0)
        spiel.schritt()
        self.assertEqual(spiel.welt.roboter[0].presse_ticks, 0)
        self.assertEqual([t["sorte"] for t in spiel.welt.roboter[0].ladung],
                         [SORTE_RADIOAKTIV] * 3)

    def test_presse_ignoriert_das_fass_neben_drei_gleichen(self):
        spiel = presse_spiel([["presse", "warte", "warte"], ["warte"] * 3])
        setze(spiel, 0, 5, 5)
        setze(spiel, 1, 20, 20)
        lade(spiel, 0, [("papier", 20)] * 3 + [(SORTE_RADIOAKTIV, -240)])
        self.assertTrue(Zustand(spiel.welt.sicht(0)).kann_pressen)
        spiel.schritt()
        spiel.schritt()
        sorten = sorted(t["sorte"] for t in spiel.welt.roboter[0].ladung)
        self.assertEqual(sorten, ["ballen", SORTE_RADIOAKTIV])

    def test_ballen_wird_beim_rammen_mitgeklaut(self):
        spiel = presse_spiel([["warte"], ["rechts"]])
        setze(spiel, 0, 6, 5)
        setze(spiel, 1, 5, 5)
        lade(spiel, 0, [{"sorte": "ballen", "wert": 48, "gepresst": True}])
        spiel.schritt()
        self.assertEqual(spiel.welt.roboter[1].ladung[0]["sorte"], "ballen")


if __name__ == "__main__":
    unittest.main()
