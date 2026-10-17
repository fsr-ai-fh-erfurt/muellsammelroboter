"""Team-Logos: Erkennung neben der Bot-Datei und Auslieferung über `/logos/`.

Ein Logo liegt neben der Bot-Datei und trägt denselben Stamm. Der Server liefert
es ohne Marke aus — ein `<img>` kann keine mitschicken —, aber nur aus den beiden
Bot-Ordnern und nur mit erlaubter Bild-Endung. Die Tests schreiben ihre Dateien
nach `abgaben/` (von `.gitignore` erfasst) und räumen sie wieder weg.
"""

import json
import os
import struct
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zlib

from engine import spielleiter
from web import api
from web.server import Anwendung, server_bauen

PROJEKT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ABGABEN = os.path.join(PROJEKT, "abgaben")
BOT = "_logotest.py"
BILD = "_logotest.png"


def winziges_png():
    """Ein gültiges 1×1-PNG, aus Standardbibliothek gebaut — keine Magic Bytes."""
    def stueck(typ, daten):
        return (struct.pack(">I", len(daten)) + typ + daten
                + struct.pack(">I", zlib.crc32(typ + daten) & 0xffffffff))
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    roh = b"\x00" + b"\x00\x00\x00\x00"
    return (b"\x89PNG\r\n\x1a\n" + stueck(b"IHDR", ihdr)
            + stueck(b"IDAT", zlib.compress(roh)) + stueck(b"IEND", b""))


class TestLogoErkennung(unittest.TestCase):
    def test_findet_das_logo_neben_der_datei(self):
        with tempfile.TemporaryDirectory() as ordner:
            bot = os.path.join(ordner, "die_profis.py")
            open(bot, "w", encoding="utf-8").close()
            self.assertEqual(spielleiter.logo_neben(bot), "")
            with open(os.path.join(ordner, "die_profis.png"), "wb") as datei:
                datei.write(b"x")
            self.assertEqual(spielleiter.logo_neben(bot), "die_profis.png")

    def test_feste_reihenfolge_bei_mehreren_endungen(self):
        with tempfile.TemporaryDirectory() as ordner:
            bot = os.path.join(ordner, "team.py")
            open(bot, "w", encoding="utf-8").close()
            for name in ("team.gif", "team.jpg", "team.png"):
                open(os.path.join(ordner, name), "wb").close()
            self.assertEqual(spielleiter.logo_neben(bot), "team.png")

    def test_andere_dateien_gelten_nicht(self):
        with tempfile.TemporaryDirectory() as ordner:
            bot = os.path.join(ordner, "team.py")
            open(bot, "w", encoding="utf-8").close()
            for name in ("team.txt", "team.png.bak", "team2.png"):
                open(os.path.join(ordner, name), "wb").close()
            self.assertEqual(spielleiter.logo_neben(bot), "")

    def test_beschreibung_traegt_das_logo(self):
        with tempfile.TemporaryDirectory() as ordner:
            bot = os.path.join(ordner, "team.py")
            with open(bot, "w", encoding="utf-8") as datei:
                datei.write('NAME = "Team"\n')
            with open(os.path.join(ordner, "team.webp"), "wb") as datei:
                datei.write(b"x")
            eintrag = spielleiter.bot_beschreibung(bot)
            self.assertEqual(eintrag["logo"], "team.webp")
            self.assertNotIn(os.sep, eintrag["logo"])

    def test_ohne_logo_bleibt_das_feld_leer(self):
        with tempfile.TemporaryDirectory() as ordner:
            bot = os.path.join(ordner, "team.py")
            open(bot, "w", encoding="utf-8").close()
            self.assertEqual(spielleiter.bot_beschreibung(bot)["logo"], "")


class TestLogoAuslieferung(unittest.TestCase):
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

    def setUp(self):
        os.makedirs(ABGABEN, exist_ok=True)
        with open(os.path.join(ABGABEN, BOT), "w", encoding="utf-8") as datei:
            datei.write('NAME = "Logo-Team"\n\n\n'
                        'def entscheide(zustand):\n    return "warte"\n')
        with open(os.path.join(ABGABEN, BILD), "wb") as datei:
            datei.write(winziges_png())

    def tearDown(self):
        for name in (BOT, BILD):
            try:
                os.remove(os.path.join(ABGABEN, name))
            except OSError:
                pass

    def rufe(self, pfad, daten=None):
        adresse = "http://127.0.0.1:%d%s" % (self.port, pfad)
        if daten is None:
            anfrage = urllib.request.Request(adresse)
        else:
            anfrage = urllib.request.Request(
                adresse, data=json.dumps(daten).encode("utf-8"),
                headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(anfrage, timeout=30) as antwort:
                return antwort.status, json.loads(antwort.read().decode("utf-8"))
        except urllib.error.HTTPError as fehler:
            return fehler.code, json.loads(fehler.read().decode("utf-8"))

    def hole(self, pfad):
        adresse = "http://127.0.0.1:%d%s" % (self.port, pfad)
        try:
            with urllib.request.urlopen(adresse, timeout=10) as antwort:
                return (antwort.status, antwort.headers.get("Content-Type"),
                        antwort.read())
        except urllib.error.HTTPError as fehler:
            return fehler.code, fehler.headers.get("Content-Type"), fehler.read()

    def marke(self):
        status, daten = self.rufe("/api/fsr/anmelden",
                                  {"passwort": self.anwendung.config.fsr_passwort})
        self.assertEqual(status, 200)
        return daten["marke"]

    def test_bots_liste_nennt_das_logo(self):
        status, daten = self.rufe("/api/fsr/bots", {"marke": self.marke()})
        self.assertEqual(status, 200)
        eintrag = [b for b in daten["abgaben"] if b["datei"] == BOT]
        self.assertEqual(len(eintrag), 1)
        self.assertEqual(eintrag[0]["logo"], BILD)

    def test_logo_wird_als_bild_ausgeliefert(self):
        status, typ, inhalt = self.hole("/logos/abgaben/%s" % BILD)
        self.assertEqual(status, 200)
        self.assertEqual(typ, "image/png")
        self.assertEqual(inhalt, winziges_png())

    def test_fehlendes_logo_meldet_404(self):
        status, _, _ = self.hole("/logos/abgaben/gibtsnicht.png")
        self.assertEqual(status, 404)

    def test_fremder_ordner_meldet_404(self):
        for pfad in ("/logos/static/style.css", "/logos/turnier/x.png",
                     "/logos/abgaben", "/logos/abgaben/", "/logos/"):
            status, _, _ = self.hole(pfad)
            self.assertEqual(status, 404, pfad)

    def test_nur_bild_endungen_kommen_durch(self):
        """Auch eine vorhandene Datei wird nicht ausgeliefert, wenn sie kein Bild ist."""
        status, _, _ = self.hole("/logos/abgaben/%s" % BOT)
        self.assertEqual(status, 404)
        status, _, inhalt = self.hole("/logos/abgaben/..%2f..%2fconfig.json")
        self.assertIn(status, (403, 404))
        self.assertNotIn(b"fsr_passwort", inhalt)

    def test_ausbruch_aus_dem_ordner_wird_abgelehnt(self):
        for pfad in ("/logos/abgaben/..%2f..%2fconfig.json",
                     "/logos/bots/..%2f..%2fconfig.json",
                     "/logos/abgaben/%2e%2e%2f%2e%2e%2fconfig.json"):
            status, _, inhalt = self.hole(pfad)
            self.assertIn(status, (403, 404), pfad)
            self.assertNotIn(b"fsr_passwort", inhalt)

    def test_ein_großes_logo_wird_abgelehnt(self):
        pfad = os.path.join(ABGABEN, "_logogross.png")
        with open(pfad, "wb") as datei:
            datei.seek(5 * 1024 * 1024)
            datei.write(b"\0")
        try:
            status, _, _ = self.hole("/logos/abgaben/_logogross.png")
            self.assertEqual(status, 413)
        finally:
            os.remove(pfad)


if __name__ == "__main__":
    unittest.main()
