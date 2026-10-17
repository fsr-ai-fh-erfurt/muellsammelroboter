"""Elternseite der Bot-Prozesse: starten, fragen, Zeitlimit, Neustart.

Jeder Bot läuft in einem eigenen Prozess — in der Werkstatt genauso wie im Turnier.
Eine Endlosschleife im Studi-Bot kostet ihn seine Züge, sonst nichts.

Bewusst Lesethreads statt select(): so bleibt der Code auch unter Windows gültig.
"""

import json
import os
import queue
import signal
import subprocess
import sys
import threading
import time

PROJEKT_ORDNER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MELDUNGEN_MAX = 200


class BotAnschluss:
    """Ein Bot in einem eigenen Prozess."""

    def __init__(self, pfad, config, name=None):
        self.pfad = os.path.abspath(pfad)
        self.config = config
        self.wunschname = name
        self.name = name or os.path.splitext(os.path.basename(self.pfad))[0]
        self.zeitlimit = config.bots.zeitlimit_ms / 1000.0
        self.start_zeitlimit = config.bots.start_zeitlimit_ms / 1000.0
        self.meldungen = []          # print()-Ausgaben des Bots
        self.fehler = []             # Abstürze und Startfehler
        self.tot = False
        self.statistik = {"ueberzogen": 0, "abstuerze": 0, "neustarts": 0}
        self._nr = 0
        self._folge_ueberzogen = 0
        self._neustarts = 0
        self._prozess = None
        self._schlange = None
        self._schreib_schlange = None
        self._starten()

    # ------------------------------------------------------------------ Prozess

    def _starten(self):
        self._schlange = queue.Queue()
        self._schreib_schlange = queue.Queue()
        try:
            self._prozess = subprocess.Popen(
                [sys.executable, "-u", "-m", "engine.bot_host", self.pfad],
                cwd=PROJEKT_ORDNER,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
                start_new_session=(os.name != "nt"),
            )
        except OSError as fehler:
            self._notieren_fehler("Der Bot-Prozess ließ sich nicht starten: %s" % fehler)
            self.tot = True
            return
        prozess = self._prozess
        threading.Thread(target=self._stdout_lesen, args=(prozess, self._schlange),
                         daemon=True).start()
        threading.Thread(target=self._stderr_lesen, args=(prozess,), daemon=True).start()
        threading.Thread(target=self._stdin_schreiben,
                         args=(prozess, self._schreib_schlange), daemon=True).start()

        frist = time.monotonic() + self.start_zeitlimit
        while True:
            rest = frist - time.monotonic()
            if rest <= 0:
                self._notieren_fehler(
                    "Der Bot hat beim Start länger als %d ms gebraucht."
                    % self.config.bots.start_zeitlimit_ms)
                self._toeten()
                self.tot = True
                return
            try:
                nachricht = self._schlange.get(timeout=rest)
            except queue.Empty:
                continue
            if nachricht is None:
                self._notieren_fehler("Der Bot-Prozess hat sich beim Start beendet.")
                self.tot = True
                return
            if nachricht.get("nr") == 0:
                if nachricht.get("fehler"):
                    self._notieren_fehler(nachricht["fehler"])
                if not nachricht.get("bereit"):
                    self.tot = True
                    return
                if self.wunschname is None and nachricht.get("name"):
                    self.name = nachricht["name"]
                return

    def _stdout_lesen(self, prozess, schlange):
        try:
            for zeile in prozess.stdout:
                zeile = zeile.strip()
                if not zeile:
                    continue
                try:
                    schlange.put(json.loads(zeile))
                except ValueError:
                    self._notieren_meldung(zeile)
        except Exception:
            pass
        finally:
            schlange.put(None)

    def _stdin_schreiben(self, prozess, schlange):
        """Ein eigener Thread je Prozess: ein blockierender Schreibvorgang darf
        weder das Zeitlimit aushebeln noch den Aufräumpfad aufhängen."""
        try:
            while True:
                auftrag = schlange.get()
                if auftrag is None:
                    return
                text, fertig, fehler = auftrag
                try:
                    prozess.stdin.write(text)
                    prozess.stdin.flush()
                except (BrokenPipeError, ValueError, OSError) as grund:
                    fehler.append(grund)
                finally:
                    fertig.set()
        except Exception:
            pass

    def _schreiben(self, text, frist):
        """Schreibt höchstens bis `frist`. 'ok', 'zeit' oder 'fehler'."""
        if self._prozess is None:
            return "fehler"
        fertig = threading.Event()
        fehler = []
        self._schreib_schlange.put((text, fertig, fehler))
        if not fertig.wait(max(0.0, frist - time.monotonic())):
            return "zeit"
        return "fehler" if fehler else "ok"

    def _stderr_lesen(self, prozess):
        try:
            for zeile in prozess.stderr:
                self._notieren_meldung(zeile.rstrip("\n"))
        except Exception:
            pass

    def _notieren_meldung(self, text):
        if len(self.meldungen) < MELDUNGEN_MAX:
            self.meldungen.append(text)
        elif len(self.meldungen) == MELDUNGEN_MAX:
            self.meldungen.append("... weitere Ausgaben werden nicht mehr angezeigt.")

    def _notieren_fehler(self, text):
        if len(self.fehler) < 20:
            self.fehler.append(text)

    def _toeten(self):
        prozess = self._prozess
        self._prozess = None
        if self._schreib_schlange is not None:
            self._schreib_schlange.put(None)
        if prozess is None:
            return
        try:
            if os.name != "nt":
                os.killpg(os.getpgid(prozess.pid), signal.SIGKILL)
            else:
                prozess.kill()
        except Exception:
            try:
                prozess.kill()
            except Exception:
                pass
        try:
            prozess.wait(timeout=2)
        except Exception:
            pass
        # Pipes schließen: bei tausenden Matches in balance.py gingen sonst die
        # Dateideskriptoren aus.
        for kanal in (prozess.stdin, prozess.stdout, prozess.stderr):
            try:
                if kanal is not None:
                    kanal.close()
            except Exception:
                pass

    def _neu_starten(self, grund):
        self._notieren_fehler(grund)
        self.statistik["abstuerze"] += 1
        self._toeten()
        self._folge_ueberzogen = 0
        if self._neustarts >= self.config.bots.neustarts_max:
            self.tot = True
            self._notieren_fehler(
                "Nach %d Neustarts gibt der Roboter auf und wartet bis zum Rundenende."
                % self._neustarts)
            return
        self._neustarts += 1
        self.statistik["neustarts"] += 1
        self._starten()

    # ------------------------------------------------------------------ Spiel

    def frage(self, sicht):
        """Gibt (aktion, regel) zurück. Bei jedem Problem: ('warte', None)."""
        if self.tot or self._prozess is None:
            return ("warte", None)
        self._nr += 1
        nr = self._nr
        frist = time.monotonic() + self.zeitlimit
        text = json.dumps({"nr": nr, "sicht": sicht}, ensure_ascii=False) + "\n"
        zustand = self._schreiben(text, frist)
        if zustand == "fehler":
            self._neu_starten("Der Bot-Prozess ist abgestürzt.")
            return ("warte", None)
        if zustand == "zeit":
            return self._ueberzogen()

        while True:
            rest = frist - time.monotonic()
            if rest <= 0:
                break
            try:
                nachricht = self._schlange.get(timeout=rest)
            except queue.Empty:
                break
            if nachricht is None:
                self._neu_starten("Der Bot-Prozess hat sich mitten im Spiel beendet.")
                return ("warte", None)
            if nachricht.get("nr") != nr:
                continue            # verspätete Antwort auf einen früheren Zug
            self._folge_ueberzogen = 0
            if nachricht.get("fehler"):
                self._notieren_fehler(nachricht["fehler"])
            aktion = nachricht.get("aktion")
            regel = nachricht.get("regel")
            return (
                aktion if isinstance(aktion, str) else "warte",
                regel if isinstance(regel, int) else None,
            )

        return self._ueberzogen()

    def _ueberzogen(self):
        """Ein Zug hat das Zeitlimit gerissen — oder das Schreiben hing fest."""
        self.statistik["ueberzogen"] += 1
        self._folge_ueberzogen += 1
        if self._folge_ueberzogen >= self.config.bots.kill_nach_ueberzogen:
            self._neu_starten(
                "Der Bot hat %d Züge hintereinander das Zeitlimit von %d ms überschritten "
                "— sehr wahrscheinlich eine Endlosschleife."
                % (self._folge_ueberzogen, self.config.bots.zeitlimit_ms))
        return ("warte", None)

    def beenden(self):
        if self._prozess is None:
            return
        self._schreiben(json.dumps({"ende": True}) + "\n", time.monotonic() + 0.5)
        try:
            self._prozess.wait(timeout=0.5)
        except Exception:
            pass
        self._toeten()

    def bericht(self):
        return {
            "name": self.name,
            "pfad": self.pfad,
            "tot": self.tot,
            "meldungen": list(self.meldungen),
            "fehler": list(self.fehler),
            "statistik": dict(self.statistik),
        }


class Anschlussgruppe:
    """Kontextmanager, damit Prozesse auch bei Fehlern wieder eingesammelt werden."""

    def __init__(self, pfade, config, namen=None):
        self.anschluesse = []
        try:
            for i, pfad in enumerate(pfade):
                name = namen[i] if namen and i < len(namen) else None
                self.anschluesse.append(BotAnschluss(pfad, config, name=name))
        except BaseException:
            for anschluss in self.anschluesse:
                anschluss.beenden()
            raise

    def __enter__(self):
        return self.anschluesse

    def __exit__(self, *_):
        for anschluss in self.anschluesse:
            anschluss.beenden()
        return False
