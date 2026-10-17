"""Was nach einem Testlauf gemeldet wird: Stillstand, Folgen ins Leere, Kreise."""

import unittest

from engine import laufbericht
from engine.laufbericht import STILLSTAND_AB, bericht


def roboter(x, y, laedt=0):
    return {"x": x, "y": y, "laedt": laedt}


def aufzeichnung(wege, regeln, aktionen=None, meldungen=()):
    """Eine Aufzeichnung mit einem Roboter: `wege` sind die Felder nach jedem Tick."""
    ticks = []
    for index, (x, y) in enumerate(wege):
        ticks.append({
            "tick": index + 1,
            "roboter": [roboter(x, y)],
            "regeln": [regeln[index]],
            "aktionen": [aktionen[index] if aktionen else "warte"],
        })
    return {"start": {"roboter": [roboter(*wege[0])]}, "ticks": ticks,
            "bots": [{"meldungen": list(meldungen)}]}


REGELN = [
    {"nummer": 1, "zeile": 4, "folge": None},
    {"nummer": 2, "zeile": 7, "folge": None},
    {"nummer": 3, "zeile": 7, "folge": {"zeile": 7, "schritt": 1, "von": 2, "richtung": "links"}},
    {"nummer": 4, "zeile": 7, "folge": {"zeile": 7, "schritt": 2, "von": 2, "richtung": "oben"}},
]


class TestStillstand(unittest.TestCase):
    def test_langes_stehen_wird_gemeldet(self):
        wege = [(5, 5)] * 3 + [(5, 6)] * (STILLSTAND_AB + 5)
        meldung, = bericht(aufzeichnung(wege, [1] * len(wege)), REGELN)
        self.assertIn("nicht vom Fleck", meldung["text"])
        self.assertIn("Regel 1 (Zeile 4)", meldung["text"])
        self.assertEqual(meldung["zeile"], 4)

    def test_pendeln_zaehlt_als_stillstand(self):
        wege = [(5, 5), (5, 6)] * STILLSTAND_AB
        self.assertEqual(len(bericht(aufzeichnung(wege, [1] * len(wege)), REGELN)), 1)

    def test_kurzes_warten_bleibt_still(self):
        # Das Feld davor zählt als zweites Feld mit — also deutlich unter der Schwelle.
        wege = [(x, 1) for x in range(10)] + [(9, 1)] * (STILLSTAND_AB - 4)
        self.assertEqual(bericht(aufzeichnung(wege, [1] * len(wege)), REGELN), [])

    def test_abladen_ist_kein_stillstand(self):
        wege = [(2, 2)] * (STILLSTAND_AB + 5)
        daten = aufzeichnung(wege, [1] * len(wege))
        for tick in daten["ticks"]:
            tick["roboter"][0]["laedt"] = 1
        self.assertEqual(bericht(daten, REGELN), [])


class TestFolgeInsLeere(unittest.TestCase):
    def test_versperrter_schritt_wird_gemeldet(self):
        # Schritt 1 will nach links, bleibt aber auf (3, 3); Schritt 2 kommt nach oben.
        wege = [(3, 3), (3, 3), (3, 2)]
        daten = aufzeichnung(wege, [2, 3, 4], ["warte", "links", "oben"])
        meldung, = bericht(daten, REGELN)
        self.assertIn("Folge aus Zeile 7", meldung["text"])
        self.assertIn("einmal", meldung["text"])
        self.assertIn("Schritt 1 (nach links)", meldung["text"])
        self.assertIn("Zug 2", meldung["text"])
        self.assertEqual(meldung["zeile"], 7)

    def test_langsamer_zug_ist_nicht_versperrt(self):
        # Mit wenig Akku wird aus `links` ein `warte` — das ist kein Hindernis.
        daten = aufzeichnung([(3, 3), (3, 3)], [2, 3], ["warte", "warte"])
        self.assertEqual(bericht(daten, REGELN), [])


class TestKreis(unittest.TestCase):
    def test_kreis_aus_den_ausgaben(self):
        meldungen = ["Achtung: die Modi wechseln im Kreis (zuletzt folge_z32_schritt1)."] * 3
        daten = aufzeichnung([(1, 1), (1, 2)], [1, 1], meldungen=meldungen)
        meldung, = bericht(daten, REGELN)
        self.assertIn("In 3 Zügen", meldung["text"])
        self.assertIn("Folge aus Zeile 32", meldung["text"])
        self.assertEqual(meldung["zeile"], 32)

    def test_abgeschnittene_ausgaben(self):
        meldungen = ["Achtung: die Modi wechseln im Kreis (zuletzt heimweg)."] * 2 + [
            "... weitere Ausgaben werden nicht mehr angezeigt."]
        meldung, = bericht(aufzeichnung([(1, 1), (1, 2)], [1, 1], meldungen=meldungen), REGELN)
        self.assertIn("mindestens 2", meldung["text"])
        self.assertIn("`heimweg`", meldung["text"])

    def test_text_passt_zum_erzeugten_code(self):
        """Der Bericht erkennt die Zeile, die der erzeugte Automat ausgibt."""
        from language.compiler import uebersetzen
        quelle = uebersetzen("STATE a\n  ELSE GOTO b\nSTATE b\n  ELSE GOTO a", "T")["quelle"]
        muster = 'print("Achtung: die Modi wechseln im Kreis (zuletzt %s)." % self.modus)'
        self.assertIn(muster, quelle)
        self.assertTrue(laufbericht.KREIS.match(
            "Achtung: die Modi wechseln im Kreis (zuletzt a)."))


if __name__ == "__main__":
    unittest.main()
