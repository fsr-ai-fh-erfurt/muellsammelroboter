"""Ein Match von außen anstoßen — von der Werkstatt, vom Turnier, von balance.py.

Hier läuft immer derselbe Weg: Prozesse starten, Runde spielen, Aufzeichnung bauen.
Damit gibt es zwischen Testlauf und Turnier keinen Unterschied.
"""

import os
import re

from . import recording
from .game import Spiel
from .runner import Anschlussgruppe

PROJEKT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOT_ORDNER = os.path.join(PROJEKT, "bots")
ABGABEN_ORDNER = os.path.join(PROJEKT, "abgaben")

# Ein Team-Logo liegt neben der Bot-Datei und trägt denselben Stamm. Die
# Reihenfolge ist fest, damit dieselbe Ablage immer dasselbe Bild ergibt.
LOGO_ENDUNGEN = (".png", ".jpg", ".jpeg", ".webp", ".gif")


def logo_neben(pfad):
    """Der Dateiname des Logos neben einer Bot-Datei, sonst leer.

    Reines Nachsehen im Dateisystem: keine Spiellogik, kein Zufall, keine
    Ausführung. Liegen mehrere Endungen bereit, gewinnt die erste in
    `LOGO_ENDUNGEN`.
    """
    stamm = os.path.splitext(pfad)[0]
    for endung in LOGO_ENDUNGEN:
        kandidat = stamm + endung
        if os.path.isfile(kandidat):
            return os.path.basename(kandidat)
    return ""


def bot_beschreibung(pfad):
    """Liest NAME und BESCHREIBUNG aus einer Bot-Datei, ohne sie auszuführen."""
    name = os.path.splitext(os.path.basename(pfad))[0]
    beschreibung = ""
    massstab = True
    try:
        with open(pfad, "r", encoding="utf-8", errors="replace") as datei:
            for zeile in datei.read().splitlines()[:80]:
                # Nur Zuweisungen ganz links: `NAME = NAME` im Klassenrumpf ist keine.
                if zeile[:1].isspace():
                    continue
                if zeile.startswith("BALANCE_MASSSTAB = "):
                    massstab = "nein" not in zeile.lower()
                for schluessel, ziel in (("NAME", "name"), ("BESCHREIBUNG", "beschreibung")):
                    anfang = schluessel + " = "
                    if not zeile.startswith(anfang):
                        continue
                    roh = zeile[len(anfang):].strip()
                    if roh[:1] not in ('"', "'"):
                        continue
                    wert = roh.strip('"').strip("'")
                    if ziel == "name":
                        name = wert
                    else:
                        beschreibung = wert
    except OSError:
        pass
    return {"name": name, "beschreibung": beschreibung, "massstab": massstab,
            "datei": os.path.basename(pfad), "pfad": pfad, "logo": logo_neben(pfad)}


def ist_bot_datei(pfad):
    """Erkennt Bot-Dateien am `entscheide`, so wie `bot_host._bot_finden` sucht.

    Teams legen gelegentlich Hilfsmodule neben ihre Abgabe. Die sollen nicht als
    startklare Roboter in Listen und Turnieren landen — sie spielen sonst nur
    `warte` und zählen in der Balance als dauerhaft kaputt.
    """
    try:
        with open(pfad, "r", encoding="utf-8") as datei:
            quelle = datei.read()
    except (OSError, UnicodeDecodeError):
        return False
    return bool(re.search(r"def\s+entscheide\b|\bentscheide\s*=", quelle))


def bots_auflisten(ordner):
    if not os.path.isdir(ordner):
        return []
    dateien = sorted(f for f in os.listdir(ordner) if f.endswith(".py"))
    pfade = (os.path.join(ordner, f) for f in dateien)
    return [bot_beschreibung(p) for p in pfade if ist_bot_datei(p)]


def mitgelieferte_gegner():
    return bots_auflisten(BOT_ORDNER)


def match(config, pfade, seed=1, ticks=None, spieler=None, namen=None, titel=None):
    """Spielt eine Runde und gibt die vollständige Aufzeichnung zurück."""
    with Anschlussgruppe(pfade, config, namen) as anschluesse:
        spiel = Spiel(config, anschluesse, seed=seed, spieler=spieler, runden_laenge=ticks)
        spiel.spiele()
        return recording.aufzeichnung(spiel, anschluesse, titel=titel, pfade=pfade)


def nur_ergebnis(config, pfade, seed=1, ticks=None, spieler=None, namen=None):
    """Wie match(), gibt aber nur den Endstand zurück — für balance.py und Turniere.

    Ohne Aufzeichnung: keiner der Aufrufer braucht die Ticks, und bei hunderten
    Spielen hintereinander summiert sich das Abbilden jedes Ticks.
    """
    with Anschlussgruppe(pfade, config, namen) as anschluesse:
        spiel = Spiel(config, anschluesse, seed=seed, spieler=spieler, runden_laenge=ticks,
                      aufzeichnen=False)
        spiel.spiele()
        ergebnis = spiel.ergebnis.als_dict()
        ergebnis["bots"] = [
            {"name": a.name, "tot": a.tot, "statistik": a.statistik,
             "fehler": a.fehler[:2]}
            for a in anschluesse
        ]
        return ergebnis
