"""Zeitlimit: die mitgelieferten Gegner müssen deutlich darunter bleiben.

Ein Bot, der über dem Limit liegt, setzt Züge aus — das würde ein Turnier still
verfälschen. Deshalb misst dieser Test die schlimmste beobachtete Rundenzeit.
"""

import os
import time
import unittest

from engine.game import Spiel
from engine.runner import Anschlussgruppe
from engine.world import Welt
from engine.zustand import Zustand
from tests.hilfen import config

BOT_ORDNER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bots")


class TestLeistung(unittest.TestCase):

    def test_gegner_bleiben_unter_dem_zeitlimit(self):
        # Feste Auswahl statt „die ersten vier im Ordner": Die Abdeckung soll sich
        # nicht verschieben, wenn neue Bots dazukommen. Der Lauerer rechnet am meisten.
        cfg = config()
        pfade = [os.path.join(BOT_ORDNER, f + ".py")
                 for f in ("fleissig", "hausmeister", "lauerer", "fassbluffer")]
        with Anschlussgruppe(pfade, cfg) as anschluesse:
            spiel = Spiel(cfg, anschluesse, seed=5, spieler=4, runden_laenge=200)
            spiel.spiele()
            for anschluss in anschluesse:
                self.assertEqual(
                    anschluss.statistik["ueberzogen"], 0,
                    "%s hat das Zeitlimit von %d ms überschritten"
                    % (anschluss.name, cfg.bots.zeitlimit_ms))

    def test_viele_muellstuecke_bremsen_die_wegfindung_nicht(self):
        """Der teure Fall: Wert-gegen-Weg über ein volles Feld.

        Gemessen wird der beste von drei Durchläufen — sonst entscheidet die
        Auslastung des Prüfrechners über den Testausgang.
        """
        cfg = config()
        welt = Welt(cfg, ["A", "B"], seed=3)
        from engine.world import Muell
        nummer = 0
        for y in range(1, welt.hoehe - 1):
            for x in range(1, welt.breite - 1):
                if welt.ist_depot(x, y) or (x, y) in welt.muell:
                    continue
                nummer += 1
                if nummer > cfg.muell.max_auf_feld:
                    break
                welt.muell[(x, y)] = Muell(x, y, "papier", 10, 0)
        zustand = Zustand(welt.sicht(0))
        messungen = []
        for _ in range(3):
            beginn = time.monotonic()
            for stueck in zustand.muell_auswahl():
                zustand.abstand_zu_feld(stueck["x"], stueck["y"])
            messungen.append(time.monotonic() - beginn)
        dauer = min(messungen)
        budget = cfg.bots.zeitlimit_ms / 1000.0 / 2
        self.assertLess(dauer, budget,
                        "Wert-gegen-Weg über %d Stücke dauert %.1f ms (Budget %.1f ms)"
                        % (len(zustand.muell), dauer * 1000, budget * 1000))


    def test_erzeugter_automat_bleibt_unter_dem_zeitlimit(self):
        """Modi + `BEST muell BY` — der teuerste Weg, den die Regelsprache erlaubt.

        Ein Moduswechsel kostet keinen Zug, es können also mehrere Durchläufe je Tick
        zusammenkommen, und jeder rechnet über alle Müllstücke.
        """
        import tempfile
        from engine import spielleiter
        from language.compiler import uebersetzen

        pseudocode = ("IF akku < 5 THEN GOTO notfall\n"
                      "STATE sammeln\n"
                      "  IF ladung_ist_voll THEN GOTO heimweg\n"
                      "  ELSE fahre_zu BEST muell BY wert * bonus - 3 * abstand\n"
                      "STATE heimweg\n"
                      "  IF ladung_ist_leer THEN GOTO sammeln\n"
                      "  ELSE fahre_zu depot\n"
                      "STATE notfall\n"
                      "  IF abstand_zu depot == 0 THEN GOTO sammeln\n"
                      "  ELSE fahre_zu depot")
        ergebnis = uebersetzen(pseudocode, "Team Automat")
        self.assertTrue(ergebnis["gueltig"], ergebnis["fehler"])
        cfg = config()
        with tempfile.TemporaryDirectory() as ordner:
            pfad = os.path.join(ordner, "automat.py")
            with open(pfad, "w", encoding="utf-8") as datei:
                datei.write(ergebnis["quelle"])
            aufzeichnung = spielleiter.match(
                cfg, [pfad, os.path.join(BOT_ORDNER, "hausmeister.py")],
                seed=5, ticks=150)
        for bot in aufzeichnung["bots"]:
            self.assertEqual(
                bot["statistik"]["ueberzogen"], 0,
                "%s hat das Zeitlimit von %d ms überschritten"
                % (bot["name"], cfg.bots.zeitlimit_ms))
            self.assertEqual(bot["fehler"], [])


if __name__ == "__main__":
    unittest.main()
