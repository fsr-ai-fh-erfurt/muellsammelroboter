"""Parser, Fehlermeldungen und die erzeugte Abgabedatei."""

import contextlib
import io
import os
import re
import unittest

from language import compiler
from language.compiler import aus_python_lesen, uebersetzen
from language.errors import RegelFehler
from language.parser import zerlegen, zerlegen_programm

BEISPIEL = """IF ladung_ist_voll THEN fahre_zu depot
IF akku < 30 THEN fahre_zu depot
IF gegner_sichtbar AND gegner_ladung >= 4 THEN ramme gegner
IF muell_in_zone THEN fahre_zu naechster_muell(in_zone)
ELSE fahre_zu naechster_muell"""

AUTOMAT = """LET grenze = 30

STATE sammeln
  IF ladung_ist_voll THEN GOTO heimweg
  ELSE fahre_zu naechster_muell

STATE heimweg
  IF abstand_zu depot == 0 THEN GOTO sammeln
  IF akku < grenze THEN fahre_zu depot
  ELSE fahre_zu depot"""

KOSTEN = {"bewegung": 1, "rammen": 5}


def meldungen(quelltext):
    return [f.vollstaendig() for f in zerlegen_programm(quelltext).fehler]


def hinweise(quelltext):
    return [h.text for h in zerlegen_programm(quelltext).hinweise]


class TestParser(unittest.TestCase):
    def test_beispiel_programm(self):
        programm = zerlegen_programm(BEISPIEL)
        self.assertTrue(programm.gueltig, programm.fehler)
        self.assertEqual(len(programm.regeln), 5)
        self.assertEqual(programm.regeln[-1].art, "else")

    def test_grossschreibung_und_leerzeichen_egal(self):
        programm = zerlegen_programm("   if    AKKU   <   30    fahre_zu    DEPOT   ")
        self.assertTrue(programm.gueltig, programm.fehler)
        self.assertEqual(len(programm.regeln), 1)

    def test_then_ist_optional(self):
        self.assertTrue(zerlegen_programm("IF akku < 30 fahre_zu depot").gueltig)

    def test_else_if_ist_eine_kette(self):
        programm = zerlegen_programm(
            "IF akku < 30 THEN fahre_zu depot\n"
            "ELSE IF ladung_ist_voll THEN fahre_zu depot\n"
            "ELSE warte")
        self.assertTrue(programm.gueltig, programm.fehler)
        self.assertEqual([r.art for r in programm.regeln], ["if", "if", "else"])

    def test_umlaute_sind_egal(self):
        for text in ("ELSE fahre_zu naechster_muell",
                     "ELSE fahre_zu nächster_müll",
                     "ELSE fahre_zu naechster_müll"):
            self.assertTrue(zerlegen_programm(text).gueltig, text)

    def test_kommentare_werden_ignoriert(self):
        programm = zerlegen_programm("# nur ein Kommentar\nELSE warte")
        self.assertTrue(programm.gueltig)
        self.assertEqual(len(programm.regeln), 1)

    def test_klammern_und_verknuepfungen(self):
        programm = zerlegen_programm(
            "IF (akku < 30 OR ladung_ist_voll) AND NOT bin_in_zone THEN fahre_zu depot")
        self.assertTrue(programm.gueltig, programm.fehler)

    def test_alle_ziele_aus_der_spec(self):
        for ziel in ("depot", "gegner", "zone", "naechster_muell",
                     "naechster_muell(metall)", "naechster_muell(in_zone)",
                     "naechster_muell(metall, in_zone)", "naechster_muell in_zone",
                     "weg_von gegner", "weg_von(gegner)", "feld(12, 8)",
                     "BEST muell BY wert - abstand"):
            programm = zerlegen_programm("ELSE fahre_zu " + ziel)
            self.assertTrue(programm.gueltig, "%s: %s" % (ziel, programm.fehler))

    def test_alle_bedingungen_aus_der_spec(self):
        for bedingung in ("ladung > 2", "ladung_ist_voll", "ladung_ist_leer", "akku < 30",
                          "gegner_sichtbar", "gegner_ladung >= 4", "abstand_zu depot < 5",
                          "tick > 350", "punkte < 100", "bin_in_zone", "muell_in_zone",
                          "habe(elektro)", "anzahl(papier) == 2", "restliche_ticks < 25",
                          "ladung_wert > 100", "freie_plaetze != 0", "RANDOM(30)"):
            programm = zerlegen_programm("IF %s THEN warte" % bedingung)
            self.assertTrue(programm.gueltig, "%s: %s" % (bedingung, programm.fehler))

    def test_alle_aktionen_aus_der_spec(self):
        for aktion in ("fahre_zu depot", "fahre rechts", "ramme gegner", "warte", "presse"):
            programm = zerlegen_programm("ELSE " + aktion)
            self.assertTrue(programm.gueltig, "%s: %s" % (aktion, programm.fehler))

    def test_presse_und_kann_pressen_werden_uebersetzt(self):
        quelle = uebersetzen("IF kann_pressen THEN presse\nELSE warte", "T")["quelle"]
        self.assertIn("zustand.kann_pressen", quelle)
        self.assertIn('"presse"', quelle)

    def test_ballen_ist_eine_sorte(self):
        for bedingung in ("anzahl(ballen) > 0", "habe(ballen)"):
            programm = zerlegen_programm("IF %s THEN warte" % bedingung)
            self.assertTrue(programm.gueltig, "%s: %s" % (bedingung, programm.fehler))

    def test_nbsp_und_vertikaltab_zwischen_woertern(self):
        """Aus dem Browser eingefügte Leerzeichen dürfen keine Regel zerstören."""
        def kern(text):
            return [(t.art, t.wert) for t in zerlegen(text, 1)]

        muster = kern("IF akku < 30 THEN fahre_zu depot")
        for trenner in ("\u00a0", "\v", "\f", "\t"):
            text = "IF%sakku%s<%s30%sTHEN%sfahre_zu%sdepot" % ((trenner,) * 6)
            self.assertEqual(kern(text), muster, repr(trenner))

    def test_nullbreites_zeichen_wird_gemeldet(self):
        fehler = zerlegen_programm("IF akku\u200b < 30 THEN warte").fehler
        self.assertEqual(len(fehler), 1)
        self.assertEqual(fehler[0].zeile, 1)
        self.assertIsNotNone(fehler[0].spalte)
        self.assertIn("gehört nicht in eine Regel", fehler[0].text)

    def test_zu_grosse_zahl_wird_gemeldet(self):
        text = meldungen("IF akku < " + "9" * 30 + " THEN warte")[0]
        self.assertIn("zu groß", text)

    def test_zu_tiefe_klammern_werden_gemeldet(self):
        quelltext = "IF " + "(" * 250 + "akku" + ")" * 250 + " THEN warte"
        programm = zerlegen_programm(quelltext)
        self.assertFalse(programm.gueltig)
        self.assertTrue(any("verschachtelt" in f.text for f in programm.fehler))


class TestRechnen(unittest.TestCase):
    def test_zwei_werte_vergleichen(self):
        programm = zerlegen_programm("IF akku < abstand_zu depot * 2 + 10 THEN fahre_zu depot")
        self.assertTrue(programm.gueltig, programm.fehler)

    def test_punkt_vor_strich(self):
        quelle = uebersetzen("IF 2 + 3 * 4 > akku THEN warte\nELSE warte", "T")["quelle"]
        self.assertIn("2 + 3 * 4 > zustand.akku", quelle)

    def test_klammern_bleiben_erhalten(self):
        quelle = uebersetzen("IF (2 + 3) * 4 > akku THEN warte\nELSE warte", "T")["quelle"]
        self.assertIn("(2 + 3) * 4", quelle)

    def test_teilen_faengt_die_null_ab(self):
        quelle = uebersetzen("IF 100 / ladung > 20 THEN warte\nELSE warte", "T")["quelle"]
        self.assertIn("def teile(a, b):", quelle)
        self.assertIn("teile(100, zustand.ladung)", quelle)

    def test_durch_null_teilen_ist_ein_fehler(self):
        self.assertIn("Durch 0", meldungen("IF akku / 0 > 1 THEN warte")[0])

    def test_rest_faengt_die_null_ab(self):
        quelle = uebersetzen("IF 100 % ladung > 20 THEN warte\nELSE warte", "T")["quelle"]
        self.assertIn("def rest(a, b):", quelle)
        self.assertIn("rest(100, zustand.ladung)", quelle)

    def test_rest_durch_null_ist_ein_fehler(self):
        self.assertIn("Durch 0", meldungen("IF akku % 0 > 1 THEN warte")[0])

    def test_konstanten(self):
        programm = zerlegen_programm("LET grenze = 30\nIF akku < grenze THEN warte\nELSE warte")
        self.assertTrue(programm.gueltig, programm.fehler)
        self.assertEqual(programm.konstanten[0].name, "grenze")
        quelle = uebersetzen("LET grenze = 30\nIF akku < grenze THEN warte\nELSE warte",
                             "T")["quelle"]
        self.assertIn("GRENZE = 30", quelle)
        self.assertIn("zustand.akku < GRENZE", quelle)

    def test_konstante_darf_nicht_wie_ein_befehl_heissen(self):
        self.assertIn("schon ein Befehl", meldungen("LET akku = 30")[0])

    def test_konstante_darf_keinen_spielwert_enthalten(self):
        text = meldungen("LET schwelle = akku - 10\nELSE warte")[0]
        self.assertIn("LET", text)
        self.assertIn("erst im Spiel", text)

    def test_konstante_mit_teilen_steht_hinter_der_hilfe(self):
        ergebnis = uebersetzen("LET half = 7 / 2\nIF akku < half THEN warte\nELSE warte",
                               "T")
        self.assertTrue(ergebnis["gueltig"], ergebnis["fehler"])
        quelle = ergebnis["quelle"]
        # `HALF = teile(7, 2)` läuft beim Laden der Datei — `def teile` muss vorher da sein.
        self.assertLess(quelle.index("def teile"), quelle.index("HALF ="))
        exec(compile(quelle, "<test>", "exec"), {})

    def test_konstante_darf_name_nicht_ueberschreiben(self):
        for name in ("name", "beschreibung", "pseudocode"):
            text = meldungen("LET %s = 5" % name)[0]
            self.assertIn("Werkstatt selbst", text)

    def test_random_wird_zu_zufall(self):
        quelle = uebersetzen("IF RANDOM(30) THEN fahre oben\nELSE warte", "T")["quelle"]
        self.assertIn("zustand.zufall_zahl(100) < 30", quelle)

    def test_random_und_feld_nehmen_keine_konstanten(self):
        """So steht es in der Anleitung: `RANDOM(...)` und `feld(...)` brauchen feste Zahlen."""
        for quelle in ("LET grenze = 30\nIF RANDOM(grenze) THEN warte",
                       "LET zahl = 3\nELSE fahre_zu feld(zahl, 2)"):
            self.assertFalse(zerlegen_programm(quelle).gueltig, quelle)

    def test_bestes_stueck_bekommt_eine_formel(self):
        quelle = uebersetzen("ELSE fahre_zu BEST muell BY wert * bonus - 3 * abstand",
                             "T")["quelle"]
        self.assertIn("lambda wert, abstand, bonus: wert * bonus - 3 * abstand", quelle)
        self.assertIn("_bestes_stueck", quelle)

    def test_formelwoerter_nur_hinter_by(self):
        self.assertIn("nur in der Rechnung", meldungen("IF wert > 3 THEN warte")[0])


class TestModi(unittest.TestCase):
    def test_automat_wird_erkannt(self):
        programm = zerlegen_programm(AUTOMAT)
        self.assertTrue(programm.gueltig, programm.fehler)
        self.assertEqual(programm.modus_namen(), ["sammeln", "heimweg"])
        self.assertEqual(len(programm.regeln), 5)
        self.assertEqual(programm.regeln[0].modus, "sammeln")

    def test_erzeugter_automat(self):
        quelle = uebersetzen(AUTOMAT, "Team Automat", "", KOSTEN)["quelle"]
        self.assertIn('START_MODUS = "sammeln"', quelle)
        self.assertIn("def _modus_sammeln(self, zustand):", quelle)
        self.assertIn("def _modus_heimweg(self, zustand):", quelle)
        self.assertIn('self.modus = "heimweg"', quelle)
        compile(quelle, "<test>", "exec")

    def test_automat_laeuft_wirklich(self):
        """Der erzeugte Automat muss wechseln, ohne einen Zug zu verlieren."""
        quelle = uebersetzen(AUTOMAT, "Team Automat", "", KOSTEN)["quelle"]
        raum = {}
        exec(compile(quelle, "<test>", "exec"), raum)
        roboter = raum["Roboter"]()

        class Zustand:
            max_wechsel = 8
            ladung_ist_voll = True
            akku = 100

            def __init__(self):
                self.regeln = []

            def regel(self, nummer):
                self.regeln.append(nummer)

            def abstand_zu_depot(self):
                return 4

            def fahre_zu_depot(self):
                return "oben"

        zustand = Zustand()
        self.assertEqual(roboter.modus, "sammeln")
        # Voll: GOTO heimweg und im selben Zug weiter — es wird gefahren, nicht gewartet.
        self.assertEqual(roboter.entscheide(zustand), "oben")
        self.assertEqual(roboter.modus, "heimweg")
        self.assertEqual(zustand.regeln[0], 1)

    def test_kreis_wird_abgefangen(self):
        quelle = uebersetzen("STATE a\n  ELSE GOTO b\nSTATE b\n  ELSE GOTO a", "T")["quelle"]
        raum = {}
        exec(compile(quelle, "<test>", "exec"), raum)

        class Zustand:
            max_wechsel = 8

            def regel(self, nummer):
                pass

        # Der erzeugte Bot schreibt dabei eine Warnung auf die Konsole.
        with contextlib.redirect_stdout(io.StringIO()) as ausgabe:
            self.assertEqual(raum["Roboter"]().entscheide(Zustand()), "warte")
        self.assertIn("im Kreis", ausgabe.getvalue())

    def test_goto_in_den_eigenen_modus_verbrennt_keinen_zug(self):
        """Die Regel wird übersprungen, statt den Modus auf sich selbst zu setzen.

        `IF ladung_ist_voll THEN GOTO heimweg` vor dem ersten `STATE` gilt in jedem
        Modus — auch in `heimweg` selbst. Ohne die Prüfung hätte sie sich dort in
        jedem Zug erneut ausgelöst, bis `MAX_WECHSEL` erreicht war, und der Zug wäre
        als `warte` verloren gewesen.
        """
        quelltext = ("IF ladung_ist_voll THEN GOTO heimweg\n\n"
                     "STATE sammeln\n  ELSE fahre_zu naechster_muell\n\n"
                     "STATE heimweg\n  IF ladung_ist_leer THEN GOTO sammeln\n"
                     "  ELSE fahre_zu depot")
        quelle = uebersetzen(quelltext, "T", "", KOSTEN)["quelle"]
        raum = {}
        exec(compile(quelle, "<test>", "exec"), raum)
        roboter = raum["Roboter"]()

        class Zustand:
            max_wechsel = 8
            ladung_ist_voll = True
            ladung_ist_leer = False

            def regel(self, nummer):
                pass

            def fahre_zu_depot(self):
                return "oben"

        zustand = Zustand()
        with contextlib.redirect_stdout(io.StringIO()) as ausgabe:
            # Erster Zug: Wechsel nach heimweg, im selben Zug weiterfahren.
            self.assertEqual(roboter.entscheide(zustand), "oben")
            self.assertEqual(roboter.modus, "heimweg")
            # Zweiter Zug: dieselbe Regel greift wieder, aber er ist schon da.
            self.assertEqual(roboter.entscheide(zustand), "oben")
            self.assertEqual(roboter.modus, "heimweg")
        self.assertEqual(ausgabe.getvalue(), "")

    def test_else_goto_in_den_eigenen_modus_wartet_ohne_warnung(self):
        """Es bleibt nichts zu tun — aber ohne acht Leerläufe und ohne Kreis-Meldung."""
        quelltext = ("STATE sammeln\n  IF akku < 5 THEN warte\n  ELSE GOTO sammeln\n\n"
                     "STATE heimweg\n  ELSE fahre_zu depot")
        quelle = uebersetzen(quelltext, "T", "", KOSTEN)["quelle"]
        raum = {}
        exec(compile(quelle, "<test>", "exec"), raum)

        class Zustand:
            max_wechsel = 8
            akku = 100

            def regel(self, nummer):
                pass

        with contextlib.redirect_stdout(io.StringIO()) as ausgabe:
            self.assertEqual(raum["Roboter"]().entscheide(Zustand()), "warte")
        self.assertEqual(ausgabe.getvalue(), "")

    def test_goto_auf_einen_anderen_modus_bleibt_ohne_pruefung(self):
        """Innerhalb eines Modus wäre die Prüfung immer wahr — sie gehört nicht ins Blatt."""
        quelle = uebersetzen(AUTOMAT, "T", "", KOSTEN)["quelle"]
        self.assertIn('self.modus = "heimweg"', quelle)
        self.assertNotIn('self.modus != "heimweg"', quelle)

    def test_oder_vor_dem_goto_wird_geklammert(self):
        """`a OR b` muss geklammert werden, sonst bindet das `and` der Prüfung falsch."""
        quelltext = ("IF ladung_ist_voll OR akku < 10 THEN GOTO heimweg\n\n"
                     "STATE sammeln\n  ELSE fahre_zu naechster_muell\n\n"
                     "STATE heimweg\n  ELSE fahre_zu depot")
        quelle = uebersetzen(quelltext, "T", "", KOSTEN)["quelle"]
        self.assertIn('if (zustand.ladung_ist_voll or zustand.akku < 10) '
                      'and self.modus != "heimweg":', quelle)

    def test_unbekannter_modus(self):
        text = meldungen("STATE a\n  ELSE GOTO b")[0]
        self.assertIn("gibt es nicht", text)

    def test_goto_ohne_state(self):
        self.assertIn("noch keinen", meldungen("ELSE GOTO heimweg")[0])

    def test_doppelter_modusname(self):
        self.assertIn("schon weiter oben", meldungen("STATE a\n ELSE warte\nSTATE a\n ELSE warte")[0])

    def test_modusnamen_kollidieren_nicht_mit_der_weiterleitung(self):
        """`STATE schritt` und `STATE weiterleiten` dürfen den Automaten nicht ersetzen."""
        quelltext = ("STATE schritt\n"
                     "  IF tick > 0 THEN GOTO weiterleiten\n"
                     "  ELSE warte\n\n"
                     "STATE weiterleiten\n"
                     "  ELSE fahre_zu depot")
        quelle = uebersetzen(quelltext, "T", "", KOSTEN)["quelle"]
        self.assertIn("def _weiterleiten(self, zustand):", quelle)
        self.assertIn("def _modus_schritt(self, zustand):", quelle)
        self.assertIn("def _modus_weiterleiten(self, zustand):", quelle)

        raum = {}
        exec(compile(quelle, "<test>", "exec"), raum)
        roboter = raum["Roboter"]()

        class Zustand:
            max_wechsel = 8
            tick = 1

            def regel(self, nummer):
                pass

            def fahre_zu_depot(self):
                return "links"

        self.assertEqual(roboter.entscheide(Zustand()), "links")
        self.assertEqual(roboter.modus, "weiterleiten")

    def test_regeln_vor_dem_ersten_state_gelten_immer(self):
        programm = zerlegen_programm(
            "IF akku < 5 THEN GOTO notfall\nSTATE sammeln\n ELSE warte\nSTATE notfall\n ELSE warte")
        self.assertTrue(programm.gueltig, programm.fehler)
        self.assertIsNone(programm.regeln[0].modus)
        self.assertTrue(any("in jedem Modus" in h for h in
                            [h.text for h in programm.hinweise]))

    def test_else_vor_dem_ersten_state_ist_ein_fehler(self):
        text = meldungen("ELSE warte\nSTATE sammeln\n  ELSE warte")[0]
        self.assertIn("überstimmen", text)

    def test_modus_ohne_eingang_wird_angemerkt(self):
        self.assertTrue(any("nie betreten" in h for h in
                            hinweise("STATE a\n ELSE warte\nSTATE b\n ELSE warte")))



class TestFolgen(unittest.TestCase):
    """`fahre links, oben, GOTO b` — mehrere Aktionen, eine je Tick."""

    QUELLE = ("IF akku < 5 THEN GOTO a\n"
              "STATE a\n"
              "  IF 1 == 1 THEN fahre links, links, warte, oben, GOTO b\n"
              "STATE b\n"
              "  ELSE fahre rechts")

    class Zustand:
        max_wechsel = 8
        akku = 100

        def __init__(self):
            self.regeln = []

        def regel(self, nummer):
            self.regeln.append(nummer)

        def fahre(self, richtung):
            return richtung

    def roboter(self, quelltext):
        ergebnis = uebersetzen(quelltext, "T", "", KOSTEN)
        self.assertTrue(ergebnis["gueltig"], ergebnis["fehler"])
        raum = {}
        exec(compile(ergebnis["quelle"], "<test>", "exec"), raum)
        return raum["Roboter"]()

    def test_ein_schritt_je_tick(self):
        roboter = self.roboter(self.QUELLE)
        zuege = [roboter.entscheide(self.Zustand()) for _ in range(6)]
        self.assertEqual(zuege, ["links", "links", "warte", "oben", "rechts", "rechts"])
        self.assertEqual(roboter.modus, "b")

    def test_ohne_goto_zurueck_in_den_eigenen_modus(self):
        roboter = self.roboter("STATE a\n  ELSE fahre links, oben")
        zuege = [roboter.entscheide(self.Zustand()) for _ in range(4)]
        self.assertEqual(zuege, ["links", "oben", "links", "oben"])

    def test_globales_goto_stoesst_die_folge_nicht_neu_an(self):
        """`GOTO a` vor dem ersten STATE darf eine laufende Folge in `a` nicht abbrechen."""
        roboter = self.roboter(self.QUELLE)
        zustand = self.Zustand()
        zustand.akku = 1
        zuege = [roboter.entscheide(zustand) for _ in range(4)]
        self.assertEqual(zuege, ["links", "links", "warte", "oben"])

    def test_versteckte_modi_bleiben_unsichtbar(self):
        ergebnis = uebersetzen(self.QUELLE, "T", "", KOSTEN)
        self.assertEqual([m["name"] for m in ergebnis["modi"]], ["a", "b"])
        sichtbar = [r for r in ergebnis["regeln"] if "Schritt" not in r["quelle"]]
        self.assertEqual([r["nummer"] for r in sichtbar], [1, 2, 3])
        schritte = [r for r in ergebnis["regeln"] if "Schritt" in r["quelle"]]
        self.assertEqual({r["modus"] for r in schritte}, {"a"})
        self.assertEqual({r["zeile"] for r in schritte}, {3})

    def test_fehler(self):
        faelle = {
            "IF 1 == 1 THEN fahre links, oben\nSTATE a\n  ELSE warte": "innerhalb eines `STATE`",
            "STATE a\n  ELSE fahre links, GOTO a, oben": "nur ganz am Ende",
            "STATE a\n  ELSE fahre links,": "fehlt noch eine Aktion",
            "STATE a\n  ELSE fahre links, GOTO sammlen\nSTATE sammeln\n  ELSE warte":
                "sammeln",
            "STATE a\n  ELSE fahre links, oben\nSTATE folge_z2_schritt1\n  ELSE warte":
                "braucht schon die Folge",
        }
        for quelltext, teil in faelle.items():
            with self.subTest(quelltext=quelltext):
                self.assertIn(teil, " ".join(meldungen(quelltext)))

    def test_richtung_allein_bleibt_ein_fehler(self):
        self.assertTrue(meldungen("STATE a\n  ELSE links"))

    def test_erklaerung_sagt_was_passiert(self):
        ergebnis = uebersetzen(self.QUELLE, "T", "", KOSTEN)
        erklaerung, = ergebnis["erklaerungen"]
        self.assertEqual(erklaerung["zeile"], 3)
        self.assertIn("4 Zügen", erklaerung["titel"])
        self.assertIn("`1 == 1`", erklaerung["text"])
        self.assertIn("① nach links", erklaerung["text"])
        self.assertIn("③ warten", erklaerung["text"])
        self.assertIn("in den Modus `b`", erklaerung["text"])
        # Vor dem ersten STATE steht eine Regel — dann gehört der Satz dazu.
        self.assertIn("vor dem ersten `STATE`", erklaerung["text"])

    def test_erklaerung_ohne_goto_warnt_vor_dem_neubeginn(self):
        text = uebersetzen("STATE a\n  IF akku > 5 THEN oben, links", "T")["erklaerungen"][0]["text"]
        self.assertIn("wieder in Modus `a`", text)
        self.assertIn("von vorn", text)
        self.assertNotIn("vor dem ersten", text)

    def test_hinweise_beim_schreiben(self):
        self.assertTrue(any("rückgängig" in h for h in hinweise("STATE a\n  ELSE links, rechts")))
        self.assertTrue(any("wieder da" in h for h in
                            hinweise("STATE a\n  ELSE oben, links, unten, rechts")))
        self.assertTrue(any("ist lang" in h for h in
                            hinweise("STATE a\n  ELSE oben, oben, oben, oben, oben, oben")))
        self.assertFalse(any("rückgängig" in h or "wieder da" in h for h in
                             hinweise("STATE a\n  ELSE oben, oben, links")))

    def test_kosten_der_folge_nennen_die_zuege(self):
        ergebnis = uebersetzen(self.QUELLE, "T", "", KOSTEN)
        start = [r for r in ergebnis["regeln"] if r["nummer"] == 2][0]
        self.assertIn("4 Züge", start["kosten"])
        self.assertIn("`b`", start["kosten"])
        self.assertNotIn("folge_z", start["kosten"])

    def test_formel_und_klammern_in_einer_folge(self):
        ergebnis = uebersetzen(
            "LET umweg = 3\nSTATE a\n  ELSE fahre_zu BEST muell BY wert * bonus - umweg * "
            "abstand, fahre_zu naechster_muell(metall, in_zone), oben", "T")
        self.assertTrue(ergebnis["gueltig"], ergebnis["fehler"])
        schritte = [r for r in ergebnis["regeln"] if r["folge"]]
        self.assertEqual([r["folge"]["schritt"] for r in schritte], [1, 2, 3])
        self.assertEqual([r["folge"]["richtung"] for r in schritte], [None, None, "oben"])

class TestKosten(unittest.TestCase):
    def test_fahrt_nennt_den_abstand(self):
        programm = zerlegen_programm("ELSE fahre_zu depot")
        kosten = programm.als_dict(KOSTEN)["regeln"][0]["kosten"]
        self.assertIn("je Schritt", kosten)
        self.assertIn("abstand_zu depot", kosten)

    def test_rammen_nennt_beide_posten(self):
        kosten = zerlegen_programm("ELSE ramme gegner").als_dict(KOSTEN)["regeln"][0]["kosten"]
        self.assertIn("5 Akku", kosten)
        self.assertIn("1 Akku", kosten)

    def test_warten_kostet_keinen_akku(self):
        kosten = zerlegen_programm("ELSE warte").als_dict(KOSTEN)["regeln"][0]["kosten"]
        self.assertIn("kein Akku", kosten)

    def test_moduswechsel_kostet_keinen_zug(self):
        programm = zerlegen_programm("STATE a\n  ELSE GOTO b\nSTATE b\n  ELSE warte")
        self.assertIn("0 Züge", programm.als_dict(KOSTEN)["regeln"][0]["kosten"])

    def test_kosten_stehen_in_der_abgabedatei(self):
        quelle = uebersetzen("ELSE fahre_zu depot", "T", "", KOSTEN)["quelle"]
        self.assertIn("# Kosten:", quelle)
        self.assertIn("abstand_zu depot", quelle)

    def test_ohne_config_bleibt_die_angabe_ohne_zahlen(self):
        kosten = zerlegen_programm("ELSE fahre_zu depot").als_dict()["regeln"][0]["kosten"]
        self.assertIn("Akku", kosten)
        self.assertNotIn("1 Akku", kosten)

    def test_presse_kosten_nennen_die_zahlen_aus_der_config(self):
        kosten = dict(KOSTEN)
        kosten.update({"presse_anzahl": 3, "presse_dauer": 2, "presse_abschlag": 20})
        text = zerlegen_programm("ELSE presse").als_dict(kosten)["regeln"][0]["kosten"]
        self.assertIn("2 Züge", text)
        self.assertIn("3 gleichen Teilen", text)
        self.assertIn("20 %", text)

    def test_fahre_gegen_einen_gegner_ist_ein_rammen(self):
        text = zerlegen_programm("ELSE fahre rechts").als_dict(KOSTEN)["regeln"][0]["kosten"]
        self.assertIn("Wand", text)
        self.assertIn("Rammen", text)
        self.assertIn("5 Akku", text)
        self.assertNotIn("Gegner, kostet er nichts", text)

    def test_alle_ziele_bekommen_ihren_eigenen_kostensatz(self):
        faelle = (
            ("ELSE fahre_zu depot", "abstand_zu depot"),
            ("ELSE fahre_zu gegner", "abstand_zu gegner"),
            ("ELSE fahre_zu zone", "abstand_zu zone"),
            ("ELSE fahre_zu naechster_muell(metall)",
             "abstand_zu naechster_muell(metall)"),
            ("ELSE fahre_zu weg_von gegner", "abstand_zu gegner"),
            ("ELSE fahre_zu feld(12, 8)", "abstand_zu feld(12, 8)"),
        )
        for quelle, erwartet in faelle:
            text = zerlegen_programm(quelle).als_dict(KOSTEN)["regeln"][0]["kosten"]
            self.assertIn(erwartet, text, quelle)
            self.assertNotIn("Rechnung gewinnt", text, quelle)

    def test_weg_von_gegner_nennt_den_abstand_zum_gegner(self):
        text = zerlegen_programm("ELSE fahre_zu weg_von gegner") \
            .als_dict(KOSTEN)["regeln"][0]["kosten"]
        self.assertIn("Abstand zum Gegner", text)

    def test_nur_das_best_ziel_bekommt_den_best_satz(self):
        text = zerlegen_programm("ELSE fahre_zu BEST muell BY wert - abstand") \
            .als_dict(KOSTEN)["regeln"][0]["kosten"]
        self.assertIn("Rechnung gewinnt", text)


class TestWortfragen(unittest.TestCase):
    """`richtung_zu` und `objekt_in_richtung`: Wörter statt Zahlen, nur `==` und `!=`."""

    def quelle(self, text):
        ergebnis = uebersetzen(text, "Team", "", KOSTEN)
        self.assertTrue(ergebnis["gueltig"], ergebnis["fehler"])
        return ergebnis["quelle"]

    def test_richtung_zu_wird_uebersetzt(self):
        quelle = self.quelle("IF richtung_zu depot == links THEN fahre rechts\nELSE warte")
        self.assertIn('zustand.richtung_zu_depot() == "links"', quelle)

    def test_alle_ziele_haben_eine_richtung(self):
        quelle = self.quelle(
            "IF richtung_zu naechster_muell(metall, in_zone) == hier THEN warte\n"
            "IF richtung_zu gegner != keine THEN warte\n"
            "IF richtung_zu zone == oben THEN warte\n"
            "IF richtung_zu weg_von gegner == unten THEN warte\n"
            "IF richtung_zu feld(3, 4) == rechts THEN warte\n"
            "IF richtung_zu BEST muell BY wert - abstand == links THEN warte\n"
            "ELSE warte")
        for teil in ('richtung_zu_muell(sorte="metall", nur_in_zone=True)',
                     "richtung_zu_gegner()", "richtung_zu_zone()",
                     "richtung_weg_von_gegner()", "richtung_zu_feld(3, 4)",
                     "self._beste_richtung(", "def _beste_richtung", "def _bestes_feld"):
            self.assertIn(teil, quelle)

    def test_objekt_in_richtung_mit_richtung_oder_frage(self):
        quelle = self.quelle(
            "IF objekt_in_richtung(oben) == wand THEN fahre unten\n"
            "IF objekt_in_richtung(richtung_zu depot) == fass THEN warte\n"
            "IF objekt_in_richtung links != frei THEN warte\n"
            "ELSE warte")
        self.assertIn('zustand.objekt_in_richtung("oben") == "wand"', quelle)
        self.assertIn('zustand.objekt_in_richtung(zustand.richtung_zu_depot()) == "radioaktiv"',
                      quelle)
        self.assertIn('zustand.objekt_in_richtung("links") != "frei"', quelle)

    def test_das_wort_darf_vorne_stehen(self):
        quelle = self.quelle("IF links == richtung_zu depot THEN warte\nELSE warte")
        self.assertIn('"links" == zustand.richtung_zu_depot()', quelle)

    def test_aliase_werden_vereinheitlicht(self):
        quelle = self.quelle("IF richtung_zu depot == hoch THEN warte\nELSE warte")
        self.assertIn('== "oben"', quelle)

    def test_nur_gleich_und_ungleich(self):
        text = meldungen("IF richtung_zu depot < links THEN warte")[0]
        self.assertIn("nur mit `==`", text)

    def test_einfaches_gleichheitszeichen(self):
        text = meldungen("IF objekt_in_richtung(oben) = wand THEN warte")[0]
        self.assertIn("zwei Gleichheitszeichen", text)

    def test_falsche_antwort_wird_erklaert(self):
        text = meldungen("IF richtung_zu depot == wand THEN warte")[0]
        self.assertIn("richtung_zu` antwortet", text)
        text = meldungen("IF objekt_in_richtung(oben) == linx THEN warte")[0]
        self.assertIn("objekt_in_richtung` antwortet", text)

    def test_ballen_liegen_nie_auf_dem_feld(self):
        text = meldungen("IF objekt_in_richtung(oben) == ballen THEN warte")[0]
        self.assertIn("Ballen", text)

    def test_richtung_ist_keine_zahl(self):
        text = meldungen("IF abstand_zu depot < richtung_zu depot THEN warte")[0]
        self.assertIn("liefert ein Wort", text)

    def test_richtung_und_objekt_nicht_mischen(self):
        text = meldungen("IF richtung_zu depot == objekt_in_richtung(oben) THEN warte")[0]
        self.assertIn("nicht mit einem Objekt", text)

    def test_objekt_braucht_eine_richtung(self):
        text = meldungen("IF objekt_in_richtung(depot) == frei THEN warte")[0]
        self.assertIn("Richtung", text)

    def test_erzeugte_datei_laeuft(self):
        quelle = self.quelle(
            "IF objekt_in_richtung(richtung_zu depot) == radioaktiv THEN fahre oben\n"
            "ELSE fahre_zu depot")
        raum = {}
        exec(compile(quelle, "<test>", "exec"), raum)

        class Zustand:
            def regel(self, nummer):
                pass

            def richtung_zu_depot(self):
                return "rechts"

            def objekt_in_richtung(self, richtung):
                return "radioaktiv" if richtung == "rechts" else "frei"

            def fahre(self, richtung):
                return richtung

            def fahre_zu_depot(self):
                return "rechts"

        self.assertEqual(raum["Roboter"]().entscheide(Zustand()), "oben")


class TestFehlermeldungen(unittest.TestCase):
    def test_alte_schluesselwoerter_werden_erklaert(self):
        self.assertIn("`WENN` heißt jetzt `IF`", meldungen("WENN akku < 30 DANN warte")[0])
        self.assertIn("`SONST` heißt jetzt `ELSE`", meldungen("SONST warte")[0])
        self.assertIn("`ladung_ist_voll`", meldungen("IF ladung ist voll THEN warte")[0])
        self.assertIn("`END`", meldungen("PYTHON\nreturn 'warte'\nENDE\nELSE warte")[0])

    def test_einfaches_gleichheitszeichen(self):
        text = meldungen("IF akku = 30 THEN warte")[0]
        self.assertIn("`==`", text)
        self.assertIn("LET", text)

    def test_fehlendes_ziel(self):
        text = meldungen("IF akku < 30 THEN fahre_zu")[0]
        self.assertIn("Zeile 1", text)
        self.assertIn("fahre_zu", text)
        self.assertIn("braucht ein Ziel", text)

    def test_tippfehler_bekommt_vorschlag(self):
        text = meldungen("ELSE fahr_zu depot")[0]
        self.assertIn("Meintest du `fahre_zu`?", text)

    def test_tippfehler_im_ziel(self):
        text = meldungen("ELSE fahre_zu depoo")[0]
        self.assertIn("Meintest du `depot`?", text)

    def test_tippfehler_im_modusnamen(self):
        text = meldungen("STATE heimweg\n ELSE GOTO heimwg")[0]
        self.assertIn("Meintest du `heimweg`?", text)

    def test_tippfehler_in_ja_nein_bedingungen_bekommt_vorschlag(self):
        for quelle, richtig in (("IF ladung_ist_vol THEN warte", "ladung_ist_voll"),
                                ("IF gegner_sichbar THEN warte", "gegner_sichtbar"),
                                ("IF RANDUM(30) THEN warte", "random")):
            text = meldungen(quelle)[0]
            self.assertIn("Meintest du `%s`?" % richtig, text, quelle)

    def test_fehlender_wert_verraet_keinen_falschen_kandidaten(self):
        for quelle in ("IF akku < THEN warte",
                       "IF akku < AND akku > 1 THEN warte",
                       "IF akku < OR akku > 1 THEN warte",
                       "IF (akku + ) > 3 THEN warte",
                       "IF akku <"):
            text = meldungen(quelle)[0]
            self.assertIn("fehlt ein Wert", text, quelle)
            self.assertNotIn("Meintest du", text, quelle)

    def test_tippfehler_der_muellsorte_bei_anzahl(self):
        text = meldungen("IF anzahl(metal) > 0 THEN warte")[0]
        self.assertIn("Die Müllsorte `metal`", text)
        self.assertIn("Meintest du `metall`?", text)

    def test_naechster_muell_erlaubt_nur_eine_sorte(self):
        for quelle in ("ELSE fahre_zu naechster_muell(metall, papier)",
                       "ELSE fahre_zu naechster_muell metall papier",
                       "ELSE fahre_zu BEST muell(metall, papier) BY wert"):
            text = meldungen(quelle)[0]
            self.assertIn("Nur eine Sorte erlaubt", text, quelle)

    def test_ballen_ist_kein_ziel(self):
        for quelle in ("ELSE fahre_zu naechster_muell(ballen)",
                       "ELSE fahre_zu naechster_muell(ballen, in_zone)"):
            text = meldungen(quelle)[0]
            self.assertIn("Ballen liegen nie auf dem Feld", text, quelle)

    def test_best_ohne_formel_zeigt_das_best_beispiel(self):
        text = meldungen("ELSE fahre_zu BEST muell BY")[0]
        self.assertIn("BEST muell BY", text)
        self.assertNotIn("IF akku < 30", text)

    def test_regel_ohne_if(self):
        text = meldungen("fahre_zu depot")[0]
        self.assertIn("`IF` oder `ELSE`", text)

    def test_fehlender_vergleich(self):
        text = meldungen("IF akku 30 THEN warte")[0]
        self.assertIn("Vergleich", text)

    def test_fehlende_aktion_nach_then(self):
        text = meldungen("IF akku < 30 THEN")[0]
        self.assertIn("fehlt", text)

    def test_richtung_statt_ziel(self):
        text = meldungen("ELSE fahre depot")[0]
        self.assertIn("fahre_zu", text)

    def test_weg_von_ohne_ziel(self):
        text = meldungen("ELSE fahre_zu weg_von")[0]
        self.assertIn("weg_von", text)
        self.assertIn("gegner", text)

    def test_weg_von_kennt_nur_gegner(self):
        for quelle in ("ELSE fahre_zu weg_von depot",
                       "ELSE fahre_zu weg_von(feld(1, 2))"):
            text = meldungen(quelle)[0]
            self.assertIn("gegner", text, quelle)
            self.assertNotIn("schließende Klammer", text, quelle)

    def test_feld_zu_viele_argumente(self):
        text = meldungen("ELSE fahre_zu feld(1, 2, 3)")[0]
        self.assertIn("Zu viele Argumente", text)
        self.assertNotIn("schließende Klammer", text)

    def test_in_zone_doppelt_ist_zu_viel(self):
        for quelle in ("ELSE fahre_zu naechster_muell(in_zone, in_zone)",
                       "ELSE fahre_zu naechster_muell in_zone in_zone"):
            text = meldungen(quelle)[0]
            self.assertIn("Zu viele Argumente", text, quelle)
            self.assertNotIn("schließende Klammer", text, quelle)

    def test_vergleich_statt_aktion(self):
        text = meldungen("IF gegner_sichtbar == 1 THEN warte")[0]
        self.assertIn("Vergleich", text)
        self.assertIn("Bedingung", text)
        self.assertNotIn("`==` ist keine Aktion", text)

    def test_alte_verknuepfung_an_der_vergleichsstelle(self):
        text = meldungen("IF akku < 30 NICHT gegner_sichtbar THEN warte")[0]
        self.assertIn("`NICHT` heißt jetzt `NOT`", text)
        self.assertNotIn("fehlt ein Vergleich", text)

    def test_alte_verknuepfungen_werden_erklaert(self):
        faelle = (("IF akku < 30 UND gegner_sichtbar THEN warte", "UND", "AND"),
                  ("IF akku < 30 ODER gegner_sichtbar THEN warte", "ODER", "OR"),
                  ("IF NICHT gegner_sichtbar THEN warte", "NICHT", "NOT"))
        for quelle, alt, neu in faelle:
            text = meldungen(quelle)[0]
            self.assertIn("`%s` heißt jetzt `%s`" % (alt, neu), text, quelle)

    def test_zeilennummer_stimmt(self):
        fehler = zerlegen_programm("ELSE warte\n\nIF quatsch THEN warte").fehler
        self.assertEqual(fehler[0].zeile, 3)

    def test_regelnummern_springen_nach_kaputtem_let_nicht(self):
        programm = zerlegen_programm("LET akku = 1\nELSE warte\nIF akku < 5 THEN warte")
        self.assertFalse(programm.gueltig)
        self.assertEqual([r.nummer for r in programm.regeln], [1, 2])

    def test_regelnummern_springen_nach_kaputtem_state_nicht(self):
        programm = zerlegen_programm("STATE akku\nELSE warte")
        self.assertFalse(programm.gueltig)
        self.assertEqual([r.nummer for r in programm.regeln], [1])

    def test_mehrere_fehler_werden_gesammelt(self):
        self.assertEqual(len(meldungen("fahre_zu depot\nIF akku THEN warte")), 2)

    def test_muell_in_der_zeile_dahinter(self):
        text = meldungen("ELSE warte 7")[0]
        self.assertIn("genau eine Regel", text)

    def test_zweite_aktion_ohne_komma(self):
        text = meldungen("ELSE warte warte")[0]
        self.assertIn("mit Komma", text)


class TestHinweise(unittest.TestCase):
    def test_regel_nach_else_ist_unerreichbar(self):
        programm = zerlegen_programm("ELSE warte\nIF akku < 5 THEN fahre_zu depot")
        self.assertTrue(programm.gueltig)
        self.assertTrue(any("nie erreicht" in h.text for h in programm.hinweise))

    def test_fehlendes_else_wird_angemerkt(self):
        programm = zerlegen_programm("IF akku < 5 THEN fahre_zu depot")
        self.assertTrue(any("ELSE" in h.text for h in programm.hinweise))

    def test_leeres_programm(self):
        programm = zerlegen_programm("\n\n# nur Kommentare\n")
        self.assertTrue(any("noch keine Regel" in h.text for h in programm.hinweise))


class TestUebersetzung(unittest.TestCase):
    def test_erzeugte_datei_ist_gueltiges_python(self):
        ergebnis = uebersetzen(BEISPIEL, "Team Blitz")
        self.assertTrue(ergebnis["gueltig"], ergebnis["fehler"])
        compile(ergebnis["quelle"], "<test>", "exec")

    def test_pseudocode_steht_in_der_datei(self):
        ergebnis = uebersetzen(BEISPIEL, "Team Blitz")
        gelesen = aus_python_lesen(ergebnis["quelle"])
        self.assertEqual(gelesen["name"], "Team Blitz")
        self.assertEqual(gelesen["pseudocode"].strip(), BEISPIEL.strip())

    def test_rueckweg_ueber_sonderzeichen(self):
        heikel = 'ELSE warte  # Anführungszeichen """ und ein Rückstrich \\'
        ergebnis = uebersetzen(heikel, 'Team "Anführung"')
        self.assertTrue(ergebnis["gueltig"], ergebnis["fehler"])
        gelesen = aus_python_lesen(ergebnis["quelle"])
        self.assertEqual(gelesen["pseudocode"].strip(), heikel.strip())

    def test_rueckweg_ueber_einen_automaten(self):
        ergebnis = uebersetzen(AUTOMAT, "Team Automat")
        gelesen = aus_python_lesen(ergebnis["quelle"])
        self.assertEqual(gelesen["pseudocode"].strip(), AUTOMAT.strip())

    def test_regelnummern_landen_im_code(self):
        ergebnis = uebersetzen(BEISPIEL, "Team Blitz")
        self.assertIn("zustand.regel(1)", ergebnis["quelle"])
        self.assertIn("zustand.regel(5)", ergebnis["quelle"])

    def test_ohne_else_wird_gewartet(self):
        ergebnis = uebersetzen("IF akku < 5 THEN fahre_zu depot", "T")
        self.assertIn('return "warte"', ergebnis["quelle"])

    def test_python_block_wird_uebernommen(self):
        quelltext = ("IF akku < 5 THEN fahre_zu depot\n"
                     "PYTHON\n"
                     "if zustand.tick > 300 and zustand.ladung > 0:\n"
                     "    return zustand.fahre_zu_depot()\n"
                     "END\n"
                     "ELSE fahre_zu naechster_muell")
        ergebnis = uebersetzen(quelltext, "Profis")
        self.assertTrue(ergebnis["gueltig"], ergebnis["fehler"])
        self.assertIn("if zustand.tick > 300", ergebnis["quelle"])
        compile(ergebnis["quelle"], "<test>", "exec")

    def test_python_block_in_einem_modus(self):
        quelltext = ("STATE sammeln\n"
                     "PYTHON\n"
                     "if zustand.tick > 300:\n"
                     "    return zustand.fahre_zu_depot()\n"
                     "END\n"
                     "ELSE fahre_zu naechster_muell")
        ergebnis = uebersetzen(quelltext, "Profis")
        self.assertTrue(ergebnis["gueltig"], ergebnis["fehler"])
        self.assertIn("def _modus_sammeln", ergebnis["quelle"])
        self.assertIn("if zustand.tick > 300", ergebnis["quelle"])
        compile(ergebnis["quelle"], "<test>", "exec")

    def test_kaputter_python_block_meldet_die_richtige_zeile(self):
        quelltext = "PYTHON\nif ohne doppelpunkt\nEND\nELSE warte"
        ergebnis = uebersetzen(quelltext, "Profis")
        self.assertFalse(ergebnis["gueltig"])
        self.assertIn("PYTHON-Block", ergebnis["fehler"][0]["meldung"])

    def test_python_block_meldet_die_zeile_im_block(self):
        quelltext = ("IF akku < 5 THEN warte\n"
                     "PYTHON\n"
                     "wert = 1\n"
                     "if ohne doppelpunkt\n"
                     "END\n")
        ergebnis = uebersetzen(quelltext, "Profis")
        self.assertFalse(ergebnis["gueltig"])
        self.assertIn("PYTHON-Block", ergebnis["fehler"][0]["meldung"])
        self.assertEqual(ergebnis["fehler"][0]["zeile"], 4)

    def test_python_block_nach_unbedingtem_else_bleibt_erhalten(self):
        quelltext = ("ELSE warte\n"
                     "PYTHON\n"
                     'return "presse"\n'
                     "END\n")
        ergebnis = uebersetzen(quelltext, "Profis")
        self.assertTrue(ergebnis["gueltig"], ergebnis["fehler"])
        self.assertIn("# --- eigener PYTHON-Block aus Zeile 2 ---", ergebnis["quelle"])
        self.assertIn('        return "presse"', ergebnis["quelle"])
        compile(ergebnis["quelle"], "<test>", "exec")

    def test_uebersetzen_ueberlebt_zu_tiefe_klammern(self):
        quelltext = "IF " + "(" * 250 + "akku" + ")" * 250 + " THEN warte"
        ergebnis = uebersetzen(quelltext, "T")
        self.assertFalse(ergebnis["gueltig"])
        self.assertTrue(any("verschachtelt" in f["meldung"]
                            for f in ergebnis["fehler"]))

    def test_offener_python_block_wird_gemeldet(self):
        ergebnis = uebersetzen("PYTHON\nreturn 'warte'", "T")
        self.assertFalse(ergebnis["gueltig"])
        self.assertIn("END", ergebnis["fehler"][0]["meldung"])

    def test_end_mit_kommentar_schliesst_den_block(self):
        ergebnis = uebersetzen("PYTHON\nreturn 'warte'\nEND  # fertig\nELSE warte", "T")
        self.assertTrue(ergebnis["gueltig"], ergebnis["fehler"])

    def test_fehlerhafter_pseudocode_erzeugt_keine_datei(self):
        ergebnis = uebersetzen("fahre_zu depot", "T")
        self.assertFalse(ergebnis["gueltig"])
        self.assertIsNone(ergebnis["quelle"])



class TestGemeinsameQuellen(unittest.TestCase):
    """Parser, Compiler und Engine dürfen bei geteilten Namen nicht auseinanderlaufen."""

    def test_flaggen_und_zahlwerte_decken_sich(self):
        from language import parser
        self.assertEqual(set(compiler.FLAGGEN_ZU_PYTHON), set(parser.FLAGGEN))
        self.assertEqual(set(compiler.ZAHLWERTE_ZU_PYTHON), set(parser.ZAHLWERTE))
        for name, ausdruck in compiler.FLAGGEN_ZU_PYTHON.items():
            self.assertEqual(ausdruck, "zustand." + name)
        for name, ausdruck in compiler.ZAHLWERTE_ZU_PYTHON.items():
            self.assertEqual(ausdruck, "zustand." + name)

    def test_unerreichbares_ziel_kommt_aus_dem_zustand(self):
        quelle = uebersetzen("ELSE fahre_zu BEST muell BY wert - abstand", "T")["quelle"]
        self.assertIn("zustand.unerriechbar", quelle)
        self.assertNotIn("9999", quelle)

    def test_max_wechsel_kommt_aus_dem_zustand(self):
        quelle = uebersetzen(AUTOMAT, "T")["quelle"]
        self.assertIn("range(zustand.max_wechsel)", quelle)
        self.assertNotIn("MAX_WECHSEL", quelle)


class TestEditorVorlage(unittest.TestCase):
    """Die Vorlage im Editor ist das Erste, was ein Team sieht.

    Sie steht in `web/static/werkstatt.js` und wird von niemandem sonst geprüft —
    ein Tippfehler darin begrüßt jedes Team mit einer roten Fehlermarkierung.
    Der Test übersetzt sie mit demselben Parser wie die Werkstatt.
    """

    PROJEKT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def vorlage(self):
        pfad = os.path.join(self.PROJEKT, "web", "static", "werkstatt.js")
        with io.open(pfad, encoding="utf-8") as datei:
            quelle = datei.read()
        treffer = re.search(r"const VORLAGE = `(.*?)`;\n", quelle, re.S)
        self.assertIsNotNone(treffer, "VORLAGE nicht in werkstatt.js gefunden")
        return treffer.group(1)

    def test_vorlage_laesst_sich_uebersetzen(self):
        ergebnis = uebersetzen(self.vorlage(), "Vorlage", kosten=KOSTEN)
        self.assertTrue(ergebnis["gueltig"],
                        "Fehler in der Vorlage: %s"
                        % [f["meldung"] for f in ergebnis["fehler"]])

    def test_vorlage_zeigt_die_modi(self):
        """Sie soll den Zustandsautomaten vorführen, nicht nur eine Regelliste."""
        ergebnis = uebersetzen(self.vorlage(), "Vorlage", kosten=KOSTEN)
        namen = [m["name"] for m in ergebnis["modi"]]
        self.assertIn("sammeln", namen)
        self.assertIn("heimweg", namen)

    def test_die_einzelnen_beispielzeilen_sind_gueltig(self):
        """Die Regelzeilen zum Einsetzen — in der Vorlage um sechs Stellen eingerückt.

        Sie werden nicht als Block angehängt, sondern in einen Modus gesetzt, so
        wie ein Team sie einsetzen würde.
        """
        zeilen = [z[7:] for z in self.vorlage().splitlines() if z.startswith("#      ")]
        self.assertTrue(zeilen, "keine einzusetzenden Beispielzeilen gefunden")
        self.assertEqual(len(zeilen), 4,
                         "Zu jedem der vier Ausbauschritte gehört eine Beispielzeile")
        for zeile in zeilen:
            rumpf = "  %s\n" % zeile
            if not zeile.upper().startswith("ELSE"):
                rumpf += "  ELSE warte\n"
            quelltext = ("LET wegkosten = 3\n\nSTATE sammeln\n%s\n"
                         "STATE heimweg\n  ELSE fahre_zu depot\n\n"
                         "STATE jagd\n  ELSE ramme gegner\n" % rumpf)
            ergebnis = uebersetzen(quelltext, "Zeile", kosten=KOSTEN)
            self.assertTrue(ergebnis["gueltig"],
                            "Beispielzeile %r: %s"
                            % (zeile, [f["meldung"] for f in ergebnis["fehler"]]))

    def test_die_auskommentierten_beispiele_sind_gueltig(self):
        """Jedes Beispiel darunter muss laufen, wenn man die # wegnimmt.

        Die Zeilen der Beispiele stehen eingerückt hinter `# ` — der Test nimmt
        genau diese Vorsilbe weg und hängt den Block an die Vorlage an.
        """
        vorlage = self.vorlage()
        bloecke, laufend = [], []
        for zeile in vorlage.splitlines():
            if zeile.startswith("# STATE ") or (laufend and zeile.startswith("#   ")):
                laufend.append(zeile[2:])
            elif laufend:
                bloecke.append("\n".join(laufend))
                laufend = []
        if laufend:
            bloecke.append("\n".join(laufend))
        self.assertTrue(bloecke, "keine Modus-Beispiele in der Vorlage gefunden")
        for block in bloecke:
            name = block.splitlines()[0]
            # Der Modus braucht einen Weg hinein, sonst meldet der Parser ihn an.
            hinein = "  IF tick > 0 THEN GOTO %s\n" % name.split()[1]
            quelltext = vorlage.replace("  ELSE fahre_zu naechster_muell\n",
                                        hinein + "  ELSE fahre_zu naechster_muell\n", 1)
            ergebnis = uebersetzen(quelltext + "\n" + block + "\n", "Beispiel",
                                   kosten=KOSTEN)
            self.assertTrue(ergebnis["gueltig"],
                            "Beispiel %r: %s"
                            % (name, [f["meldung"] for f in ergebnis["fehler"]]))


class TestReferenz(unittest.TestCase):
    """Die Befehlsreferenz im Browser muss zur Sprache und zum Spiel passen.

    Sie steht in `web/static/app.js` und wird von niemandem sonst geprüft.
    """

    PROJEKT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def referenz(self):
        pfad = os.path.join(self.PROJEKT, "web", "static", "app.js")
        with io.open(pfad, encoding="utf-8") as datei:
            quelle = datei.read()
        treffer = re.search(r"const REFERENZ = `(.*?)`;\n", quelle, re.S)
        self.assertIsNotNone(treffer, "REFERENZ nicht in app.js gefunden")
        return treffer.group(1)

    def test_referenz_ist_nicht_leer(self):
        self.assertTrue(self.referenz().strip())

    def test_referenz_kennt_jede_aktion(self):
        from language.parser import AKTIONSWOERTER
        text = self.referenz().lower()
        for wort in sorted(AKTIONSWOERTER):
            self.assertIn(wort, text, "Aktion `%s` fehlt in der Referenz" % wort)

    def test_presse_dauer_ist_konkret(self):
        self.assertNotIn("ein paar Züge", self.referenz())


    def test_beispiele_mit_modi_sind_gueltig(self):
        """Jedes Beispiel mit `STATE` muss sich so, wie es dasteht, übersetzen lassen."""
        import html
        for roh in re.findall(r'<div class="beispiel">(.*?)</div>', self.referenz(), re.S):
            beispiel = html.unescape(roh)
            if "STATE" not in beispiel:
                continue
            with self.subTest(beispiel=beispiel[:40]):
                ergebnis = uebersetzen(beispiel, "T")
                self.assertTrue(ergebnis["gueltig"], ergebnis["fehler"])


class TestAbgabestand(unittest.TestCase):
    """Passt eine Abgabedatei noch zu dem, was die Werkstatt heute erzeugt?"""

    QUELLE = "STATE a\n  IF akku < 5 THEN oben, links, GOTO b\n  ELSE warte\nSTATE b\n  ELSE warte"

    def test_frisch_erzeugt_ist_aktuell(self):
        datei = uebersetzen(self.QUELLE, "T", "", KOSTEN)["quelle"]
        self.assertEqual(compiler.abgabe_stand(datei, KOSTEN), "aktuell")
        # Kosten und Docstrings stehen nur in Kommentaren — kein Grund für „veraltet".
        self.assertEqual(compiler.abgabe_stand(datei, None), "aktuell")

    def test_geaenderter_code_ist_veraltet(self):
        datei = uebersetzen(self.QUELLE, "T", "", KOSTEN)["quelle"]
        alt = datei.replace('return "warte"', 'return "oben"', 1)
        self.assertEqual(compiler.abgabe_stand(alt, KOSTEN), "veraltet")

    def test_ohne_pseudocode_kein_urteil(self):
        self.assertIsNone(compiler.abgabe_stand("class Roboter:\n    pass\n"))
        self.assertIsNone(compiler.abgabe_stand("das ist kein python ("))

    def test_pseudocode_der_nicht_mehr_geht(self):
        datei = uebersetzen(self.QUELLE, "T", "", KOSTEN)["quelle"]
        kaputt = datei.replace("ELSE warte", "ELSE trödeln", 1)
        self.assertEqual(compiler.abgabe_stand(kaputt, KOSTEN), "ungueltig")

if __name__ == "__main__":
    unittest.main()
