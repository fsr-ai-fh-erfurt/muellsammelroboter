"""Lokaler Webserver — nur Standardbibliothek.

Der Browser bekommt hier ausschließlich Dateien und JSON. Jede Spielregel läuft in
Python. Wenn hier eine Route auftaucht, die etwas *entscheidet* statt etwas
*auszuliefern*, gehört die Logik in engine/.
"""

import json
import mimetypes
import os
import posixpath
import secrets
import sys
import threading
import time
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from engine import config as config_modul
from engine import spielleiter

STATISCH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

MARKEN_FRIST = 12 * 3600            # Sekunden, dann muss sich der FSR neu anmelden
KOERPER_MAX = 5 * 1024 * 1024       # größere Anfragen sind immer ein Fehler
LOGO_MAX = 5 * 1024 * 1024          # ein Team-Logo ist ein Bild, kein Datenpaket
# Nur diese beiden Ordner geben Bilder heraus — keine anderen Pfade des Projekts.
LOGO_ORDNER = {"abgaben": spielleiter.ABGABEN_ORDNER, "bots": spielleiter.BOT_ORDNER}
AUFGABEN_MAX = 50                   # ältere Aufgabenergebnisse werden vergessen
AUFGABEN_PARALLEL_MAX = 4           # so viele Hintergrundaufgaben dürfen gleichzeitig laufen
LOKALE_HOSTS = ("127.0.0.1", "localhost", "::1")


class Antwort(Exception):
    """Abbruch mit einem bestimmten Status und einer deutschen Meldung."""

    def __init__(self, status, meldung):
        super().__init__(meldung)
        self.status = status
        self.meldung = meldung


class Anwendung:
    """Hält den Zustand des Servers: Konfiguration, Routen, laufende Aufgaben."""

    def __init__(self, config_pfad=None):
        self.config_pfad = config_pfad or config_modul.STANDARD_PFAD
        self.config = config_modul.lade(self.config_pfad)
        self.sperre = threading.Lock()
        self.routen = {}
        self.aufgaben = {}
        self.aufgaben_zaehler = 0
        self.fsr_marken = {}        # Marke -> Ausgabezeitpunkt

    def route(self, pfad, methoden=("POST",)):
        def merker(funktion):
            for methode in methoden:
                self.routen[(pfad, methode)] = funktion
            return funktion
        return merker

    def marke_anlegen(self):
        marke = secrets.token_hex(8)
        jetzt = time.time()
        with self.sperre:
            self.fsr_marken = {m: t for m, t in self.fsr_marken.items()
                               if jetzt - t <= MARKEN_FRIST}
            self.fsr_marken[marke] = jetzt
        return marke

    def marke_gueltig(self, marke):
        if not isinstance(marke, str):
            return False
        # Unter der Sperre lesen: `marke_anlegen` ersetzt das Dict, und zwischen
        # Prüfen und Zugriff darf der Eintrag nicht verschwinden.
        with self.sperre:
            zeitpunkt = self.fsr_marken.get(marke)
            if zeitpunkt is None:
                return False
            if time.time() - zeitpunkt > MARKEN_FRIST:
                del self.fsr_marken[marke]
                return False
        return True

    def config_setzen(self, daten):
        config = config_modul.aus_dict(daten)
        with self.sperre:
            self.config = config
        return config

    # -------------------------------------------------------------- Aufgaben

    def aufgabe_starten(self, beschreibung, arbeit):
        """Startet eine länger laufende Aufgabe (Turnier, Balance) im Hintergrund."""
        with self.sperre:
            laufend = sum(1 for a in self.aufgaben.values() if not a["fertig"])
            if laufend >= AUFGABEN_PARALLEL_MAX:
                raise Antwort(429, "Es laufen schon zu viele Aufgaben. Bitte kurz warten.")
            self.aufgaben_zaehler += 1
            nummer = self.aufgaben_zaehler
        eintrag = {
            "id": nummer,
            "beschreibung": beschreibung,
            "fertig": False,
            "fortschritt": 0,
            "gesamt": 0,
            "meldung": "läuft ...",
            "ergebnis": None,
            "fehler": None,
        }
        with self.sperre:
            self.aufgaben[nummer] = eintrag
            if len(self.aufgaben) > AUFGABEN_MAX:
                # Nur fertige Einträge verdrängen — ein laufender Job muss abrufbar
                # bleiben, sonst antwortet `/api/fsr/aufgabe` mitten im Lauf mit 404.
                fertige = sorted(a for a, e in self.aufgaben.items() if e["fertig"])
                for alt in fertige[:len(self.aufgaben) - AUFGABEN_MAX]:
                    del self.aufgaben[alt]

        def melden(fortschritt, gesamt, meldung=None):
            eintrag["fortschritt"] = fortschritt
            eintrag["gesamt"] = gesamt
            if meldung:
                eintrag["meldung"] = meldung

        def laufen():
            try:
                eintrag["ergebnis"] = arbeit(melden)
                eintrag["meldung"] = "fertig"
            except Exception as fehler:
                sys.stderr.write("Aufgabe %d (%s) ist gescheitert:\n%s"
                                 % (nummer, beschreibung, traceback.format_exc()))
                eintrag["fehler"] = "Unerwarteter Fehler: %s" % type(fehler).__name__
                eintrag["meldung"] = "abgebrochen"
            finally:
                eintrag["fertig"] = True

        threading.Thread(target=laufen, daemon=True).start()
        return eintrag


class Behandler(BaseHTTPRequestHandler):
    server_version = "Muellsammler"
    anwendung = None
    timeout = 15                      # ein hängender Browser blockiert keinen Faden ewig

    def log_message(self, format, *args):
        pass                                   # keine Zugriffsprotokolle in der Konsole

    # -------------------------------------------------------------- Werkzeug

    def _senden(self, status, koerper, typ="application/json; charset=utf-8"):
        if isinstance(koerper, str):
            koerper = koerper.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(koerper)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(koerper)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, daten, status=200):
        self._senden(status, json.dumps(daten, ensure_ascii=False), )

    def _fehler(self, status, meldung):
        self._json({"fehler": meldung}, status=status)

    def _herkunft_ist_lokal(self):
        """Fremde Seiten dürfen nichts anstoßen — ohne Origin gilt es als lokal.

        Das ist nur zusammen mit der Host-Prüfung sicher: Ein Browser schickt den
        Origin nicht immer mit, den Host aber immer.
        """
        herkunft = self.headers.get("Origin")
        if not herkunft:
            return True
        zerlegt = urllib.parse.urlparse(herkunft)
        return zerlegt.hostname in LOKALE_HOSTS

    def _host_ist_lokal(self):
        """DNS-Rebinding: Der Host-Header muss auf diesen Rechner zeigen."""
        host = (self.headers.get("Host") or "").strip().lower()
        if not host:
            return False
        if host.startswith("["):                # IPv6 in Klammern, z.B. [::1]:8000
            name = host[1:].split("]")[0]
        else:
            name = host.rsplit(":", 1)[0]
        return name in LOKALE_HOSTS

    def _koerper_lesen(self):
        typ = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if typ != "application/json":
            raise Antwort(415, "Erwartet wird der Content-Type application/json.")
        try:
            laenge = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise Antwort(400, "Ungültige Content-Length.")
        if laenge < 0:
            raise Antwort(400, "Ungültige Content-Length.")
        if laenge > KOERPER_MAX:
            raise Antwort(413, "Die Anfrage ist zu groß.")
        if laenge == 0:
            return {}
        roh = self.rfile.read(laenge)
        try:
            return json.loads(roh.decode("utf-8"))
        except ValueError:
            raise Antwort(400, "Die Anfrage war kein gültiges JSON.")

    # -------------------------------------------------------------- Routen

    def do_GET(self):
        pfad = urllib.parse.urlparse(self.path).path
        if pfad.startswith("/api/"):
            self._api(pfad, "GET")
        elif pfad.startswith("/logos/"):
            self._logo(pfad)
        else:
            self._datei(pfad)

    def do_POST(self):
        pfad = urllib.parse.urlparse(self.path).path
        if pfad.startswith("/api/"):
            if not (self._host_ist_lokal() and self._herkunft_ist_lokal()):
                self._fehler(403, "Anfragen von fremden Seiten sind nicht erlaubt.")
                return
            self._api(pfad, "POST")
        else:
            self._fehler(404, "Unbekannte Adresse.")

    def do_PUT(self):
        self._fehler(405, "Diese Methode wird nicht unterstützt.")

    do_DELETE = do_PATCH = do_OPTIONS = do_PUT

    def _api(self, pfad, methode):
        funktion = self.anwendung.routen.get((pfad, methode))
        if funktion is None:
            bekannt = any(p == pfad for p, _ in self.anwendung.routen)
            if bekannt:
                self._fehler(405, "Diese Adresse gibt es nur mit einer anderen Methode.")
            else:
                self._fehler(404, "Unbekannte Schnittstelle: %s" % pfad)
            return
        try:
            daten = self._koerper_lesen() if methode == "POST" else \
                dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
            ergebnis = funktion(self.anwendung, daten)
            self._json(ergebnis)
        except Antwort as antwort:
            self._fehler(antwort.status, antwort.meldung)
        except Exception:
            sys.stderr.write(traceback.format_exc(limit=8))
            self._fehler(500, "Im Server ist etwas schiefgegangen.")

    def _datei(self, pfad):
        if pfad in ("", "/"):
            pfad = "/index.html"
        sicher = posixpath.normpath(urllib.parse.unquote(pfad)).lstrip("/")
        try:
            basis = os.path.realpath(STATISCH)
            ziel = os.path.realpath(os.path.join(STATISCH, sicher))
        except (OSError, ValueError):
            # z.B. ein NUL-Byte im Pfad — `realpath` wirft dann ValueError.
            self._fehler(400, "Ungültiger Dateiname.")
            return
        if ziel != basis and not ziel.startswith(basis + os.sep):
            self._fehler(403, "Nicht erlaubt.")
            return
        try:
            with open(ziel, "rb") as datei:
                inhalt = datei.read()
        except OSError:
            self._fehler(404, "Datei nicht gefunden: %s" % sicher)
            return
        typ, _ = mimetypes.guess_type(ziel)
        self._senden(200, inhalt, typ or "application/octet-stream")

    def _logo(self, pfad):
        """Ein Team-Logo ausliefern: `/logos/abgaben/<datei>` oder `/logos/bots/<datei>`.

        Ohne Marke: Ein `<img>` kann keine mitschicken. Es verlassen ausschließlich
        Bilddateien mit erlaubter Endung diese beiden Ordner, geprüft über
        `realpath` wie bei den statischen Dateien.
        """
        teile = urllib.parse.unquote(pfad).split("/")
        if len(teile) != 4 or not teile[3]:
            self._fehler(404, "Dieses Logo gibt es nicht.")
            return
        basis = LOGO_ORDNER.get(teile[2])
        datei = teile[3]
        if basis is None or datei != posixpath.basename(datei):
            self._fehler(404, "Dieses Logo gibt es nicht.")
            return
        if os.path.splitext(datei)[1].lower() not in spielleiter.LOGO_ENDUNGEN:
            self._fehler(404, "Dieses Logo gibt es nicht.")
            return
        try:
            wurzel = os.path.realpath(basis)
            ziel = os.path.realpath(os.path.join(basis, datei))
        except (OSError, ValueError):
            self._fehler(400, "Ungültiger Dateiname.")
            return
        if ziel != wurzel and not ziel.startswith(wurzel + os.sep):
            self._fehler(403, "Nicht erlaubt.")
            return
        try:
            if os.path.getsize(ziel) > LOGO_MAX:
                self._fehler(413, "Dieses Logo ist zu groß.")
                return
            with open(ziel, "rb") as bild:
                inhalt = bild.read(LOGO_MAX + 1)
        except OSError:
            self._fehler(404, "Dieses Logo gibt es nicht.")
            return
        if len(inhalt) > LOGO_MAX:
            self._fehler(413, "Dieses Logo ist zu groß.")
            return
        typ, _ = mimetypes.guess_type(ziel)
        self._senden(200, inhalt, typ or "application/octet-stream")


def server_bauen(anwendung, port):
    behandler = type("GebundenerBehandler", (Behandler,), {"anwendung": anwendung})
    return ThreadingHTTPServer(("127.0.0.1", port), behandler)
