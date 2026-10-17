"""Gruppenphase, K.-o.-Baum und das Turnierarchiv.

Die Partien selbst sind an anderer Stelle geprüft. Hier geht es um das Drumherum:
Setzliste, Freilose, Gleichstandswiederholung, Punktevergabe und Ablage. Wo eine
echte Partie nichts beweist, wird `spielleiter.nur_ergebnis` ersetzt — das spart
Prozesse und macht den Ausgang vorhersagbar.
"""

import json
import os
import shutil
import tempfile
import unittest

from engine import spielleiter, tournament
from tests.hilfen import config


def bot(name, datei=None):
    datei = datei or (name.lower() + ".py")
    return {"name": name, "datei": datei,
            "pfad": os.path.join(spielleiter.BOT_ORDNER, "fleissig.py")}


def ergebnis_bauen(punkte, unentschieden=False, akku=None):
    """Ein Endstand, wie ihn `spielleiter.nur_ergebnis` liefern würde."""
    akku = akku or [50] * len(punkte)
    roboter = [{"punkte": p, "akku": a, "statistik": {"abgeliefert_stueck": 0}}
               for p, a in zip(punkte, akku)]
    reihenfolge = sorted(range(len(punkte)), key=lambda i: (-punkte[i], i))
    return {
        "seed": 0, "ticks": 1, "roboter": roboter,
        "sieger": None if unentschieden else reihenfolge[0],
        "reihenfolge": reihenfolge,
        "unentschieden": unentschieden,
        "bots": [{"name": "B%d" % i, "tot": False, "statistik": {}, "fehler": []}
                 for i in range(len(punkte))],
    }


class Ersatz:
    """Setzt `spielleiter.nur_ergebnis` für die Dauer eines Tests aus.

    Eine Antwort darf eine feste Endstand-Vorlage sein oder eine Funktion. Ohne
    `mit_namen` bekommt sie nur die laufende Nummer, sonst zusätzlich die Namen
    der Beteiligten in Partie-Reihenfolge.
    """

    def __init__(self, antwort, mit_namen=False):
        self.antwort = antwort
        self.mit_namen = mit_namen
        self.aufrufe = []
        self.echt = None

    def __enter__(self):
        self.echt = tournament.spielleiter.nur_ergebnis

        def ersatz(cfg, pfade, seed=1, ticks=None, spieler=None, namen=None):
            self.aufrufe.append({"seed": seed, "namen": list(namen or []),
                                 "pfade": list(pfade or [])})
            antwort = self.antwort
            if not callable(antwort):
                return antwort
            nummer = len(self.aufrufe) - 1
            if self.mit_namen:
                return antwort(nummer, list(namen or []))
            return antwort(nummer)

        tournament.spielleiter.nur_ergebnis = ersatz
        return self

    def __exit__(self, *_):
        tournament.spielleiter.nur_ergebnis = self.echt
        return False


def setzplatz(name):
    """'S7' -> 7 — die Reihenfolge der übergebenen Bots ist die Setzliste."""
    return int(name[1:])


def favorit(nummer, namen):
    """Fake-Ergebnis: die bessere Setzung gewinnt, egal auf welcher Seite sie steht."""
    a, b = namen
    return ergebnis_bauen([100, 20] if setzplatz(a) < setzplatz(b) else [20, 100])


# --------------------------------------------------------------------- Setzliste

class TestSetzliste(unittest.TestCase):
    def test_standardbracket_reihenfolge(self):
        bots = [bot("B%d" % i) for i in range(8)]
        paare = tournament.setzliste(bots)
        self.assertEqual(len(paare), 4)
        self.assertEqual([(a["name"], b["name"]) for a, b in paare],
                         [("B0", "B7"), ("B3", "B4"), ("B1", "B6"), ("B2", "B5")])

    def test_freilose_gehen_an_die_hoechsten_setzungen(self):
        bots = [bot("B%d" % i) for i in range(5)]
        paare = tournament.setzliste(bots)
        self.assertEqual(len(paare), 4)                  # aufgefüllt auf acht Plätze
        self.assertEqual([(a["name"] if a else None, b["name"] if b else None)
                          for a, b in paare],
                         [("B0", None), ("B3", "B4"), ("B1", None), ("B2", None)])

    def test_zweierfeld_hat_genau_eine_partie(self):
        paare = tournament.setzliste([bot("A"), bot("B")])
        self.assertEqual([(a["name"], b["name"]) for a, b in paare], [("A", "B")])


class TestPartieSeed(unittest.TestCase):
    def test_gleiche_eingabe_gleicher_seed(self):
        self.assertEqual(tournament.partie_seed(7, 2, 3), tournament.partie_seed(7, 2, 3))

    def test_runde_und_nummer_trennen(self):
        seeds = {tournament.partie_seed(1, runde, nummer)
                 for runde in range(1, 6) for nummer in range(8)}
        self.assertEqual(len(seeds), 40)


# --------------------------------------------------------------------- Duell

class TestDuell(unittest.TestCase):
    def setUp(self):
        self.config = config()

    def test_klarer_sieg_wird_nicht_wiederholt(self):
        with Ersatz(ergebnis_bauen([100, 20])) as ersatz:
            partie = tournament.duell(self.config, bot("A"), bot("B"), seed=5)
        self.assertEqual(len(ersatz.aufrufe), 1)
        self.assertEqual(partie["wiederholungen"], 0)
        self.assertEqual(partie["sieger"], 0)
        self.assertEqual(partie["punkte"], [100, 20])

    def test_unentschieden_wird_mit_dem_naechsten_seed_wiederholt(self):
        cfg = config(**{"turnier.gleichstand_wiederholungen": 3})
        with Ersatz(ergebnis_bauen([50, 50], unentschieden=True)) as ersatz:
            partie = tournament.duell(cfg, bot("A"), bot("B"), seed=10)
        self.assertEqual([a["seed"] for a in ersatz.aufrufe], [10, 11, 12, 13])
        self.assertEqual(partie["wiederholungen"], 3)
        self.assertTrue(partie["unentschieden"])

    def test_wiederholung_endet_beim_ersten_sieger(self):
        def antwort(nummer):
            return ergebnis_bauen([50, 50], unentschieden=nummer < 2)
        with Ersatz(antwort) as ersatz:
            partie = tournament.duell(self.config, bot("A"), bot("B"), seed=1)
        self.assertEqual(len(ersatz.aufrufe), 3)
        self.assertEqual(partie["wiederholungen"], 2)
        self.assertFalse(partie["unentschieden"])

    def test_wiederholungen_kommen_aus_der_config(self):
        cfg = config(**{"turnier.gleichstand_wiederholungen": 0})
        with Ersatz(ergebnis_bauen([50, 50], unentschieden=True)) as ersatz:
            partie = tournament.duell(cfg, bot("A"), bot("B"), seed=1)
        self.assertEqual(len(ersatz.aufrufe), 1)
        self.assertEqual(partie["wiederholungen"], 0)

    def test_die_gespielte_laenge_steht_im_ergebnis(self):
        """Die Bühne spielt eine Partie mit `seed` und `ticks` nach — beides muss
        aus dem Ergebnis hervorgehen, nicht aus der gerade geladenen config.json."""
        with Ersatz(ergebnis_bauen([100, 20])):
            ohne_angabe = tournament.duell(self.config, bot("A"), bot("B"), seed=5)
            mit_angabe = tournament.duell(self.config, bot("A"), bot("B"), seed=5,
                                          ticks=77)
        self.assertEqual(ohne_angabe["ticks"], self.config.spiel.runden_laenge)
        self.assertEqual(mit_angabe["ticks"], 77)


# --------------------------------------------------------------------- K.-o.

class TestKo(unittest.TestCase):
    def setUp(self):
        self.config = config()

    def test_vier_roboter_zwei_runden_ein_sieger(self):
        with Ersatz(ergebnis_bauen([100, 20])):        # immer gewinnt der Erstgenannte
            turnier = tournament.ko_turnier(
                self.config, [bot("A"), bot("B"), bot("C"), bot("D")], seed=1)
        self.assertEqual([r["name"] for r in turnier["runden"]], ["Halbfinale", "Finale"])
        self.assertEqual(turnier["sieger"]["name"], "A")

    def test_freilos_kommt_ohne_partie_weiter(self):
        with Ersatz(ergebnis_bauen([100, 20])) as ersatz:
            turnier = tournament.ko_turnier(
                self.config, [bot("A"), bot("B"), bot("C")], seed=1)
        erste = turnier["runden"][0]["partien"]
        self.assertEqual(sum(1 for p in erste if p["freilos"]), 1)
        self.assertEqual([p for p in erste if p["freilos"]][0]["sieger_bot"]["name"], "A")
        self.assertEqual(len(ersatz.aufrufe), 2)       # B gegen C, dann das Finale
        self.assertEqual(turnier["sieger"]["name"], "A")

    def test_jeder_roboter_taucht_in_der_ersten_runde_auf(self):
        bots = [bot("B%d" % i) for i in range(6)]
        with Ersatz(ergebnis_bauen([100, 20])):
            turnier = tournament.ko_turnier(self.config, bots, seed=3)
        namen = set()
        for partie in turnier["runden"][0]["partien"]:
            for seite in ("a", "b", "sieger_bot"):
                eintrag = partie.get(seite)
                if eintrag:
                    namen.add(eintrag["name"])
        self.assertEqual(namen, {b["name"] for b in bots})

    def test_favoriten_treffen_sich_erst_im_finale(self):
        bots = [bot("S%d" % i) for i in range(1, 17)]

        with Ersatz(favorit, mit_namen=True) as ersatz:
            turnier = tournament.ko_turnier(self.config, bots, seed=1)

        # 8 + 4 + 2 + 1 Partien und das Spiel um Platz 3
        self.assertEqual(len(ersatz.aufrufe), 16)
        viertel = turnier["runden"][1]
        self.assertEqual(viertel["name"], "Viertelfinale")
        paare = [frozenset((p["a"]["name"], p["b"]["name"]))
                 for p in viertel["partien"]]
        self.assertEqual(set(paare),
                         {frozenset(("S1", "S8")), frozenset(("S4", "S5")),
                          frozenset(("S3", "S6")), frozenset(("S2", "S7"))})
        self.assertFalse(any({"S1", "S2"} <= paar for paar in paare))
        finale = turnier["runden"][-1]["partien"][0]
        self.assertEqual({finale["a"]["name"], finale["b"]["name"]}, {"S1", "S2"})
        self.assertEqual(turnier["sieger"]["name"], "S1")
        self.assertEqual([b["name"] for b in turnier["podest"]], ["S1", "S2", "S3"])

    def test_freilose_der_fuenf_und_die_wege_der_besten(self):
        bots = [bot("S%d" % i) for i in range(1, 6)]

        with Ersatz(favorit, mit_namen=True):
            turnier = tournament.ko_turnier(self.config, bots, seed=1)

        erste = turnier["runden"][0]["partien"]
        self.assertEqual([p["freilos"] for p in erste], [True, False, True, True])
        self.assertEqual([p["sieger_bot"]["name"] for p in erste if p["freilos"]],
                         ["S1", "S2", "S3"])
        # Bei fünf Teams treffen sich zwangsläufig zwei Freilose in Runde 2; S1 ist
        # aber nicht dabei, und die beiden besten Setzungen trennen sich bis zum Finale.
        zweite = turnier["runden"][1]["partien"]
        self.assertEqual([(p["a"]["name"], p["b"]["name"]) for p in zweite],
                         [("S1", "S4"), ("S2", "S3")])
        finale = turnier["runden"][-1]["partien"][0]
        self.assertEqual({finale["a"]["name"], finale["b"]["name"]}, {"S1", "S2"})
        self.assertEqual(turnier["sieger"]["name"], "S1")

    def test_upset_und_gleichstand_entscheidet_die_bessere_setzung(self):
        bots = [bot("S1"), bot("S2"), bot("S3"), bot("S4")]

        def antwort(nummer):
            if nummer == 0:
                return ergebnis_bauen([20, 100])         # S4 schlägt S1 (Upset)
            if nummer == 1:
                return ergebnis_bauen([100, 20])         # S2 schlägt S3
            return ergebnis_bauen([50, 50], unentschieden=True)

        with Ersatz(antwort):
            turnier = tournament.ko_turnier(self.config, bots, seed=1)

        finale = turnier["runden"][-1]["partien"][0]
        self.assertEqual((finale["a"]["name"], finale["b"]["name"]), ("S4", "S2"))
        self.assertEqual(finale["entschieden_durch"], "Setzliste")
        self.assertEqual(finale["sieger_bot"]["name"], "S2")
        self.assertEqual(turnier["sieger"]["name"], "S2")

    def test_dauerhaftes_unentschieden_entscheidet_die_setzliste(self):
        with Ersatz(ergebnis_bauen([50, 50], unentschieden=True)):
            turnier = tournament.ko_turnier(self.config, [bot("A"), bot("B")], seed=1)
        partie = turnier["runden"][0]["partien"][0]
        self.assertEqual(partie["entschieden_durch"], "Setzliste")
        self.assertEqual(partie["sieger_bot"]["name"], "A")
        self.assertEqual(turnier["sieger"]["name"], "A")

    def test_gleicher_seed_gleiche_partieseeds(self):
        bots = [bot("B%d" % i) for i in range(4)]
        with Ersatz(ergebnis_bauen([100, 20])) as erst:
            tournament.ko_turnier(self.config, bots, seed=42)
        with Ersatz(ergebnis_bauen([100, 20])) as zweit:
            tournament.ko_turnier(self.config, bots, seed=42)
        self.assertEqual([a["seed"] for a in erst.aufrufe],
                         [a["seed"] for a in zweit.aufrufe])

    def test_rundennamen_richten_sich_nach_der_feldgroesse(self):
        self.assertEqual(tournament.runden_name(1), "Finale")
        self.assertEqual(tournament.runden_name(2), "Halbfinale")
        self.assertEqual(tournament.runden_name(4), "Viertelfinale")
        self.assertEqual(tournament.runden_name(8), "Achtelfinale")


# --------------------------------------------------------------------- Platz 3

class TestPlatzDrei(unittest.TestCase):
    def setUp(self):
        self.config = config()

    def test_halbfinalverlierer_spielen_um_platz_3(self):
        bots = [bot("S%d" % i) for i in range(1, 5)]
        with Ersatz(favorit, mit_namen=True) as ersatz:
            turnier = tournament.ko_turnier(self.config, bots, seed=1)
        platz3 = turnier["spiel_um_platz_3"]
        self.assertEqual({platz3["a"]["name"], platz3["b"]["name"]}, {"S3", "S4"})
        self.assertFalse(platz3["freilos"])
        self.assertEqual(platz3["sieger_bot"]["name"], "S3")
        self.assertEqual([b["name"] for b in turnier["podest"]], ["S1", "S2", "S3"])
        # Halbfinale (2), Finale (1), Platz 3 (1)
        self.assertEqual(len(ersatz.aufrufe), 4)

    def test_platz_3_hat_einen_eigenen_seed(self):
        bots = [bot("S%d" % i) for i in range(1, 17)]
        with Ersatz(favorit, mit_namen=True) as ersatz:
            turnier = tournament.ko_turnier(self.config, bots, seed=5)
        seeds = [a["seed"] for a in ersatz.aufrufe]
        self.assertEqual(len(set(seeds)), len(seeds))
        self.assertEqual(turnier["spiel_um_platz_3"]["seed"], seeds[-1])

    def test_gleichstand_um_platz_3_entscheidet_die_setzung(self):
        bots = [bot("S%d" % i) for i in range(1, 5)]

        def antwort(nummer, namen):
            if set(namen) == {"S3", "S4"} and nummer >= 3:
                return ergebnis_bauen([50, 50], unentschieden=True)
            return favorit(nummer, namen)

        with Ersatz(antwort, mit_namen=True):
            turnier = tournament.ko_turnier(self.config, bots, seed=1)
        platz3 = turnier["spiel_um_platz_3"]
        self.assertEqual(platz3["entschieden_durch"], "Setzliste")
        self.assertEqual(platz3["sieger_bot"]["name"], "S3")

    def test_bei_drei_robotern_ist_der_halbfinalverlierer_dritter(self):
        with Ersatz(favorit, mit_namen=True) as ersatz:
            turnier = tournament.ko_turnier(
                self.config, [bot("S1"), bot("S2"), bot("S3")], seed=1)
        self.assertIsNone(turnier["spiel_um_platz_3"])
        self.assertEqual([b["name"] for b in turnier["podest"]], ["S1", "S2", "S3"])
        self.assertEqual(len(ersatz.aufrufe), 2)

    def test_zwei_roboter_haben_keinen_dritten(self):
        with Ersatz(favorit, mit_namen=True):
            turnier = tournament.ko_turnier(self.config, [bot("S1"), bot("S2")], seed=1)
        self.assertIsNone(turnier["spiel_um_platz_3"])
        self.assertEqual(turnier["podest"][0]["name"], "S1")
        self.assertEqual(turnier["podest"][1]["name"], "S2")
        self.assertIsNone(turnier["podest"][2])

    def test_upset_im_halbfinale(self):
        bots = [bot("S%d" % i) for i in range(1, 5)]

        def antwort(nummer, namen):
            if set(namen) == {"S1", "S4"}:
                return ergebnis_bauen([20, 100] if namen[0] == "S1" else [100, 20])
            return favorit(nummer, namen)

        with Ersatz(antwort, mit_namen=True):
            turnier = tournament.ko_turnier(self.config, bots, seed=1)
        self.assertEqual([b["name"] for b in turnier["podest"]], ["S2", "S4", "S1"])


# --------------------------------------------------------------------- Auslosung

class TestAuslosung(unittest.TestCase):
    def setUp(self):
        self.config = config()
        self.bots = [bot("T%02d" % i) for i in range(16)]

    def namen(self, reihe):
        return [b["name"] for b in reihe]

    def test_auslosung_ist_eine_mischung(self):
        gelost = tournament.auslosen(self.bots, 3)
        self.assertEqual(sorted(self.namen(gelost)), self.namen(self.bots))
        self.assertNotEqual(self.namen(gelost), self.namen(self.bots))

    def test_gleicher_seed_gleiche_auslosung_egal_in_welcher_reihenfolge(self):
        umgedreht = list(reversed(self.bots))
        self.assertEqual(self.namen(tournament.auslosen(self.bots, 9)),
                         self.namen(tournament.auslosen(umgedreht, 9)))

    def test_anderer_seed_andere_auslosung(self):
        ergebnisse = {tuple(self.namen(tournament.auslosen(self.bots, s))) for s in range(6)}
        self.assertGreater(len(ergebnisse), 1)

    def test_auslosung_ruehrt_die_eingabe_nicht_an(self):
        vorher = self.namen(self.bots)
        tournament.auslosen(self.bots, 4)
        self.assertEqual(self.namen(self.bots), vorher)

    def test_ausgeloste_setzliste_bestimmt_die_freilose(self):
        bots = self.bots[:14]
        with Ersatz(ergebnis_bauen([100, 20])):
            turnier = tournament.ko_turnier(self.config, bots, seed=11, losen=True)
        self.assertTrue(turnier["ausgelost"])
        setzliste = self.namen(turnier["setzliste"])
        self.assertEqual(setzliste, self.namen(tournament.auslosen(bots, 11)))
        freilose = [p["sieger_bot"]["name"] for p in turnier["runden"][0]["partien"]
                    if p["freilos"]]
        self.assertEqual(sorted(freilose), sorted(setzliste[:2]))

    def test_ohne_los_bleibt_die_reihenfolge(self):
        with Ersatz(ergebnis_bauen([100, 20])):
            turnier = tournament.ko_turnier(self.config, self.bots, seed=11)
        self.assertFalse(turnier["ausgelost"])
        self.assertEqual(self.namen(turnier["setzliste"]), self.namen(self.bots))


# --------------------------------------------------------------------- Gruppe

class TestGruppe(unittest.TestCase):
    def test_punkte_kommen_aus_der_config(self):
        cfg = config(**{"turnier.punkte_je_platz": [10, 5, 2, 0]})
        bots = [bot("A"), bot("B"), bot("C"), bot("D")]
        with Ersatz(ergebnis_bauen([400, 300, 200, 100])):
            gruppe = tournament.gruppe(cfg, bots, seed=1)
        # Über vier Runden kommt jeder Bot einmal auf jeden Platz: 10+5+2+0.
        self.assertEqual([e["punkte"] for e in gruppe["tabelle"]], [17, 17, 17, 17])
        self.assertEqual([e["siege"] for e in gruppe["tabelle"]], [1, 1, 1, 1])
        self.assertEqual(gruppe["platzierung"], [0, 1, 2, 3])

    def test_rotation_stellt_jeden_einmal_an_die_startposition(self):
        bots = [bot("A"), bot("B"), bot("C"), bot("D")]
        for nummer, eintrag in enumerate(bots):
            eintrag["pfad"] = "/pfade/%d.py" % nummer
        with Ersatz(ergebnis_bauen([400, 300, 200, 100])) as ersatz:
            gruppe = tournament.gruppe(config(), bots, seed=1)
        # Der jeweils erstgenannte Bot steht an Position 0 und gewinnt die Runde;
        # Namen und Pfade rotieren gemeinsam.
        self.assertEqual([a["namen"][0] for a in ersatz.aufrufe],
                         ["A", "B", "C", "D"])
        self.assertEqual([a["pfade"][0] for a in ersatz.aufrufe],
                         ["/pfade/0.py", "/pfade/1.py", "/pfade/2.py", "/pfade/3.py"])
        self.assertEqual([p["rotation"] for p in gruppe["partien"]], [0, 1, 2, 3])
        # Jeder startet genau einmal in jeder Ecke: ein Sieg, 3+2+1+0 Punkte,
        # 400+300+200+100 Spielpunkte — trotz rotierter Ergebnis-Reihenfolge.
        self.assertEqual([e["siege"] for e in gruppe["tabelle"]], [1, 1, 1, 1])
        self.assertEqual([e["punkte"] for e in gruppe["tabelle"]], [6, 6, 6, 6])
        self.assertEqual([e["gesamtpunkte"] for e in gruppe["tabelle"]],
                         [1000, 1000, 1000, 1000])

    def test_jede_runde_hat_ihren_eigenen_seed(self):
        bots = [bot("A"), bot("B"), bot("C"), bot("D")]
        with Ersatz(ergebnis_bauen([4, 3, 2, 1])) as ersatz:
            tournament.gruppe(bots=bots, config=config(), seed=1)
        seeds = [a["seed"] for a in ersatz.aufrufe]
        self.assertEqual(len(seeds), 4)
        self.assertEqual(len(set(seeds)), 4)

    def test_unentschieden_zaehlt_nicht_als_sieg(self):
        bots = [bot("A"), bot("B"), bot("C"), bot("D")]
        with Ersatz(ergebnis_bauen([4, 3, 2, 1], unentschieden=True)):
            gruppe = tournament.gruppe(config(), bots, seed=1)
        self.assertEqual([e["siege"] for e in gruppe["tabelle"]], [0, 0, 0, 0])

    def test_bei_gleichen_punkten_entscheiden_erst_siege_dann_spielpunkte(self):
        bots = [bot("A"), bot("B"), bot("C"), bot("D")]
        # Die Startplätze je Runde, unabhängig von der Rotation nach Namen verteilt.
        startplaetze = [
            {"A": 0, "B": 1, "C": 2, "D": 3},
            {"D": 0, "C": 1, "B": 2, "A": 3},
            {"A": 0, "B": 1, "D": 2, "C": 3},
            {"C": 0, "D": 1, "B": 2, "A": 3},
        ]
        werte = [900, 500, 200, 50]

        def antwort(nummer, namen):
            rang = startplaetze[nummer]
            faktor = 2 if nummer == 3 else 1
            return ergebnis_bauen([werte[rang[name]] * faktor for name in namen])

        with Ersatz(antwort, mit_namen=True):
            gruppe = tournament.gruppe(config(), bots, seed=1)

        tabelle = gruppe["tabelle"]
        namen = [tabelle[i]["name"] for i in gruppe["platzierung"]]
        # Alle vier haben gleich viele Tabellenpunkte (jeder Rang einmal: 6).
        self.assertEqual(namen, ["A", "C", "D", "B"])
        self.assertEqual([tabelle[i]["punkte"] for i in gruppe["platzierung"]],
                         [6, 6, 6, 6])
        # A steht wegen der Siege vorn, C und D trennen sich erst über die Spielpunkte.
        self.assertEqual([tabelle[i]["siege"] for i in gruppe["platzierung"]],
                         [2, 1, 1, 0])
        self.assertGreater(tabelle[2]["gesamtpunkte"], tabelle[3]["gesamtpunkte"])

    def test_dauerhafter_gleichstand_wird_gekennzeichnet(self):
        cfg = config(**{"turnier.gleichstand_wiederholungen": 2})
        bots = [bot("A"), bot("B"), bot("C"), bot("D")]
        with Ersatz(ergebnis_bauen([4, 3, 2, 1], unentschieden=True)) as ersatz:
            erste = tournament.gruppe(cfg, bots, seed=1)
            zweite = tournament.gruppe(cfg, bots, seed=1)
        self.assertEqual(len(ersatz.aufrufe), 24)        # 4 Runden zu je 3 Versuchen
        self.assertTrue(all(p["ergebnis"]["entschieden_durch"] == "Gleichstand"
                            for p in erste["partien"]))
        self.assertEqual([e["unentschieden"] for e in erste["tabelle"]], [4, 4, 4, 4])
        self.assertEqual([e["spiele"] for e in erste["tabelle"]], [4, 4, 4, 4])
        self.assertEqual([e["siege"] for e in erste["tabelle"]], [0, 0, 0, 0])
        # Ein dauerhafter Gleichstand vergibt keine Tabellenpunkte.
        self.assertEqual([e["punkte"] for e in erste["tabelle"]], [0, 0, 0, 0])
        self.assertEqual([p["seed"] for p in erste["partien"]],
                         [tournament.partie_seed(1, 0, r) for r in range(4)])
        self.assertEqual([a["seed"] for a in ersatz.aufrufe[:3]],
                         [tournament.partie_seed(1, 0, 0) + v for v in range(3)])
        self.assertEqual(erste["tabelle"], zweite["tabelle"])
        self.assertEqual(erste["platzierung"], zweite["platzierung"])

    def test_gruppenseeds_trennen_sich_vom_ko(self):
        bots = [bot("A"), bot("B"), bot("C"), bot("D")]
        with Ersatz(ergebnis_bauen([4, 3, 2, 1])) as gruppe_aufrufe:
            tournament.gruppe(config(), bots, seed=7)
        with Ersatz(ergebnis_bauen([100, 20])) as ko_aufrufe:
            tournament.ko_turnier(config(), bots, seed=7)
        gruppe_seeds = {a["seed"] for a in gruppe_aufrufe.aufrufe}
        ko_seeds = {a["seed"] for a in ko_aufrufe.aufrufe}
        self.assertEqual(gruppe_seeds,
                         {tournament.partie_seed(7, 0, r) for r in range(4)})
        self.assertFalse(gruppe_seeds & ko_seeds)

    def test_echte_gruppe_laeuft_durch(self):
        """Einmal ohne Ersatz — vier Prozesse, kurze Runden."""
        cfg = config(**{"spiel.runden_laenge": 20})
        bots = [spielleiter.bot_beschreibung(
            os.path.join(spielleiter.BOT_ORDNER, name))
            for name in ("fleissig.py", "hausmeister.py", "lauerer.py", "rumpelstilzchen.py")]
        gruppe = tournament.gruppe(cfg, bots, seed=1, ticks=20)
        self.assertEqual(len(gruppe["partien"]), 4)
        self.assertEqual(sorted(gruppe["platzierung"]), [0, 1, 2, 3])
        self.assertEqual(sum(e["spiele"] for e in gruppe["tabelle"]), 16)


# --------------------------------------------------------------------- Archiv

class TestArchiv(unittest.TestCase):
    def setUp(self):
        self.ordner = tempfile.mkdtemp(prefix="turnier_test_")
        self.echt = tournament.TURNIER_ORDNER
        tournament.TURNIER_ORDNER = self.ordner

    def tearDown(self):
        tournament.TURNIER_ORDNER = self.echt
        shutil.rmtree(self.ordner, ignore_errors=True)

    def test_zeit_aus_dem_dateinamen(self):
        self.assertEqual(tournament.zeit_aus_name("20260907_232551_ko.json"),
                         "07.09.2026, 23:25 Uhr")
        self.assertEqual(tournament.zeit_aus_name("handgeschrieben.json"), "")
        self.assertEqual(tournament.zeit_aus_name("abcdefgh_ijklmn_ko.json"), "")

    def test_speichern_und_wieder_laden(self):
        daten = {"art": "ko", "runden": [], "sieger": {"name": "A"}}
        pfad = tournament.speichern(daten, "ko")
        self.assertTrue(os.path.isfile(pfad))
        self.assertEqual(tournament.laden(os.path.basename(pfad)), daten)

    def test_gleiche_sekunde_kollidiert_nicht(self):
        from unittest import mock
        daten = {"art": "ko", "runden": [], "sieger": {"name": "A"}}
        with mock.patch.object(tournament.time, "strftime",
                               return_value="20260101_120000"):
            pfade = [tournament.speichern(dict(daten), "ko") for _ in range(3)]
        self.assertEqual(len(set(pfade)), 3)
        for pfad in pfade:
            self.assertTrue(pfad.endswith(".json"))
            self.assertEqual(tournament.laden(os.path.basename(pfad)), daten)
        self.assertEqual(tournament.zeit_aus_name(os.path.basename(pfade[0])),
                         "01.01.2026, 12:00 Uhr")

    def test_laden_bleibt_im_turnierordner(self):
        with self.assertRaises(OSError):
            tournament.laden("../config.json")

    def test_kurzfassung_eines_ko_turniers(self):
        daten = {
            "art": "ko", "seed": 1, "sieger": {"name": "A"},
            "runden": [
                {"nummer": 1, "name": "Halbfinale", "partien": [
                    {"a": {"name": "A"}, "b": {"name": "D"}, "freilos": False},
                    {"a": {"name": "B"}, "b": None, "freilos": True,
                     "sieger_bot": {"name": "B"}}]},
                {"nummer": 2, "name": "Finale", "partien": [
                    {"a": {"name": "A"}, "b": {"name": "B"}, "freilos": False}]},
            ],
        }
        pfad = tournament.speichern(daten, "ko")
        kurz = tournament.kurzfassung(pfad)
        self.assertTrue(kurz["lesbar"])
        self.assertEqual(kurz["art"], "ko")
        self.assertEqual(kurz["sieger"], "A")
        self.assertEqual(kurz["runden"], 2)
        self.assertEqual(kurz["teilnehmer"], ["A", "D", "B"])
        self.assertNotIn("podest", kurz)        # alte Dateien kennen kein Podest

    def test_kurzfassung_nennt_das_podest(self):
        daten = {"art": "ko", "seed": 1, "sieger": {"name": "A"}, "runden": [],
                 "podest": [{"name": "A"}, {"name": "B"}, None]}
        kurz = tournament.kurzfassung(tournament.speichern(daten, "ko"))
        self.assertEqual(kurz["podest"], ["A", "B", ""])

    def test_kurzfassung_einer_gruppe(self):
        daten = {"art": "gruppe", "seed": 1, "partien": [{}, {}],
                 "platzierung": [2, 0, 1],
                 "tabelle": [{"name": "A"}, {"name": "B"}, {"name": "C"}]}
        pfad = tournament.speichern(daten, "gruppe")
        kurz = tournament.kurzfassung(pfad)
        self.assertEqual(kurz["sieger"], "C")
        self.assertEqual(kurz["teilnehmer"], ["A", "B", "C"])
        self.assertEqual(kurz["runden"], 2)

    def test_kaputte_datei_wird_gemeldet_statt_zu_stuerzen(self):
        pfad = os.path.join(self.ordner, "20260101_000000_ko.json")
        with open(pfad, "w", encoding="utf-8") as datei:
            datei.write("{kein json")
        kurz = tournament.kurzfassung(pfad)
        self.assertFalse(kurz["lesbar"])
        self.assertEqual(kurz["zeit"], "01.01.2026, 00:00 Uhr")

    def test_kaputte_gruppentabelle_stuerzt_nicht(self):
        daten = {"art": "gruppe", "partien": [],
                 "platzierung": [7], "tabelle": ["kaputt"]}
        pfad = tournament.speichern(daten, "gruppe")
        kurz = tournament.kurzfassung(pfad)
        self.assertTrue(kurz["lesbar"])
        self.assertEqual(kurz["sieger"], "")
        self.assertEqual(kurz["teilnehmer"], [])

    def test_gespeicherte_liefert_das_neueste_zuerst(self):
        for name, art in (("20260101_120000_ko.json", "ko"),
                          ("20260301_120000_gruppe.json", "gruppe"),
                          ("20260201_120000_ko.json", "ko")):
            with open(os.path.join(self.ordner, name), "w", encoding="utf-8") as datei:
                json.dump({"art": art, "runden": [], "tabelle": [], "platzierung": [],
                           "partien": []}, datei)
        liste = tournament.gespeicherte()
        self.assertEqual([e["datei"] for e in liste],
                         ["20260301_120000_gruppe.json",
                          "20260201_120000_ko.json",
                          "20260101_120000_ko.json"])
        self.assertTrue(all(e["zeit"] for e in liste))

    def test_leerer_ordner_ist_kein_fehler(self):
        tournament.TURNIER_ORDNER = os.path.join(self.ordner, "gibtsnicht")
        self.assertEqual(tournament.gespeicherte(), [])


if __name__ == "__main__":
    unittest.main()
