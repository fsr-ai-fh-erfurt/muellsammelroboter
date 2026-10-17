"""Bot-Prozesse: Abstürze, Endlosschleifen, Unsinn und Geschwätz dürfen nichts anhalten."""

import os
import queue
import threading
import time
import unittest

from engine.game import Spiel
from engine.runner import Anschlussgruppe, BotAnschluss, MELDUNGEN_MAX
from tests.hilfen import config

ORDNER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kaputte_bots")
BRAV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "bots", "fleissig.py")


def spielen(kaputt, ticks=12, **cfg_aenderungen):
    cfg = config(**cfg_aenderungen)
    pfade = [os.path.join(ORDNER, kaputt), BRAV]
    with Anschlussgruppe(pfade, cfg) as anschluesse:
        spiel = Spiel(cfg, anschluesse, seed=1, runden_laenge=ticks)
        spiel.spiele()
        return spiel, anschluesse


class TestProzessschutz(unittest.TestCase):

    def test_absturz_haelt_die_runde_nicht_an(self):
        spiel, anschluesse = spielen("absturz.py")
        self.assertTrue(spiel.beendet)
        self.assertEqual(spiel.ergebnis.ticks, 12)
        self.assertTrue(anschluesse[0].fehler)

    def test_endlosschleife_kostet_nur_die_eigenen_zuege(self):
        spiel, anschluesse = spielen(
            "endlosschleife.py", ticks=8,
            **{"bots.zeitlimit_ms": 30, "bots.kill_nach_ueberzogen": 3,
               "bots.neustarts_max": 1, "bots.start_zeitlimit_ms": 3000})
        self.assertTrue(spiel.beendet)
        self.assertGreater(anschluesse[0].statistik["ueberzogen"], 0)
        start = spiel.welt.roboter[0].depot
        self.assertEqual((spiel.welt.roboter[0].x, spiel.welt.roboter[0].y),
                         start, "ein hängender Bot darf sich nicht bewegen")
        self.assertGreater(spiel.welt.roboter[1].statistik["bewegungen"], 0)

    def test_unsinniger_rueckgabewert_gilt_als_warte(self):
        spiel, _ = spielen("unsinn.py")
        self.assertTrue(spiel.beendet)
        self.assertEqual((spiel.welt.roboter[0].x, spiel.welt.roboter[0].y),
                         spiel.welt.roboter[0].depot)

    def test_rueckgabe_none_gilt_als_warte(self):
        spiel, anschluesse = spielen("rueckgabe_none.py")
        self.assertTrue(spiel.beendet)
        self.assertEqual((spiel.welt.roboter[0].x, spiel.welt.roboter[0].y),
                         spiel.welt.roboter[0].depot)
        self.assertEqual(anschluesse[0].fehler, [])

    def test_rueckgabe_dict_gilt_als_warte(self):
        spiel, anschluesse = spielen("rueckgabe_dict.py")
        self.assertTrue(spiel.beendet)
        self.assertEqual((spiel.welt.roboter[0].x, spiel.welt.roboter[0].y),
                         spiel.welt.roboter[0].depot)
        self.assertEqual(anschluesse[0].fehler, [])

    def test_unbekannte_richtung_gilt_als_warte(self):
        spiel, anschluesse = spielen("unbekannte_richtung.py")
        self.assertTrue(spiel.beendet)
        self.assertEqual((spiel.welt.roboter[0].x, spiel.welt.roboter[0].y),
                         spiel.welt.roboter[0].depot)
        self.assertEqual(anschluesse[0].fehler, [])

    def test_stderr_flut_wird_gekappt(self):
        spiel, anschluesse = spielen("stderr_flut.py")
        self.assertTrue(spiel.beendet)
        self.assertEqual(len(anschluesse[0].meldungen), MELDUNGEN_MAX + 1)
        self.assertIn("weitere Ausgaben", anschluesse[0].meldungen[-1])
        self.assertEqual(anschluesse[0].fehler, [])

    def test_konsolenausgabe_zerstoert_das_protokoll_nicht(self):
        spiel, anschluesse = spielen("schwatzhaft.py")
        self.assertTrue(spiel.beendet)
        self.assertGreater(spiel.welt.roboter[0].statistik["bewegungen"], 0,
                           "der Bot muss trotz print() normal spielen")
        self.assertTrue(anschluesse[0].meldungen)
        self.assertIn("Ich denke nach", anschluesse[0].meldungen[0])

    def test_syntaxfehler_wird_gemeldet(self):
        spiel, anschluesse = spielen("syntaxfehler.py", ticks=4)
        self.assertTrue(anschluesse[0].tot)
        self.assertTrue(any("SyntaxError" in f for f in anschluesse[0].fehler))
        self.assertTrue(spiel.beendet)

    def test_fehler_beim_laden_wird_gemeldet(self):
        spiel, anschluesse = spielen("beim_start_kaputt.py", ticks=4)
        self.assertTrue(anschluesse[0].tot)
        self.assertTrue(any("RuntimeError" in f for f in anschluesse[0].fehler))
        self.assertTrue(spiel.beendet)


class TestStartUndNeustart(unittest.TestCase):

    def test_haengender_start_laeuft_in_die_startfrist(self):
        spiel, anschluesse = spielen(
            "haengt_beim_import.py", ticks=4,
            **{"bots.start_zeitlimit_ms": 300})
        self.assertTrue(spiel.beendet)
        self.assertTrue(anschluesse[0].tot)
        self.assertTrue(any("beim Start" in f for f in anschluesse[0].fehler))

    def test_absturz_mitten_im_spiel_fuehrt_zu_neustart(self):
        spiel, anschluesse = spielen(
            "stirbt_mitte.py", ticks=8,
            **{"bots.neustarts_max": 1, "bots.start_zeitlimit_ms": 3000})
        self.assertTrue(spiel.beendet)
        self.assertEqual(anschluesse[0].statistik["neustarts"], 1)
        self.assertTrue(anschluesse[0].tot)

    def test_neustart_loescht_das_modusgedaechtnis(self):
        """SPEC §11: Nach dem Neustart beginnt ein Bot wieder im Startmodus."""
        spiel, anschluesse = spielen(
            "modus_gedaechtnis.py", ticks=5,
            **{"bots.neustarts_max": 1, "bots.start_zeitlimit_ms": 3000})
        self.assertTrue(spiel.beendet)
        self.assertEqual(anschluesse[0].statistik["neustarts"], 1)
        gewuenscht = [tick["gewuenscht"][0] for tick in spiel.ticks]
        self.assertEqual(gewuenscht[:4], ["rechts", "links", "warte", "rechts"],
                         "der Bot muss wieder im Startmodus anfangen")


class TestSchreibfrist(unittest.TestCase):
    """Ein blockierender Schreibvorgang darf den Elternprozess nicht aufhängen."""

    def _anschluss_bauen(self):
        anschluss = object.__new__(BotAnschluss)
        anschluss._prozess = None
        anschluss._schreib_schlange = queue.Queue()
        return anschluss

    def _writer_starten(self, anschluss, prozess):
        threading.Thread(target=anschluss._stdin_schreiben,
                         args=(prozess, anschluss._schreib_schlange),
                         daemon=True).start()

    def test_blockiertes_schreiben_haelt_die_frist_ein(self):
        class HaengenderKanal:
            def write(self, text):
                time.sleep(5)

            def flush(self):
                pass

        class FakeProzess:
            stdin = HaengenderKanal()

        anschluss = self._anschluss_bauen()
        anschluss._prozess = FakeProzess()
        self._writer_starten(anschluss, anschluss._prozess)
        beginn = time.monotonic()
        ergebnis = anschluss._schreiben("x\n", beginn + 0.05)
        gedauert = time.monotonic() - beginn
        self.assertEqual(ergebnis, "zeit")
        self.assertLess(gedauert, 1.0)

    def test_gebrochene_pipe_gilt_als_fehler(self):
        class KaputterKanal:
            def write(self, text):
                raise BrokenPipeError()

            def flush(self):
                pass

        class FakeProzess:
            stdin = KaputterKanal()

        anschluss = self._anschluss_bauen()
        anschluss._prozess = FakeProzess()
        self._writer_starten(anschluss, anschluss._prozess)
        self.assertEqual(anschluss._schreiben("x\n", time.monotonic() + 1.0), "fehler")


if __name__ == "__main__":
    unittest.main()
