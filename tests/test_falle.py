"""Die Fass-Falle — SPEC §8.

Diese Bluff-Strategie ist der interessanteste Teil des Spiels. Wenn hier etwas
rot wird, ist eine Regeländerung schiefgegangen, egal wie gut sie sonst aussah.
"""

import unittest

from engine.world import SORTE_RADIOAKTIV
from tests.hilfen import config, lade, setze, spiel_bauen


def einmal_rammen(seed, opfer_ladung, angreifer_ladung=()):
    spiel = spiel_bauen([["rechts"], ["warte"]], seed=seed, ticks=5)
    setze(spiel, 0, 5, 5)
    setze(spiel, 1, 6, 5)
    lade(spiel, 0, list(angreifer_ladung))
    lade(spiel, 1, list(opfer_ladung))
    spiel.schritt()
    return spiel


class TestFalle(unittest.TestCase):

    def test_wer_ein_fass_traegt_gibt_es_beim_rammen_ab(self):
        spiel = einmal_rammen(1, [(SORTE_RADIOAKTIV, -120)])
        self.assertEqual([t["sorte"] for t in spiel.welt.roboter[0].ladung],
                         [SORTE_RADIOAKTIV])
        self.assertEqual(spiel.welt.roboter[1].ladung, [])

    def test_der_angreifer_kann_sich_nichts_aussuchen(self):
        """Bei einem Fass unter vier Teilen muss das Fass in rund einem Viertel kommen."""
        ladung = [(SORTE_RADIOAKTIV, -120), ("papier", 10), ("papier", 10), ("papier", 10)]
        fass = 0
        laeufe = 200
        for seed in range(laeufe):
            spiel = einmal_rammen(seed + 1, ladung)
            if spiel.welt.roboter[0].ladung[0]["sorte"] == SORTE_RADIOAKTIV:
                fass += 1
        self.assertGreater(fass, laeufe // 8, "das Fass wird viel zu selten gezogen")
        self.assertLess(fass, laeufe // 2, "das Fass wird viel zu oft gezogen")

    def test_elektroschrott_ist_nicht_gezielt_greifbar(self):
        """Kein Seed darf systematisch das teuerste Teil liefern."""
        ladung = [("papier", 10), ("elektro", 80), ("bio", 18), ("metall", 40)]
        gezogen = set()
        for seed in range(40):
            spiel = einmal_rammen(seed + 1, ladung)
            gezogen.add(spiel.welt.roboter[0].ladung[0]["sorte"])
        self.assertGreater(len(gezogen), 1, "das Klauen ist offenbar nicht zufällig")

    def test_der_bluff_rechnet_sich(self):
        """Rammen bei geladenem Fass kostet den Angreifer am Rundenende echte Punkte."""
        cfg = config()
        spiel = spiel_bauen([["rechts"], ["warte"]], seed=3, ticks=1, cfg=cfg)
        setze(spiel, 0, 5, 5)
        setze(spiel, 1, 6, 5)
        lade(spiel, 1, [(SORTE_RADIOAKTIV, cfg.radioaktiv.wert)])
        spiel.schritt()
        self.assertEqual(spiel.welt.roboter[0].punkte, cfg.radioaktiv.wert)
        self.assertEqual(spiel.welt.roboter[1].punkte, 0)

    def test_gegner_verraet_die_sorten_nicht(self):
        """Ohne diese Regel würde niemand je in die Falle fahren."""
        cfg = config()
        spiel = spiel_bauen([["warte"], ["warte"]], cfg=cfg)
        setze(spiel, 0, 5, 5)
        setze(spiel, 1, 6, 5)
        lade(spiel, 1, [(SORTE_RADIOAKTIV, cfg.radioaktiv.wert), ("papier", 10)])
        gegner = spiel.welt.sicht(0)["gegner"]
        self.assertEqual(gegner, [{"x": 6, "y": 5, "ladung": 2}])

    def test_fass_bleibt_in_der_ladung_kein_wegwerfen(self):
        cfg = config()
        spiel = spiel_bauen([["rechts"] * 10, ["warte"]], cfg=cfg, ticks=10)
        setze(spiel, 0, 5, 5)
        setze(spiel, 1, 20, 20)
        lade(spiel, 0, [(SORTE_RADIOAKTIV, cfg.radioaktiv.wert)])
        for _ in range(8):
            spiel.schritt()
        self.assertEqual(len(spiel.welt.roboter[0].ladung), 1)

    def test_aufgenommene_faesser_erscheinen_nicht_nach(self):
        cfg = config()
        spiel = spiel_bauen([["warte"], ["warte"]], cfg=cfg, ticks=120,
                            ohne_muell=False)
        for feld in [p for p, m in spiel.welt.muell.items() if m.radioaktiv]:
            del spiel.welt.muell[feld]
        for _ in range(100):
            spiel.schritt()
        self.assertEqual([m for m in spiel.welt.muell.values() if m.radioaktiv], [])


if __name__ == "__main__":
    unittest.main()
