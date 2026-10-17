"""Die JSON-Schnittstelle. Getestet wird das Verhalten, nicht die Oberfläche."""

import contextlib
import io
import json
import os
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

from engine import tournament
from web import api
from web.server import Anwendung, server_bauen

PROJEKT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestSchnittstelle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        anwendung = Anwendung()
        api.registriere(anwendung)
        cls.anwendung = anwendung
        cls.server = server_bauen(anwendung, 0)
        cls.port = cls.server.server_address[1]
        cls.faden = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.faden.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def rufe(self, pfad, daten=None, kopfzeilen=None):
        adresse = "http://127.0.0.1:%d%s" % (self.port, pfad)
        if daten is None:
            anfrage = urllib.request.Request(adresse, headers=kopfzeilen or {})
        else:
            kopf = {"Content-Type": "application/json"}
            kopf.update(kopfzeilen or {})
            anfrage = urllib.request.Request(
                adresse, data=json.dumps(daten).encode("utf-8"), headers=kopf)
        try:
            with urllib.request.urlopen(anfrage, timeout=60) as antwort:
                return antwort.status, json.loads(antwort.read().decode("utf-8"))
        except urllib.error.HTTPError as fehler:
            return fehler.code, json.loads(fehler.read().decode("utf-8"))

    def pfad_schluessel(self, daten, stelle=()):
        """Sammelt rekursiv die Fundstellen aller Schlüssel `pfad`."""
        treffer = []
        if isinstance(daten, dict):
            for schluessel, wert in daten.items():
                if schluessel == "pfad":
                    treffer.append(stelle + (schluessel,))
                treffer.extend(self.pfad_schluessel(wert, stelle + (schluessel,)))
        elif isinstance(daten, list):
            for i, wert in enumerate(daten):
                treffer.extend(self.pfad_schluessel(wert, stelle + (i,)))
        return treffer

    def test_startseite_wird_ausgeliefert(self):
        adresse = "http://127.0.0.1:%d/" % self.port
        with urllib.request.urlopen(adresse, timeout=10) as antwort:
            inhalt = antwort.read().decode("utf-8")
        self.assertIn("<title>Müllsammel-Roboter Turnier</title>", inhalt)

    def test_status_nennt_die_gegner(self):
        status, daten = self.rufe("/api/status")
        self.assertEqual(status, 200)
        self.assertTrue(any(g["datei"] == "fleissig.py" for g in daten["gegner"]))
        self.assertEqual(daten["spiel"]["breite"], 24)

    def test_pruefen_meldet_fehler_mit_zeile(self):
        _, daten = self.rufe("/api/pruefen", {"quelltext": "IF akku < 30 THEN fahr_zu depot"})
        self.assertFalse(daten["gueltig"])
        self.assertEqual(daten["fehler"][0]["zeile"], 1)
        self.assertEqual(daten["fehler"][0]["vorschlag"], "fahre_zu")

    def test_pruefen_meldet_uebersetzungsfehler(self):
        """Was der Parser durchlässt, kann beim Übersetzen noch scheitern."""
        _, daten = self.rufe("/api/pruefen", {"quelltext":
            "IF abstand_zu BEST muell BY wert > 2 THEN warte"})
        self.assertFalse(daten["gueltig"])
        self.assertIn("abstand_zu BEST", daten["fehler"][0]["meldung"])
        # Der erzeugte Python-Code wird beim Prüfen nicht mitgeschickt.
        self.assertIsNone(daten["quelle"])

    def test_pruefen_meldet_zu_grosse_zahl_ohne_500(self):
        status, daten = self.rufe("/api/pruefen", {
            "quelltext": "IF akku < " + "9" * 30 + " THEN warte"})
        self.assertEqual(status, 200)
        self.assertFalse(daten["gueltig"])
        self.assertTrue(any("zu groß" in f["meldung"] for f in daten["fehler"]),
                        daten["fehler"])
        self.assertNotIn("Traceback", json.dumps(daten))

    def test_pruefen_meldet_zu_tiefe_klammern_ohne_500(self):
        quelltext = "IF " + "(" * 250 + "akku" + ")" * 250 + " THEN warte"
        status, daten = self.rufe("/api/pruefen", {"quelltext": quelltext})
        self.assertEqual(status, 200)
        self.assertFalse(daten["gueltig"])
        self.assertTrue(any("verschachtelt" in f["meldung"] for f in daten["fehler"]),
                        daten["fehler"])
        self.assertNotIn("Traceback", json.dumps(daten))

    def test_testlauf_liefert_eine_aufzeichnung(self):
        _, daten = self.rufe("/api/testlauf", {
            "quelltext": "IF ladung_ist_voll THEN fahre_zu depot\n"
                         "ELSE fahre_zu naechster_muell",
            "teamname": "Team Test", "gegner": "fleissig.py", "seed": 2, "ticks": 60})
        self.assertTrue(daten["programm"]["gueltig"], daten["programm"]["fehler"])
        aufzeichnung = daten["aufzeichnung"]
        self.assertEqual(len(aufzeichnung["ticks"]), 60)
        self.assertIn("start", aufzeichnung)
        self.assertEqual(aufzeichnung["spieler"][0]["name"], "Team Test")

    def test_testlauf_meldet_stillstand_und_folgen_ins_leere(self):
        """Der Bericht kommt aus Python: der Roboter fährt nach links gegen die Wand."""
        _, daten = self.rufe("/api/testlauf", {
            "quelltext": "STATE a\n  ELSE links, links", "seed": 1, "ticks": 60})
        self.assertTrue(daten["programm"]["gueltig"], daten["programm"]["fehler"])
        texte = " ".join(m["text"] for m in daten["bericht"])
        self.assertIn("Folge aus Zeile 2", texte)
        self.assertIn("nicht vom Fleck", texte)
        self.assertTrue(all(m["zeile"] == 2 for m in daten["bericht"]), daten["bericht"])

    def test_testlauf_verraet_keinen_serverpfad(self):
        _, daten = self.rufe("/api/testlauf", {
            "quelltext": "ELSE warte", "teamname": "Team Pfad",
            "seed": 1, "ticks": 10})
        self.assertTrue(daten["programm"]["gueltig"], daten["programm"]["fehler"])
        self.assertEqual(self.pfad_schluessel(daten), [])
        self.assertNotIn(PROJEKT, json.dumps(daten))

    def test_pruefen_liefert_modus_und_kosten(self):
        _, daten = self.rufe("/api/pruefen", {"quelltext":
            "STATE sammeln\n  IF ladung_ist_voll THEN GOTO heimweg\n"
            "  ELSE fahre_zu naechster_muell\n"
            "STATE heimweg\n  ELSE fahre_zu depot"})
        self.assertTrue(daten["gueltig"], daten["fehler"])
        self.assertEqual([m["name"] for m in daten["modi"]], ["sammeln", "heimweg"])
        self.assertEqual(daten["regeln"][0]["modus"], "sammeln")
        self.assertIn("0 Züge", daten["regeln"][0]["kosten"])
        # Die Zahlen in der Kostenangabe kommen aus der config.json.
        self.assertIn("1 Akku", daten["regeln"][2]["kosten"])

    def test_testlauf_mit_einem_automaten(self):
        _, daten = self.rufe("/api/testlauf", {
            "quelltext": "STATE sammeln\n"
                         "  IF ladung_ist_voll THEN GOTO heimweg\n"
                         "  ELSE fahre_zu BEST muell BY wert - 3 * abstand\n"
                         "STATE heimweg\n"
                         "  IF ladung_ist_leer THEN GOTO sammeln\n"
                         "  ELSE fahre_zu depot",
            "teamname": "Team Automat", "gegner": "fleissig.py", "seed": 2, "ticks": 80})
        self.assertTrue(daten["programm"]["gueltig"], daten["programm"]["fehler"])
        self.assertEqual(len(daten["aufzeichnung"]["ticks"]), 80)
        for bot in daten["aufzeichnung"]["bots"]:
            self.assertEqual(bot["fehler"], [])

    def test_testlauf_ohne_gegner_faehrt_allein(self):
        """Die Vorgabe in der Werkstatt: erst einmal zusehen, was der eigene tut."""
        _, daten = self.rufe("/api/testlauf", {
            "quelltext": "IF ladung_ist_voll THEN fahre_zu depot\n"
                         "ELSE fahre_zu naechster_muell",
            "teamname": "Team Allein", "gegner": "", "seed": 2, "ticks": 40})
        self.assertTrue(daten["programm"]["gueltig"], daten["programm"]["fehler"])
        aufzeichnung = daten["aufzeichnung"]
        self.assertEqual(len(aufzeichnung["ergebnis"]["roboter"]), 1)
        self.assertEqual(aufzeichnung["ergebnis"]["roboter"][0]["name"], "Team Allein")
        self.assertEqual(len(aufzeichnung["ticks"]), 40)
        for bot in aufzeichnung["bots"]:
            self.assertEqual(bot["fehler"], [])

    def test_testlauf_ohne_angabe_faehrt_allein(self):
        """Fehlt das Feld ganz, gilt dasselbe — kein heimlicher Gegner."""
        _, daten = self.rufe("/api/testlauf", {
            "quelltext": "ELSE fahre_zu naechster_muell",
            "teamname": "Team Allein", "seed": 1, "ticks": 20})
        self.assertEqual(len(daten["aufzeichnung"]["ergebnis"]["roboter"]), 1)

    def test_testlauf_ohne_gueltige_regeln_spielt_nicht(self):
        _, daten = self.rufe("/api/testlauf", {"quelltext": "fahre_zu depot"})
        self.assertIsNone(daten["aufzeichnung"])
        self.assertFalse(daten["programm"]["gueltig"])

    def test_unbekannter_gegner_wird_abgelehnt(self):
        status, daten = self.rufe("/api/testlauf", {
            "quelltext": "ELSE warte", "gegner": "../../etc/passwd"})
        self.assertEqual(status, 400)
        self.assertIn("Gegner", daten["fehler"])

    def test_abgabe_und_wieder_oeffnen(self):
        quelltext = "IF akku < 20 THEN fahre_zu depot\nELSE fahre_zu naechster_muell"
        _, abgabe = self.rufe("/api/abgabe", {"quelltext": quelltext,
                                              "teamname": "Die Müll-Profis"})
        self.assertEqual(abgabe["dateiname"], "die_muell_profis.py")
        _, gelesen = self.rufe("/api/oeffnen", {"inhalt": abgabe["quelle"]})
        self.assertEqual(gelesen["pseudocode"].strip(), quelltext.strip())
        self.assertEqual(gelesen["name"], "Die Müll-Profis")

    def test_fremde_datei_wird_freundlich_abgelehnt(self):
        status, daten = self.rufe("/api/oeffnen", {"inhalt": "print('hallo')\n"})
        self.assertEqual(status, 400)
        self.assertIn("PSEUDOCODE", daten["fehler"])

    def test_fsr_passwort(self):
        status, _ = self.rufe("/api/fsr/anmelden", {"passwort": "falsch"})
        self.assertEqual(status, 403)
        status, daten = self.rufe("/api/fsr/anmelden",
                                  {"passwort": self.anwendung.config.fsr_passwort})
        self.assertEqual(status, 200)
        self.assertIn("marke", daten)

    # ------------------------------------------------------------------ FSR

    def marke(self):
        _, daten = self.rufe("/api/fsr/anmelden",
                             {"passwort": self.anwendung.config.fsr_passwort})
        return daten["marke"]

    def fsr(self, pfad, daten=None):
        eingabe = dict(daten or {})
        eingabe.setdefault("marke", self.marke())
        return self.rufe(pfad, eingabe)

    def warte_auf_aufgabe(self, nummer, marke, versuche=600):
        for _ in range(versuche):
            status, eintrag = self.rufe("/api/fsr/aufgabe", {"id": nummer, "marke": marke})
            self.assertEqual(status, 200)
            if eintrag["fertig"]:
                self.assertIsNone(eintrag["fehler"], eintrag["fehler"])
                return eintrag["ergebnis"]
            time.sleep(0.1)
        self.fail("Die Aufgabe %d wurde nicht fertig." % nummer)

    def test_fsr_routen_verlangen_eine_marke(self):
        for pfad in ("/api/fsr/bots", "/api/fsr/match", "/api/fsr/gruppe", "/api/fsr/ko",
                     "/api/fsr/balance", "/api/fsr/aufgabe", "/api/fsr/config",
                     "/api/fsr/turniere"):
            status, daten = self.rufe(pfad, {})
            self.assertEqual(status, 403, pfad)
            self.assertIn("anmelden", daten["fehler"])

    def test_erfundene_marke_zaehlt_nicht(self):
        status, _ = self.rufe("/api/fsr/bots", {"marke": "0123456789abcdef"})
        self.assertEqual(status, 403)

    def test_fsr_bots_listet_beide_ordner(self):
        status, daten = self.fsr("/api/fsr/bots")
        self.assertEqual(status, 200)
        self.assertTrue(any(b["datei"] == "hausmeister.py" for b in daten["mitgeliefert"]))
        self.assertIsInstance(daten["abgaben"], list)
        self.assertEqual(daten["abgaben_ordner"], "abgaben")
        # Kein Serverpfad — weder als Schlüssel noch als Text im Paket.
        self.assertEqual(self.pfad_schluessel(daten), [])
        self.assertFalse(os.path.isabs(daten["abgaben_ordner"]))
        self.assertNotIn(PROJEKT, json.dumps(daten))

    def test_fsr_bots_zeigt_veraltete_abgaben(self):
        from engine import spielleiter
        from language.compiler import uebersetzen
        quelle = uebersetzen("STATE a\n  ELSE oben, links", "Frisch", "",
                             api.kosten_aus(self.anwendung.config))["quelle"]
        with tempfile.TemporaryDirectory() as ordner:
            with open(os.path.join(ordner, "frisch.py"), "w", encoding="utf-8") as datei:
                datei.write(quelle)
            with open(os.path.join(ordner, "alt.py"), "w", encoding="utf-8") as datei:
                datei.write(quelle.replace('return "warte"', 'return "oben"', 1))
            vorher = spielleiter.ABGABEN_ORDNER
            spielleiter.ABGABEN_ORDNER = ordner
            try:
                status, daten = self.fsr("/api/fsr/bots")
            finally:
                spielleiter.ABGABEN_ORDNER = vorher
        self.assertEqual(status, 200)
        stand = {b["datei"]: b["stand"] for b in daten["abgaben"]}
        self.assertEqual(stand, {"alt.py": "veraltet", "frisch.py": "aktuell"})

    def test_fsr_match_spielt_zwei_roboter(self):
        status, daten = self.fsr("/api/fsr/match", {
            "bots": ["bots/fleissig.py", "bots/rumpelstilzchen.py"],
            "seed": 3, "ticks": 40})
        self.assertEqual(status, 200)
        aufzeichnung = daten["aufzeichnung"]
        self.assertEqual(len(aufzeichnung["ticks"]), 40)
        self.assertEqual([s["name"] for s in aufzeichnung["spieler"]],
                         ["Fleißig", "Rumpelstilzchen"])

    def test_fsr_match_nimmt_jeden_partieseed_eines_turniers(self):
        # Ein gewürfelter Turnier-Seed erzeugt Partie-Seeds bis knapp unter 2**31;
        # die Bühne muss jede davon nachspielen dürfen.
        seed = max(tournament.partie_seed(s, 4, 0) for s in range(100000, 100200)) + 100
        self.assertGreater(seed, 10 ** 9)
        status, daten = self.fsr("/api/fsr/match", {
            "bots": ["bots/fleissig.py", "bots/rumpelstilzchen.py"],
            "seed": seed, "ticks": 10})
        self.assertEqual(status, 200, daten)

    def test_fsr_match_verraet_keinen_serverpfad(self):
        status, daten = self.fsr("/api/fsr/match", {
            "bots": ["bots/fleissig.py", "bots/hausmeister.py"],
            "seed": 1, "ticks": 10})
        self.assertEqual(status, 200)
        self.assertNotIn('"pfad"', json.dumps(daten))
        self.assertEqual(len(daten["aufzeichnung"]["spieler"]), 2)

    def test_fsr_match_prueft_die_anzahl(self):
        status, daten = self.fsr("/api/fsr/match", {"bots": ["bots/fleissig.py"]})
        self.assertEqual(status, 400)
        self.assertIn("2 bis 4", daten["fehler"])

    def test_fsr_match_laesst_keinen_pfad_durch(self):
        for kennung in ("bots/../config.json", "abgaben/../../start.py", "fleissig.py",
                        "sonstwo/fleissig.py"):
            status, _ = self.fsr("/api/fsr/match",
                                 {"bots": [kennung, "bots/fleissig.py"], "ticks": 20})
            self.assertEqual(status, 400, kennung)

    def test_fsr_gruppe_braucht_die_volle_gruppengroesse(self):
        status, daten = self.fsr("/api/fsr/gruppe",
                                 {"bots": ["bots/fleissig.py", "bots/hausmeister.py"]})
        self.assertEqual(status, 400)
        self.assertIn("Gruppe", daten["fehler"])

    def test_fsr_ko_laeuft_als_hintergrundaufgabe_durch(self):
        marke = self.marke()
        alt = self.anwendung.config.als_dict()
        kurz = json.loads(json.dumps(alt))
        kurz["spiel"]["runden_laenge"] = 20
        self.anwendung.config_setzen(kurz)
        try:
            status, daten = self.rufe("/api/fsr/ko", {
                "marke": marke, "seed": 1,
                "bots": ["bots/fleissig.py", "bots/rumpelstilzchen.py",
                         "bots/hausmeister.py"]})
            self.assertEqual(status, 200)
            ergebnis = self.warte_auf_aufgabe(daten["aufgabe"], marke)
        finally:
            self.anwendung.config_setzen(alt)
        self.assertEqual(ergebnis["art"], "ko")
        self.assertIsNotNone(ergebnis["sieger"])
        # Nur der Dateiname, kein Pfad aus dem Rechner der Turnierleitung.
        self.assertNotIn(os.sep, ergebnis["gespeichert"])
        self.assertTrue(ergebnis["gespeichert"].endswith("_ko.json"))

        _, archiv = self.rufe("/api/fsr/turniere", {"marke": marke})
        eintrag = [e for e in archiv["turniere"] if e["datei"] == ergebnis["gespeichert"]]
        self.assertEqual(len(eintrag), 1)
        self.assertEqual(eintrag[0]["art"], "ko")
        self.assertEqual(eintrag[0]["sieger"], ergebnis["sieger"]["name"])

        _, geladen = self.rufe("/api/fsr/turniere",
                               {"marke": marke, "datei": ergebnis["gespeichert"]})
        self.assertEqual(geladen["turnier"]["sieger"]["name"], ergebnis["sieger"]["name"])
        os.remove(os.path.join(PROJEKT, "turnier", ergebnis["gespeichert"]))

    def test_fsr_ko_lehnt_doppelte_roboter_ab(self):
        status, daten = self.fsr("/api/fsr/ko", {
            "bots": ["bots/fleissig.py", "bots/fleissig.py"]})
        self.assertEqual(status, 400)
        self.assertIn("nur einmal", daten["fehler"])

    def test_fsr_ko_braucht_mindestens_zwei(self):
        status, daten = self.fsr("/api/fsr/ko", {"bots": ["bots/fleissig.py"]})
        self.assertEqual(status, 400)
        self.assertIn("mindestens 2", daten["fehler"])

    def test_archiv_verraet_keinen_serverpfad(self):
        """Die Ablage kennt den absoluten Bot-Pfad — der Browser bekommt ihn nicht."""
        marke = self.marke()
        datei = "_test_serverpfad_ko.json"
        pfad = os.path.join(PROJEKT, "turnier", datei)
        os.makedirs(os.path.dirname(pfad), exist_ok=True)
        turnier = {
            "art": "ko", "seed": 1,
            "sieger": {"name": "A", "datei": "a.py", "pfad": "/geheim/a.py"},
            "runden": [{"nummer": 1, "name": "Finale", "partien": [{
                "a": {"name": "A", "datei": "a.py", "pfad": "/geheim/a.py"},
                "b": {"name": "B", "datei": "b.py", "pfad": "/geheim/b.py"},
                "sieger_bot": {"name": "A", "datei": "a.py", "pfad": "/geheim/a.py"},
                "freilos": False, "punkte": [3, 1],
            }]}],
        }
        with open(pfad, "w", encoding="utf-8") as datei_inhalt:
            json.dump(turnier, datei_inhalt)
        try:
            status, geladen = self.rufe("/api/fsr/turniere",
                                        {"marke": marke, "datei": datei})
            self.assertEqual(status, 200)
            self.assertNotIn('"pfad"', json.dumps(geladen))
            status, liste = self.rufe("/api/fsr/turniere", {"marke": marke})
            self.assertEqual(status, 200)
            self.assertIn(datei, [e["datei"] for e in liste["turniere"]])
            self.assertNotIn('"pfad"', json.dumps(liste))
        finally:
            os.remove(pfad)

    def test_fsr_gruppe_laeuft_als_hintergrundaufgabe_durch(self):
        marke = self.marke()
        alt = self.anwendung.config.als_dict()
        kurz = json.loads(json.dumps(alt))
        kurz["spiel"]["runden_laenge"] = 20
        self.anwendung.config_setzen(kurz)
        try:
            status, daten = self.rufe("/api/fsr/gruppe", {
                "marke": marke, "seed": 1,
                "bots": ["bots/fleissig.py", "bots/rumpelstilzchen.py",
                         "bots/hausmeister.py", "bots/lauerer.py"]})
            self.assertEqual(status, 200)
            ergebnis = self.warte_auf_aufgabe(daten["aufgabe"], marke)
        finally:
            self.anwendung.config_setzen(alt)
        self.assertEqual(ergebnis["art"], "gruppe")
        self.assertEqual(len(ergebnis["tabelle"]), 4)
        self.assertTrue(ergebnis["gespeichert"].endswith("_gruppe.json"))
        os.remove(os.path.join(PROJEKT, "turnier", ergebnis["gespeichert"]))

    def test_fsr_balance_laeuft_als_hintergrundaufgabe_durch(self):
        marke = self.marke()
        alt = self.anwendung.config.als_dict()
        kurz = json.loads(json.dumps(alt))
        kurz["spiel"]["runden_laenge"] = 20
        self.anwendung.config_setzen(kurz)
        try:
            status, daten = self.rufe("/api/fsr/balance",
                                      {"marke": marke, "ordner": "bots", "seeds": 1})
            self.assertEqual(status, 200)
            bericht = self.warte_auf_aufgabe(daten["aufgabe"], marke)
        finally:
            self.anwendung.config_setzen(alt)
        self.assertEqual(len(bericht["bots"]), 5)
        self.assertIn("urteil", bericht)

    def test_unbekannte_aufgabe_meldet_404(self):
        status, _ = self.fsr("/api/fsr/aufgabe", {"id": 999999})
        self.assertEqual(status, 404)

    def test_aufgabe_verraet_keinen_pfad_und_schont_das_original(self):
        """Auch das rohe Aufgabenergebnis wird beschnitten — die Kopie, nicht das Original."""
        marke = self.marke()
        with self.anwendung.sperre:
            self.anwendung.aufgaben_zaehler += 1
            nummer = self.anwendung.aufgaben_zaehler
            self.anwendung.aufgaben[nummer] = {
                "id": nummer,
                "beschreibung": "Test",
                "fertig": True,
                "fortschritt": 1,
                "gesamt": 1,
                "meldung": "fertig",
                "ergebnis": {
                    "sieger": {"name": "A", "kennung": "bots/a.py",
                               "pfad": "/geheim/a.py"},
                    "partien": [{"a": {"name": "A", "pfad": "/geheim/a.py"}}],
                },
                "fehler": None,
            }
        try:
            status, daten = self.rufe("/api/fsr/aufgabe", {"id": nummer, "marke": marke})
            self.assertEqual(status, 200)
            self.assertNotIn('"pfad"', json.dumps(daten))
            self.assertEqual(daten["ergebnis"]["sieger"]["kennung"], "bots/a.py")
            with self.anwendung.sperre:
                original = self.anwendung.aufgaben[nummer]["ergebnis"]["sieger"]["pfad"]
        finally:
            with self.anwendung.sperre:
                del self.anwendung.aufgaben[nummer]
        self.assertEqual(original, "/geheim/a.py")

    def test_gescheiterte_aufgabe_verraet_keinen_traceback(self):
        """Der Traceback bleibt auf stderr; die Antwort trägt nur die Kurzmeldung."""
        def arbeit(melden):
            raise ValueError("geheim")

        puffer = io.StringIO()
        with contextlib.redirect_stderr(puffer):
            eintrag = self.anwendung.aufgabe_starten("Testaufgabe", arbeit)
            for _ in range(200):
                if eintrag["fertig"]:
                    break
                time.sleep(0.02)
        self.assertTrue(eintrag["fertig"])
        self.assertEqual(eintrag["fehler"], "Unerwarteter Fehler: ValueError")
        self.assertNotIn("geheim", eintrag["fehler"])
        # Der volle Traceback landet auf stderr, mit der Aufgabe davor.
        self.assertIn("Testaufgabe", puffer.getvalue())
        self.assertIn("geheim", puffer.getvalue())
        marke = self.marke()
        status, daten = self.rufe("/api/fsr/aufgabe",
                                  {"id": eintrag["id"], "marke": marke})
        self.assertEqual(status, 200)
        self.assertEqual(daten["fehler"], "Unerwarteter Fehler: ValueError")
        with self.anwendung.sperre:
            self.anwendung.aufgaben.pop(eintrag["id"], None)

    def test_fehlendes_turnier_meldet_404(self):
        status, daten = self.fsr("/api/fsr/turniere", {"datei": "gibtsnicht.json"})
        self.assertEqual(status, 404)
        self.assertIn("gibtsnicht.json", daten["fehler"])

    def test_config_lesen_und_setzen(self):
        marke = self.marke()
        _, daten = self.rufe("/api/fsr/config", {"marke": marke})
        # Der Pfad aus dem Rechner der Turnierleitung gehört nicht in die Antwort.
        self.assertNotIn("pfad", daten)
        alt = daten["config"]
        neu = json.loads(json.dumps(alt))
        neu["spiel"]["runden_laenge"] = 123
        try:
            status, antwort = self.rufe("/api/fsr/config", {"marke": marke, "config": neu})
            self.assertEqual(status, 200)
            self.assertEqual(antwort["config"]["spiel"]["runden_laenge"], 123)
            self.assertEqual(self.anwendung.config.spiel.runden_laenge, 123)
            self.assertFalse(antwort["gespeichert"])
        finally:
            self.rufe("/api/fsr/config", {"marke": marke, "config": alt})
        self.assertEqual(self.anwendung.config.spiel.runden_laenge,
                         alt["spiel"]["runden_laenge"])

    def test_unsinnige_config_wird_abgelehnt(self):
        marke = self.marke()
        _, daten = self.rufe("/api/fsr/config", {"marke": marke})
        kaputt = json.loads(json.dumps(daten["config"]))
        kaputt["spiel"]["depot_abstand"] = 1
        status, antwort = self.rufe("/api/fsr/config", {"marke": marke, "config": kaputt})
        self.assertEqual(status, 400)
        self.assertIn("depot_abstand", antwort["fehler"])
        self.assertEqual(self.anwendung.config.spiel.depot_abstand,
                         daten["config"]["spiel"]["depot_abstand"])

    def test_config_abschnitt_mit_falschem_typ_meldet_400(self):
        marke = self.marke()
        _, daten = self.rufe("/api/fsr/config", {"marke": marke})
        kaputt = json.loads(json.dumps(daten["config"]))
        kaputt["presse"] = None
        status, antwort = self.rufe("/api/fsr/config", {"marke": marke, "config": kaputt})
        self.assertEqual(status, 400)
        self.assertIn("presse", antwort["fehler"])
        self.assertIn("Objekt", antwort["fehler"])
        self.assertEqual(self.anwendung.config.presse.anzahl,
                         daten["config"]["presse"]["anzahl"])

    def test_config_ohne_anzeige_wird_abgelehnt(self):
        """Vorher kam so eine Änderung durch und /api/status stürzte danach ab."""
        marke = self.marke()
        _, daten = self.rufe("/api/fsr/config", {"marke": marke})
        kaputt = json.loads(json.dumps(daten["config"]))
        del kaputt["muell"]["sorten"]["papier"]["anzeige"]
        status, antwort = self.rufe("/api/fsr/config", {"marke": marke, "config": kaputt})
        self.assertEqual(status, 400)
        self.assertIn("anzeige", antwort["fehler"])
        status, _ = self.rufe("/api/status")
        self.assertEqual(status, 200)

    def test_config_mit_null_im_wechselintervall_wird_abgelehnt(self):
        marke = self.marke()
        _, daten = self.rufe("/api/fsr/config", {"marke": marke})
        kaputt = json.loads(json.dumps(daten["config"]))
        kaputt["zone"]["wechsel_alle"] = 0
        status, antwort = self.rufe("/api/fsr/config",
                                    {"marke": marke, "config": kaputt})
        self.assertEqual(status, 400)
        self.assertIn("wechsel_alle", antwort["fehler"])

    def test_config_dauerhaft_schreibt_das_passwort_mit(self):
        """Der Browser schickt kein Passwort — der Server setzt seins wieder ein."""
        marke = self.marke()
        _, daten = self.rufe("/api/fsr/config", {"marke": marke})
        alt_config = daten["config"]
        alt_pfad = self.anwendung.config_pfad
        with tempfile.TemporaryDirectory() as ordner:
            pfad = os.path.join(ordner, "config.json")
            self.anwendung.config_pfad = pfad
            neu = json.loads(json.dumps(alt_config))
            neu["spiel"]["runden_laenge"] = 123
            try:
                status, antwort = self.rufe(
                    "/api/fsr/config",
                    {"marke": marke, "config": neu, "dauerhaft": True})
                self.assertEqual(status, 200)
                self.assertTrue(antwort["gespeichert"])
                with open(pfad, "r", encoding="utf-8") as datei:
                    geschrieben = json.load(datei)
            finally:
                self.anwendung.config_pfad = alt_pfad
                self.rufe("/api/fsr/config", {"marke": marke, "config": alt_config})
        self.assertEqual(geschrieben["fsr_passwort"],
                         self.anwendung.config.fsr_passwort)

    def test_config_wird_nicht_ungefragt_geschrieben(self):
        pfad = os.path.join(PROJEKT, "config.json")
        with open(pfad, "r", encoding="utf-8") as datei:
            vorher = datei.read()
        marke = self.marke()
        _, daten = self.rufe("/api/fsr/config", {"marke": marke})
        neu = json.loads(json.dumps(daten["config"]))
        neu["spiel"]["runden_laenge"] = 321
        try:
            self.rufe("/api/fsr/config", {"marke": marke, "config": neu})
            with open(pfad, "r", encoding="utf-8") as datei:
                self.assertEqual(datei.read(), vorher)
        finally:
            self.rufe("/api/fsr/config", {"marke": marke, "config": daten["config"]})

    def test_kein_ausbruch_aus_dem_statischen_ordner(self):
        adresse = "http://127.0.0.1:%d/../../config.json" % self.port
        try:
            with urllib.request.urlopen(adresse, timeout=10) as antwort:
                inhalt = antwort.read().decode("utf-8")
        except urllib.error.HTTPError as fehler:
            self.assertIn(fehler.code, (403, 404))
            return
        self.assertNotIn("fsr_passwort", inhalt)

    # ------------------------------------------------------------- Absicherung

    def test_nur_json_koerper_wird_angenommen(self):
        adresse = "http://127.0.0.1:%d/api/pruefen" % self.port
        anfrage = urllib.request.Request(
            adresse, data=b"quelltext=warte", headers={"Content-Type": "text/plain"})
        with self.assertRaises(urllib.error.HTTPError) as gefangen:
            urllib.request.urlopen(anfrage, timeout=10)
        self.assertEqual(gefangen.exception.code, 415)

    def test_fremde_seite_darf_nichts_anfordern(self):
        status, daten = self.rufe(
            "/api/testlauf", {"quelltext": "ELSE warte"},
            kopfzeilen={"Origin": "http://boese.example"})
        self.assertEqual(status, 403)
        self.assertIn("fremden Seiten", daten["fehler"])

    def test_fremder_host_wird_abgelehnt(self):
        """DNS-Rebinding: Der Host muss auf den eigenen Rechner zeigen."""
        status, daten = self.rufe(
            "/api/testlauf", {"quelltext": "ELSE warte"},
            kopfzeilen={"Host": "boese.example"})
        self.assertEqual(status, 403)
        self.assertIn("fremden Seiten", daten["fehler"])

    def test_abgelaufene_marke_wird_entfernt(self):
        marke = self.marke()
        with self.anwendung.sperre:
            self.anwendung.fsr_marken[marke] = time.time() - 13 * 3600
        status, _ = self.rufe("/api/fsr/bots", {"marke": marke})
        self.assertEqual(status, 403)
        with self.anwendung.sperre:
            self.assertNotIn(marke, self.anwendung.fsr_marken)

    def test_nul_byte_im_pfad_meldet_400(self):
        adresse = "http://127.0.0.1:%d/%%00" % self.port
        try:
            with urllib.request.urlopen(adresse, timeout=10) as antwort:
                self.fail("Der Pfad hätte abgelehnt werden müssen (Status %d)."
                          % antwort.status)
        except urllib.error.HTTPError as fehler:
            self.assertEqual(fehler.code, 400)

    def test_falsche_methode_meldet_405(self):
        status, daten = self.rufe("/api/testlauf")
        self.assertEqual(status, 405)
        self.assertIn("fehler", daten)

    def test_passwort_kommt_nicht_ueber_die_schnittstelle(self):
        marke = self.marke()
        _, daten = self.rufe("/api/fsr/config", {"marke": marke})
        self.assertNotIn("fsr_passwort", daten["config"])
        self.assertIn("fsr_passwort", self.anwendung.config.als_dict())

    def test_config_schreiben_ist_atomar(self):
        with tempfile.TemporaryDirectory() as ordner:
            pfad = os.path.join(ordner, "config.json")
            with open(pfad, "w", encoding="utf-8") as datei:
                datei.write("alt")
            api.config_schreiben(pfad, {"a": 1})
            with open(pfad, "r", encoding="utf-8") as datei:
                self.assertEqual(json.load(datei), {"a": 1})
            self.assertEqual(os.listdir(ordner), ["config.json"])


if __name__ == "__main__":
    unittest.main()
