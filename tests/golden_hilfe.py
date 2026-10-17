"""Golden Tests: fester Seed, feste Bots, feste Rundenzahl, fester Endstand.

Jedes Szenario friert die Konfiguration mit ein, mit der es aufgenommen wurde. So
schlagen die Golden Tests bei Engine-Änderungen an, aber nicht bei jeder
Balance-Schraube in der config.json — dafür gibt es balance.py.

Neu aufnehmen (nur nach einer BEWUSSTEN Regeländerung):
    python3 -m tests.run --golden-neu
"""

import hashlib
import json
import os
import tempfile

from engine import config as config_modul
from engine.game import Spiel
from engine.runner import Anschlussgruppe

ORDNER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden")
PROJEKT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SZENARIEN_DATEI = os.path.join(ORDNER, "szenarien.json")


def szenarien():
    with open(SZENARIEN_DATEI, "r", encoding="utf-8") as datei:
        return json.load(datei)


def datei_von(name):
    return os.path.join(ORDNER, name + ".json")


def pruefsumme(spiel):
    """Über den kompletten Spielverlauf, nicht nur über den Endstand."""
    roh = json.dumps(spiel.ticks, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(roh).hexdigest()


def spielen(szenario, config):
    pfade = [os.path.join(PROJEKT, p) for p in szenario["bots"]]
    with Anschlussgruppe(pfade, config) as anschluesse:
        spiel = Spiel(config, anschluesse, seed=szenario["seed"],
                      spieler=szenario.get("spieler"),
                      runden_laenge=szenario["ticks"])
        spiel.spiele()
        for anschluss in anschluesse:
            if anschluss.fehler:
                raise AssertionError(
                    "Golden-Szenario %r: Bot %s hatte Probleme: %s"
                    % (szenario["name"], anschluss.name, anschluss.fehler[0]))
        return spiel


def erwartung(spiel):
    return {
        "punkte": [r["punkte"] for r in spiel.ergebnis.roboter],
        "akku": [r["akku"] for r in spiel.ergebnis.roboter],
        "abgeliefert": [r["statistik"]["abgeliefert_stueck"] for r in spiel.ergebnis.roboter],
        "positionen": [[r.x, r.y] for r in spiel.welt.roboter],
        "sieger": spiel.ergebnis.sieger,
        "unentschieden": spiel.ergebnis.unentschieden,
        "pruefsumme": pruefsumme(spiel),
    }


def aufnehmen(nur=None, config_neu=False):
    """Nimmt alle (oder ein) Szenario neu auf. Gibt die Namen zurück.

    `config_neu` übernimmt zusätzlich die aktuelle config.json in das Szenario —
    nötig, wenn sich die Zahlenwerte bewusst geändert haben.

    Erst werden alle Spiele gespielt, dann wird geschrieben. Bricht eines ab oder
    gibt es das per `--nur` gewählte Szenario nicht, bleibt der alte Stand auf der
    Platte unangetastet.
    """
    alle = szenarien()
    if nur is not None:
        ausgewaehlt = [s for s in alle if s["name"] == nur]
        if not ausgewaehlt:
            bekannt = ", ".join(s["name"] for s in alle)
            raise ValueError(
                "Das Golden-Szenario %r gibt es nicht. Bekannt sind: %s"
                % (nur, bekannt))
    else:
        ausgewaehlt = alle

    aufgenommen = []
    vorbereitet = []
    for szenario in ausgewaehlt:
        pfad = datei_von(szenario["name"])
        if os.path.exists(pfad) and not config_neu:
            with open(pfad, "r", encoding="utf-8") as datei:
                alt = json.load(datei)
            config_daten = alt["config"]
        else:
            config_daten = config_modul.lade().als_dict()
        config = config_modul.aus_dict(config_daten)
        spiel = spielen(szenario, config)
        vorbereitet.append((pfad, {
            "szenario": szenario,
            "config": config_daten,
            "erwartet": erwartung(spiel),
        }))
        aufgenommen.append(szenario["name"])

    tempdateien = []
    try:
        for pfad, inhalt in vorbereitet:
            tempdateien.append((_temp_schreiben(pfad, inhalt), pfad))
        for tempdatei, pfad in tempdateien:
            os.replace(tempdatei, pfad)
    except BaseException:
        for tempdatei, _ in tempdateien:
            try:
                os.unlink(tempdatei)
            except OSError:
                pass
        raise
    return aufgenommen


def _temp_schreiben(pfad, inhalt):
    """Schreibt das Ergebnis neben die Zieldatei — `os.replace` tauscht sie dann atomar."""
    griff, tempdatei = tempfile.mkstemp(
        dir=os.path.dirname(pfad), prefix=".golden-", suffix=".tmp")
    try:
        with os.fdopen(griff, "w", encoding="utf-8") as datei:
            json.dump(inhalt, datei, ensure_ascii=False, indent=2, sort_keys=True)
            datei.write("\n")
    except BaseException:
        try:
            os.unlink(tempdatei)
        except OSError:
            pass
        raise
    return tempdatei
