"""Aufzeichnungsformat.

Eine Aufzeichnung enthält alles, was der Browser zum Abspielen braucht — und keine
Regel, die er selbst anwenden müsste. Deshalb steht je Tick der vollständige
sichtbare Zustand darin, nicht nur die Änderungen.
"""

import json
import os
import tempfile

FORMAT_VERSION = 2

FARBEN = ["#3d8bfd", "#e8590c", "#2f9e44", "#ae3ec9"]


def aufzeichnung(spiel, anschluesse=None, titel=None, pfade=None):
    welt = spiel.welt
    spieler = []
    for r in welt.roboter:
        anschluss = anschluesse[r.index] if anschluesse and r.index < len(anschluesse) else None
        spieler.append({
            "index": r.index,
            "name": r.name,
            "pfad": (pfade[r.index] if pfade and r.index < len(pfade)
                     else (anschluss.pfad if anschluss else None)),
            "depot": [r.depot[0], r.depot[1]],
            "farbe": FARBEN[r.index % len(FARBEN)],
        })

    daten = {
        "version": FORMAT_VERSION,
        "titel": titel or " gegen ".join(s["name"] for s in spieler),
        "seed": welt.seed,
        "breite": welt.breite,
        "hoehe": welt.hoehe,
        "runden_laenge": spiel.runden_laenge,
        "kapazitaet": welt.kapazitaet,
        "sorten": {
            name: {
                "wert": spiel.config.muell.sorten[name].wert,
                "anzeige": (spiel.config.muell.sorten[name].anzeige
                            if "anzeige" in spiel.config.muell.sorten[name]
                            else name),
            }
            for name in sorted(spiel.config.muell.sorten.keys())
        },
        "radioaktiv": {
            "wert": spiel.config.radioaktiv.wert,
            "anzeige": (spiel.config.radioaktiv.anzeige
                        if "anzeige" in spiel.config.radioaktiv else "Radioaktives Fass"),
        },
        "zone_groesse": spiel.config.zone.groesse,
        "spieler": spieler,
        "start": spiel.start_abbild,
        "ticks": spiel.ticks,
        "ergebnis": spiel.ergebnis.als_dict() if spiel.ergebnis else None,
    }
    if anschluesse:
        daten["bots"] = [a.bericht() for a in anschluesse]
    return daten


def speichern(pfad, daten):
    """Schreibt über eine Temp-Datei — ein Abbruch lässt nie eine halbe Aufzeichnung."""
    ordner = os.path.dirname(os.path.abspath(pfad))
    if ordner:
        os.makedirs(ordner, exist_ok=True)
    griff, temp = tempfile.mkstemp(prefix="aufzeichnung_", suffix=".tmp", dir=ordner)
    try:
        with os.fdopen(griff, "w", encoding="utf-8") as datei:
            json.dump(daten, datei, ensure_ascii=False, separators=(",", ":"))
            datei.write("\n")
        os.replace(temp, pfad)
    except BaseException:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise
    return pfad


def laden(pfad):
    with open(pfad, "r", encoding="utf-8") as datei:
        daten = json.load(datei)
    version = daten.get("version") if isinstance(daten, dict) else None
    if version != FORMAT_VERSION:
        raise ValueError(
            "Aufzeichnung %s: unbekannte Formatversion %r (erwartet %d)."
            % (os.path.basename(pfad), version, FORMAT_VERSION))
    return daten
