"""Die Massenauswertung: Paarungsplan, Quotenmatrix und das Urteil.

Die Partien selbst spielt hier keine Prüfung — `auftraege_bauen`, `auswerten`,
`urteil` und die Kommandozeile kommen ohne Bot-Prozesse aus. Genau dort lagen
die Fehler bei leeren Ergebnissen.
"""

import contextlib
import io
import unittest
from unittest import mock

import balance


def bot(name, datei=None):
    datei = datei or (name.lower() + ".py")
    return {"name": name, "datei": datei, "pfad": "/bots/" + datei}


def eintrag(name, siegquote, massstab=True):
    return {"name": name, "siegquote": siegquote, "massstab": massstab}


class TestAuftraegeBauen(unittest.TestCase):
    def test_jede_paarung_kommt_genau_einmal_vor(self):
        bots = [bot("A"), bot("B"), bot("C")]
        auftraege = balance.auftraege_bauen(bots, [1], 20)
        self.assertEqual(len(auftraege), 6)
        self.assertEqual({frozenset((a[0], a[1])) for a in auftraege},
                         {frozenset((0, 1)), frozenset((0, 2)), frozenset((1, 2))})
        self.assertTrue(all(a[0] != a[1] for a in auftraege))

    def test_seeds_ticks_und_pfade_stehen_im_auftrag(self):
        bots = [bot("A"), bot("B")]
        auftraege = balance.auftraege_bauen(bots, [3, 4], 77)
        self.assertEqual(len(auftraege), 4)
        self.assertEqual({a[4] for a in auftraege}, {3, 4})
        self.assertTrue(all(a[5] == 77 for a in auftraege))
        self.assertTrue(all(a[2] == bots[a[0]]["pfad"] and a[3] == bots[a[1]]["pfad"]
                            for a in auftraege))

    def test_nur_behaelt_paarungen_mit_diesem_bot(self):
        bots = [bot("A"), bot("B"), bot("C")]
        auftraege = balance.auftraege_bauen(bots, [1, 2], 20, nur="a")
        self.assertEqual(len(auftraege), 8)
        self.assertTrue(all(0 in (a[0], a[1]) for a in auftraege))
        self.assertTrue(all({a[0], a[1]} != {1, 2} for a in auftraege))

    def test_nur_akzeptiert_dateiname_und_stamm(self):
        bots = [bot("A"), bot("B")]
        for name in ("a.py", "a"):
            with self.subTest(nur=name):
                self.assertEqual(len(balance.auftraege_bauen(bots, [1], 20, nur=name)), 2)

    def test_unbekanntes_nur_ergibt_keine_auftraege(self):
        bots = [bot("A"), bot("B")]
        self.assertEqual(balance.auftraege_bauen(bots, [1], 20, nur="gibtsnicht"), [])


class TestAuswerten(unittest.TestCase):
    def ergebnisse(self):
        return [
            (0, 1, 30, 10, "a", [False, False]),
            (0, 2, 20, 20, "unentschieden", [False, False]),
            (1, 2, 10, 40, "b", [True, False]),
        ]

    def test_sieg_niederlage_und_remis_zaehlen_je_zur_haelfte(self):
        bericht = balance.auswerten([bot("A"), bot("B"), bot("C")], self.ergebnisse())
        self.assertEqual(bericht["quoten"][0][1], 100.0)
        self.assertEqual(bericht["quoten"][1][0], 0.0)
        self.assertEqual(bericht["quoten"][0][2], 50.0)
        self.assertEqual(bericht["quoten"][2][0], 50.0)
        self.assertEqual(bericht["quoten"][2][1], 100.0)
        self.assertEqual(bericht["quoten"][1][2], 0.0)

    def test_diagonale_ist_leer(self):
        bericht = balance.auswerten([bot("A"), bot("B"), bot("C")], self.ergebnisse())
        self.assertTrue(all(bericht["quoten"][i][i] is None for i in range(3)))

    def test_kaputt_kommt_aus_den_tot_marken(self):
        bericht = balance.auswerten([bot("A"), bot("B"), bot("C")], self.ergebnisse())
        kaputt = {e["name"]: e["kaputt"] for e in bericht["gesamt"]}
        self.assertEqual(kaputt, {"A": False, "B": True, "C": False})

    def test_siegquote_und_punkte_schnitt(self):
        bericht = balance.auswerten([bot("A"), bot("B"), bot("C")], self.ergebnisse())
        gesamt = {e["name"]: e for e in bericht["gesamt"]}
        self.assertEqual(gesamt["A"]["siegquote"], 75.0)
        self.assertEqual(gesamt["A"]["punkte_schnitt"], 25)
        self.assertEqual(gesamt["B"]["siegquote"], 0.0)
        self.assertEqual(gesamt["B"]["punkte_schnitt"], 10)
        self.assertEqual(gesamt["C"]["siegquote"], 75.0)
        self.assertEqual(gesamt["C"]["punkte_schnitt"], 30)

    def test_bot_ohne_spiele_bleibt_ohne_werte(self):
        bericht = balance.auswerten([bot("A"), bot("B")], [])
        self.assertIsNone(bericht["quoten"][0][1])
        gesamt = {e["name"]: e for e in bericht["gesamt"]}
        self.assertIsNone(gesamt["A"]["siegquote"])
        self.assertIsNone(gesamt["A"]["punkte_schnitt"])

    def test_leere_matrix_kippt_nicht(self):
        ausgabe = io.StringIO()
        with contextlib.redirect_stdout(ausgabe):
            balance.matrix_drucken({"bots": [], "quoten": [], "gesamt": []})
        self.assertIn("Keine Paarungen gespielt.", ausgabe.getvalue())


class TestUrteil(unittest.TestCase):
    def bericht(self, *eintraege):
        return {"gesamt": list(eintraege)}

    def test_dominanter_bot_wird_gemeldet(self):
        text = balance.urteil(self.bericht(eintrag("A", 90.0), eintrag("B", 50.0)))
        self.assertIn("A gewinnt fast immer (90.0%)", text)

    def test_untergehender_bot_wird_gemeldet(self):
        text = balance.urteil(self.bericht(eintrag("A", 50.0), eintrag("B", 10.0)))
        self.assertIn("B verliert fast immer (10.0%)", text)

    def test_ausgeglichene_lage_ohne_meldung(self):
        text = balance.urteil(self.bericht(eintrag("A", 60.0), eintrag("B", 40.0)))
        self.assertEqual(text, "Kein Bot dominiert und keiner geht unter — die Balance "
                               "ist brauchbar.")

    def test_leerer_bericht(self):
        self.assertEqual(balance.urteil(self.bericht()), "Keine Paarungen gespielt.")

    def test_bots_ohne_massstab_zaehlen_nicht(self):
        text = balance.urteil(self.bericht(eintrag("Rumpel", 100.0, massstab=False),
                                           eintrag("B", 50.0)))
        self.assertEqual(text, "Kein Bot dominiert und keiner geht unter — die Balance "
                               "ist brauchbar.")


class TestHauptprogramm(unittest.TestCase):
    def test_null_oder_negative_seeds_brechen_mit_meldung_ab(self):
        for wert in ("0", "-5"):
            with self.subTest(seeds=wert):
                fehler = io.StringIO()
                with contextlib.redirect_stderr(fehler):
                    with self.assertRaises(SystemExit):
                        balance.main(["--seeds", wert])
                self.assertIn("--seeds muss mindestens 1 sein", fehler.getvalue())

    def test_unbekanntes_nur_endet_ohne_prozesse_und_mit_meldung(self):
        ausgabe = io.StringIO()
        with mock.patch.object(balance.multiprocessing, "get_context",
                               side_effect=AssertionError("Es wurden Prozesse gestartet")):
            with contextlib.redirect_stdout(ausgabe):
                ergebnis = balance.main(["--seeds", "1", "--nur", "gibtsnicht"])
        self.assertEqual(ergebnis, 1)
        text = ausgabe.getvalue()
        self.assertIn("gibtsnicht", text)
        self.assertIn("Keine Paarungen", text)


if __name__ == "__main__":
    unittest.main()
