"""Aufnahme, Depot, Akku, Rundenende — SPEC §3, §5, §6, §10."""

import unittest

from engine.game import Spiel
from engine.world import Muell, SORTE_RADIOAKTIV
from tests.hilfen import (SkriptBot, auf_depot, config, depot, lade, setze,
                          spiel_bauen)


class TestAufnahme(unittest.TestCase):
    def test_zwangsaufnahme_beim_hineinfahren(self):
        spiel = spiel_bauen([["rechts"], ["warte"]])
        setze(spiel, 0, 5, 5)
        setze(spiel, 1, 15, 15)
        spiel.welt.muell[(6, 5)] = Muell(6, 5, "bio", 18, 0)
        spiel.schritt()
        self.assertEqual([t["sorte"] for t in spiel.welt.roboter[0].ladung], ["bio"])
        self.assertNotIn((6, 5), spiel.welt.muell)

    def test_stehenbleiben_nimmt_nichts_auf(self):
        spiel = spiel_bauen([["warte"], ["warte"]])
        setze(spiel, 0, 5, 5)
        spiel.welt.muell[(5, 5)] = Muell(5, 5, "bio", 18, 0)
        spiel.schritt()
        self.assertEqual(spiel.welt.roboter[0].ladung, [])
        self.assertIn((5, 5), spiel.welt.muell)

    def test_volle_ladung_faehrt_darueber(self):
        spiel = spiel_bauen([["rechts"], ["warte"]])
        setze(spiel, 0, 5, 5)
        setze(spiel, 1, 15, 15)
        lade(spiel, 0, [("papier", 10)] * spiel.welt.kapazitaet)
        spiel.welt.muell[(6, 5)] = Muell(6, 5, "elektro", 80, 0)
        spiel.schritt()
        self.assertEqual((spiel.welt.roboter[0].x, spiel.welt.roboter[0].y), (6, 5))
        self.assertIn((6, 5), spiel.welt.muell)

    def test_wert_wird_beim_aufnehmen_eingefroren(self):
        cfg = config()
        spiel = spiel_bauen([["rechts"], ["warte"]], cfg=cfg, ticks=200)
        setze(spiel, 0, 5, 5)
        setze(spiel, 1, 15, 15)
        spiel.welt.muell[(6, 5)] = Muell(6, 5, "metall", cfg.muell.sorten.metall.wert, 0)
        spiel.schritt()
        wert = spiel.welt.roboter[0].ladung[0]["wert"]
        for _ in range(150):
            spiel.schritt()
        self.assertEqual(spiel.welt.roboter[0].ladung[0]["wert"], wert)

    def test_zonenbonus_bleibt_wenn_die_zone_weiterwandert(self):
        cfg = config()
        spiel = spiel_bauen([["rechts"], ["warte"]], cfg=cfg, ticks=200)
        zx, zy = spiel.welt.zone
        setze(spiel, 0, zx, zy + 1)
        setze(spiel, 1, 20, 20)
        spiel.welt.muell[(zx + 1, zy + 1)] = Muell(zx + 1, zy + 1, "metall",
                                                   cfg.muell.sorten.metall.wert, 0)
        spiel.schritt()
        self.assertEqual(spiel.welt.roboter[0].ladung[0]["wert"],
                         cfg.muell.sorten.metall.wert * cfg.zone.faktor)
        spiel.welt.zone = (1, 1)
        self.assertEqual(spiel.welt.roboter[0].ladung[0]["wert"],
                         cfg.muell.sorten.metall.wert * cfg.zone.faktor)


class TestDepot(unittest.TestCase):
    def test_abliefern_zaehlt_punkte_und_leert(self):
        spiel = spiel_bauen([["warte"], ["warte"]])
        auf_depot(spiel, 0)
        lade(spiel, 0, [("papier", 10), ("metall", 40)])
        spiel.schritt()
        r = spiel.welt.roboter[0]
        self.assertEqual(r.punkte, 50)
        self.assertEqual(r.ladung, [])

    def test_ablieferung_nennt_die_teile(self):
        spiel = spiel_bauen([["warte"], ["warte"]])
        auf_depot(spiel, 0)
        lade(spiel, 0, [("papier", 10), (SORTE_RADIOAKTIV, -120)])
        tick = spiel.schritt()
        ereignis = [e for e in tick["ereignisse"] if e["art"] == "abliefern"][0]
        self.assertEqual(ereignis["teile"], [{"sorte": "papier", "wert": 10},
                                             {"sorte": SORTE_RADIOAKTIV, "wert": -120}])
        self.assertEqual(sum(t["wert"] for t in ereignis["teile"]), ereignis["punkte"])

    def test_negative_werte_werden_abgezogen(self):
        spiel = spiel_bauen([["warte"], ["warte"]])
        auf_depot(spiel, 0)
        lade(spiel, 0, [(SORTE_RADIOAKTIV, -120), ("papier", 10)])
        spiel.schritt()
        self.assertEqual(spiel.welt.roboter[0].punkte, -110)

    def test_volle_ladung_laedt_akku_ganz_auf(self):
        # Der Roboter steht schon auf dem Depot: bei Akku 0 wäre er langsam und käme
        # in einem ungeraden Tick gar nicht erst dorthin.
        cfg = config()
        spiel = spiel_bauen([["warte"], ["warte"]], cfg=cfg)
        r = auf_depot(spiel, 0)
        r.akku = 0
        lade(spiel, 0, [("papier", 1)] * cfg.spiel.kapazitaet)
        spiel.schritt()
        self.assertEqual(r.akku, cfg.akku.max)
        self.assertEqual(r.lade_ticks, 100 // cfg.akku.laden_prozent_pro_tick)

    def test_halbe_ladung_laedt_anteilig(self):
        cfg = config()
        spiel = spiel_bauen([["warte"], ["warte"]], cfg=cfg)
        r = auf_depot(spiel, 0)
        r.akku = 0
        lade(spiel, 0, [("papier", 1)] * (cfg.spiel.kapazitaet // 2))
        spiel.schritt()
        self.assertEqual(r.akku, cfg.akku.max // 2)

    def test_waehrend_des_ladens_keine_bewegung(self):
        cfg = config()
        spiel = spiel_bauen([["warte", "rechts", "rechts"], ["warte"]], cfg=cfg)
        r = auf_depot(spiel, 0)
        r.akku = 0
        lade(spiel, 0, [("papier", 1)] * cfg.spiel.kapazitaet)
        spiel.schritt()
        self.assertEqual(r.lade_ticks, 100 // cfg.akku.laden_prozent_pro_tick)
        spiel.schritt()
        self.assertEqual((r.x, r.y), r.depot,
                         "während des Ladens darf nichts passieren")
        spiel.schritt()
        self.assertEqual((r.x, r.y), r.depot)

    def test_fremdes_depot_liefert_nicht_ab(self):
        spiel = spiel_bauen([["rechts"], ["warte"]])
        fremd = depot(spiel, 1)
        setze(spiel, 0, fremd[0] - 1, fremd[1])
        setze(spiel, 1, 12, 5)
        lade(spiel, 0, [("papier", 10)])
        spiel.schritt()
        self.assertEqual(spiel.welt.roboter[0].punkte, 0)
        self.assertEqual(len(spiel.welt.roboter[0].ladung), 1)

    def test_ladender_wird_geschubst_und_laedt_weiter(self):
        """SPEC §5: Ein Ladender ist bewegungsunfähig, aber schiebbar."""
        cfg = config()
        spiel = spiel_bauen([["warte", "links"], ["warte", "rechts"]],
                            cfg=cfg, ticks=6)
        r = auf_depot(spiel, 0)
        r.akku = 0
        d = r.depot
        setze(spiel, 1, d[0] - 1, d[1])
        lade(spiel, 0, [("papier", 1)] * cfg.spiel.kapazitaet)

        spiel.schritt()
        self.assertGreater(r.lade_ticks, 0)
        rest = r.lade_ticks

        spiel.schritt()
        self.assertEqual((r.x, r.y), (d[0] + 1, d[1]),
                         "der Ladende muss sich schieben lassen")
        self.assertEqual(r.lade_ticks, rest - 1)
        ereignis = [e for e in spiel.ticks[-1]["ereignisse"]
                    if e["art"] == "rammen"][0]
        self.assertTrue(ereignis["geschoben"])


class TestAkku(unittest.TestCase):
    def test_langsam_nur_jeder_zweite_tick(self):
        cfg = config()
        spiel = spiel_bauen([["rechts"] * 4, ["warte"]], cfg=cfg)
        r = setze(spiel, 0, 5, 5)
        setze(spiel, 1, 20, 20)
        r.akku = cfg.akku.langsam_ab - 1
        spiel.schritt()                       # Tick 1 ist ungerade -> ignoriert
        self.assertEqual((r.x, r.y), (5, 5))
        spiel.schritt()                       # Tick 2 -> ausgeführt
        self.assertEqual((r.x, r.y), (6, 5))

    def test_akku_faellt_nie_unter_null(self):
        cfg = config()
        spiel = spiel_bauen([["rechts"] * 30, ["warte"]], cfg=cfg, ticks=30)
        r = setze(spiel, 0, 5, 5)
        setze(spiel, 1, 20, 20)
        r.akku = 1
        for _ in range(20):
            spiel.schritt()
        self.assertEqual(r.akku, 0)

    def test_leerer_akku_bewegt_sich_weiter(self):
        cfg = config()
        spiel = spiel_bauen([["rechts"] * 10, ["warte"]], cfg=cfg, ticks=10)
        r = setze(spiel, 0, 5, 5)
        setze(spiel, 1, 20, 20)
        r.akku = 0
        start = r.x
        for _ in range(6):
            spiel.schritt()
        self.assertGreater(r.x, start)


class TestAkkuLeer(unittest.TestCase):
    """SPEC §6: Wer auf 0 fällt, verliert die Ladung — radioaktive Fässer bleiben."""

    def spiel(self, aktionen, cfg=None):
        spiel = spiel_bauen(aktionen, cfg=cfg)
        # Unter `langsam_ab` fährt ein Roboter nur in geraden Ticks; der nächste ist Tick 2.
        spiel.welt.tick = 1
        return spiel

    def ereignisse(self, tick, art="akku_leer"):
        return [e for e in tick["ereignisse"] if e["art"] == art]

    def test_wer_auf_null_faellt_verliert_alles_ausser_dem_fass(self):
        spiel = self.spiel([["rechts"], ["warte"]])
        setze(spiel, 0, 5, 5)
        r = spiel.welt.roboter[0]
        r.akku = spiel.config.akku.kosten_bewegung
        lade(spiel, 0, [("papier", 10), (SORTE_RADIOAKTIV, -240), ("metall", 40)])
        tick = spiel.schritt()
        self.assertEqual(r.akku, 0)
        self.assertEqual([t["sorte"] for t in r.ladung], [SORTE_RADIOAKTIV])
        ereignis = self.ereignisse(tick)[0]
        self.assertEqual(ereignis["wer"], 0)
        self.assertEqual(ereignis["teile"], [{"sorte": "papier", "wert": 10},
                                             {"sorte": "metall", "wert": 40}])
        self.assertEqual(r.statistik["verloren"], 2)

    def test_wer_schon_leer_ist_verliert_nichts_mehr(self):
        # Sonst käme ein leerer Roboter nie wieder hoch: Laden geht nur übers Abliefern.
        spiel = self.spiel([["rechts"], ["warte"]])
        setze(spiel, 0, 5, 5)
        r = spiel.welt.roboter[0]
        r.akku = 0
        lade(spiel, 0, [("papier", 10)])
        tick = spiel.schritt()
        self.assertEqual(len(r.ladung), 1)
        self.assertEqual(self.ereignisse(tick), [])

    def test_wer_es_ins_depot_schafft_liefert_vorher_ab(self):
        spiel = self.spiel([["warte"], ["warte"]])
        auf_depot(spiel, 0)
        r = spiel.welt.roboter[0]
        dx, dy = r.depot
        setze(spiel, 0, dx - 1, dy)
        spiel.bots[0].aktionen = ["rechts"]
        r.akku = spiel.config.akku.kosten_bewegung
        lade(spiel, 0, [("metall", 40)])
        tick = spiel.schritt()
        self.assertEqual(r.punkte, 40)
        self.assertGreater(r.akku, 0)
        self.assertEqual(self.ereignisse(tick), [])

    def test_rammen_kann_den_gegner_leer_machen(self):
        spiel = self.spiel([["rechts"], ["warte"]])
        setze(spiel, 0, 5, 5)
        setze(spiel, 1, 6, 5)
        opfer = spiel.welt.roboter[1]
        opfer.akku = spiel.config.akku.kosten_rammen
        lade(spiel, 1, [("papier", 10), ("bio", 20), (SORTE_RADIOAKTIV, -240)])
        spiel.schritt()
        self.assertEqual(opfer.akku, 0)
        self.assertTrue(all(t["sorte"] == SORTE_RADIOAKTIV for t in opfer.ladung))

    def test_schalter_in_der_config(self):
        cfg = config(**{"akku.leer_verliert_ladung": False})
        spiel = self.spiel([["rechts"], ["warte"]], cfg=cfg)
        setze(spiel, 0, 5, 5)
        r = spiel.welt.roboter[0]
        r.akku = cfg.akku.kosten_bewegung
        lade(spiel, 0, [("papier", 10)])
        tick = spiel.schritt()
        self.assertEqual(r.akku, 0)
        self.assertEqual(len(r.ladung), 1)
        self.assertEqual(self.ereignisse(tick), [])


class TestRundenende(unittest.TestCase):
    def test_restladung_positiv_halbiert_negativ_voll(self):
        cfg = config()
        spiel = spiel_bauen([["warte"], ["warte"]], cfg=cfg, ticks=1)
        setze(spiel, 0, 5, 5)          # nicht auf dem Depot: sonst wird abgeliefert
        lade(spiel, 0, [("metall", 41), (SORTE_RADIOAKTIV, -120)])
        spiel.schritt()
        self.assertEqual(spiel.welt.roboter[0].punkte, 41 // 2 - 120)
        self.assertEqual(spiel.welt.roboter[0].ladung, [])

    def test_abrechnung_steht_teil_fuer_teil_im_ergebnis(self):
        spiel = spiel_bauen([["warte"], ["warte"]], ticks=1)
        setze(spiel, 0, 5, 5)
        spiel.welt.roboter[0].punkte = 100
        lade(spiel, 0, [("metall", 41), (SORTE_RADIOAKTIV, -120)])
        spiel.schritt()
        abrechnung = spiel.ergebnis.roboter[0]["abrechnung"]
        self.assertEqual(abrechnung["punkte_vorher"], 100)
        self.assertEqual(abrechnung["posten"], [
            {"sorte": "metall", "wert": 41, "punkte": 41 // 2},
            {"sorte": SORTE_RADIOAKTIV, "wert": -120, "punkte": -120}])
        self.assertEqual(abrechnung["punkte_vorher"]
                         + sum(p["punkte"] for p in abrechnung["posten"]),
                         spiel.ergebnis.roboter[0]["punkte"])
        # Ohne Ladung bleibt die Abrechnung leer.
        self.assertEqual(spiel.ergebnis.roboter[1]["abrechnung"]["posten"], [])

    def test_gleichstand_entscheidet_der_akku(self):
        spiel = spiel_bauen([["warte"], ["warte"]], ticks=1)
        spiel.welt.roboter[0].akku = 50
        spiel.welt.roboter[1].akku = 80
        spiel.schritt()
        self.assertEqual(spiel.ergebnis.sieger, 1)
        self.assertFalse(spiel.ergebnis.unentschieden)

    def test_echter_gleichstand_bleibt_unentschieden(self):
        spiel = spiel_bauen([["warte"], ["warte"]], ticks=1)
        spiel.schritt()
        self.assertTrue(spiel.ergebnis.unentschieden)
        self.assertIsNone(spiel.ergebnis.sieger)

    def test_gleichstand_entscheiden_abgelieferte_stuecke(self):
        """SPEC §10, drittes Kriterium: mehr abgelieferte Stücke gewinnt."""
        spiel = spiel_bauen([["warte"], ["warte"]], ticks=1)
        spiel.welt.roboter[0].statistik["abgeliefert_stueck"] = 1
        spiel.welt.roboter[1].statistik["abgeliefert_stueck"] = 2
        spiel.schritt()
        self.assertEqual(spiel.ergebnis.sieger, 1)
        self.assertFalse(spiel.ergebnis.unentschieden)


class TestAufzeichnungSchalter(unittest.TestCase):
    """Ohne Aufzeichnung darf nur der Endstand übrig bleiben — sonst nichts."""

    def bauen(self, aufzeichnen):
        bots = [SkriptBot("A", ["rechts", "unten", "links", "rechts"]), SkriptBot("B")]
        spiel = Spiel(config(), bots, seed=4, runden_laenge=8, aufzeichnen=aufzeichnen)
        spiel.spiele()
        return spiel

    def test_abgeschaltete_aufzeichnung_spart_nur_die_ticks(self):
        mit = self.bauen(True)
        ohne = self.bauen(False)
        self.assertEqual(len(mit.ticks), 8)
        self.assertIsNotNone(mit.start_abbild)
        self.assertEqual(ohne.ticks, [])
        self.assertIsNone(ohne.start_abbild)
        self.assertEqual(ohne.ergebnis.als_dict(), mit.ergebnis.als_dict())


class TestRundenlaenge(unittest.TestCase):
    """Die gespielte Länge muss auch beim Bot ankommen — nicht nur in der config.json."""

    def test_bot_sieht_die_tatsaechliche_laenge(self):
        spiel = spiel_bauen([["warte"], ["warte"]], ticks=30)
        self.assertEqual(spiel.welt.sicht(0)["runden_laenge"], 30)

    def test_ohne_override_gilt_die_config(self):
        bots = [SkriptBot("A"), SkriptBot("B")]
        spiel = Spiel(config(), bots, seed=1)
        self.assertEqual(spiel.welt.sicht(0)["runden_laenge"],
                         spiel.config.spiel.runden_laenge)


if __name__ == "__main__":
    unittest.main()
