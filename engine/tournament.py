"""Gruppenphase und K.-o.-Runden.

Alle Ergebnisse sind reproduzierbar: jede Partie bekommt ihren Seed aus einem
festen Turnier-Seed, damit ein Turnier bei Bedarf exakt wiederholbar ist.
"""

import json
import os
import threading
import time

from . import spielleiter
from .rng import Zufall

PROJEKT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TURNIER_ORDNER = os.path.join(PROJEKT, "turnier")
SPEICHER_SPERRE = threading.Lock()


def partie_seed(turnier_seed, runde, nummer):
    """Fester Seed je Partie — gleiches Turnier, gleicher Verlauf."""
    return (turnier_seed * 1000003 + runde * 7919 + nummer * 104729) % (2 ** 31)


def duell(config, a, b, seed, ticks=None):
    """Ein Duell. Bei Gleichstand wird mit dem nächsten Seed wiederholt."""
    # Die tatsächlich gespielte Länge gehört ins Ergebnis: Die Bühne im FSR-Modus
    # spielt jede Partie aus dem Archiv mit `seed` und `ticks` nach. Ohne den Wert
    # hinge das Nachspiel an der gerade geladenen config.json.
    dauer = ticks if ticks is not None else config.spiel.runden_laenge
    versuche = []
    for versuch in range(config.turnier.gleichstand_wiederholungen + 1):
        ergebnis = spielleiter.nur_ergebnis(
            config, [a["pfad"], b["pfad"]], seed=seed + versuch, ticks=ticks,
            namen=[a["name"], b["name"]])
        versuche.append({
            "seed": seed + versuch,
            "punkte": [ergebnis["roboter"][0]["punkte"], ergebnis["roboter"][1]["punkte"]],
            "akku": [ergebnis["roboter"][0]["akku"], ergebnis["roboter"][1]["akku"]],
            "sieger": ergebnis["sieger"],
            "unentschieden": ergebnis["unentschieden"],
            "bots": ergebnis["bots"],
        })
        if not ergebnis["unentschieden"]:
            break
    letzter = versuche[-1]
    return {
        "a": a, "b": b,
        "seed": seed,
        "ticks": dauer,
        "wiederholungen": len(versuche) - 1,
        "spiele": versuche,
        "punkte": letzter["punkte"],
        "sieger": letzter["sieger"],
        "unentschieden": letzter["unentschieden"],
    }


# --------------------------------------------------------------------- Gruppen

def gruppe(config, bots, seed=1, ticks=None, melden=None):
    """Gruppenphase: alle vier gleichzeitig auf dem Feld, mehrere Runden.

    Vier Roboter spielen zusammen — nicht jeder gegen jeden einzeln. Das ist näher
    am späteren Turnierbild und deutlich schneller.

    Jede Runde startet eine andere Ecke: `bots` wird zyklisch verschoben, damit keine
    Startposition bevorzugt wird. Das `ergebnis` einer Partie ist in der rotierten
    Reihenfolge abgelegt; `partien[].rotation` nennt den Versatz. Platz `i` im
    Ergebnis gehört deshalb zum ursprünglichen Bot `(i + rotation) % len(bots)`.
    """
    anzahl = len(bots)
    runden = max(1, anzahl)
    punkte_je_platz = list(config.turnier.punkte_je_platz)
    tabelle = [{"name": b["name"], "datei": b["datei"], "punkte": 0, "spiele": 0,
                "siege": 0, "gesamtpunkte": 0, "unentschieden": 0} for b in bots]
    partien = []
    for runde in range(runden):
        bots_runde = bots[runde:] + bots[:runde]
        # Eigener Seedraum (Runde 0), getrennt von der ersten K.-o.-Runde (Runde 1).
        s = partie_seed(seed, 0, runde)
        versuche = 0
        while True:
            ergebnis = spielleiter.nur_ergebnis(
                config, [b["pfad"] for b in bots_runde], seed=s + versuche, ticks=ticks,
                namen=[b["name"] for b in bots_runde])
            if not ergebnis["unentschieden"]:
                break
            if versuche >= config.turnier.gleichstand_wiederholungen:
                break
            versuche += 1
        if ergebnis["unentschieden"]:
            ergebnis["entschieden_durch"] = "Gleichstand"
        partien.append({"seed": s, "ergebnis": ergebnis, "rotation": runde,
                        "wiederholungen": versuche})
        reihenfolge = ergebnis["reihenfolge"]
        for platz, index_runde in enumerate(reihenfolge):
            index = (index_runde + runde) % anzahl
            eintrag = tabelle[index]
            eintrag["spiele"] += 1
            eintrag["gesamtpunkte"] += ergebnis["roboter"][index_runde]["punkte"]
            # Ein dauerhafter Gleichstand gibt keine Tabellenpunkte: erst der
            # entschiedene Versuch zählt.
            if not ergebnis["unentschieden"]:
                eintrag["punkte"] += (punkte_je_platz[platz]
                                      if platz < len(punkte_je_platz) else 0)
                if platz == 0:
                    eintrag["siege"] += 1
        if ergebnis["unentschieden"]:
            for eintrag in tabelle:
                eintrag["unentschieden"] += 1
        if melden:
            melden(runde + 1, runden)

    # Gleichstand: erst Tabellenpunkte, dann Siege, dann Spielpunkte, zuletzt die
    # Startreihenfolge — dieselbe Reihenfolge, in der die Tabelle sie auch anzeigt.
    platzierung = sorted(range(len(tabelle)),
                         key=lambda i: (-tabelle[i]["punkte"], -tabelle[i]["siege"],
                                        -tabelle[i]["gesamtpunkte"], i))
    return {"art": "gruppe", "seed": seed, "tabelle": tabelle,
            "platzierung": platzierung, "partien": partien}


# --------------------------------------------------------------------- K.-o.

def setzliste(bots):
    """Die übliche Setzung in Bracket-Reihenfolge: (1, n), (8, 9), ...

    Die 0-basierte Platzfolge wird rekursiv verdoppelt; sie lautet für 16 Plätze
    0, 15, 7, 8, 3, 12, 4, 11, 1, 14, 6, 9, 2, 13, 5, 10. Freilose bekommen die
    höchsten Setzungen, zwei der besten treffen sich frühestens im Finale.
    """
    anzahl = len(bots)
    groesse = 1
    while groesse < anzahl:
        groesse *= 2
    reihe = [0]
    while len(reihe) < groesse:
        reihe = [x for paar in zip(reihe, [len(reihe) * 2 - 1 - s for s in reihe])
                 for x in paar]
    seeds = list(bots) + [None] * (groesse - anzahl)
    bracket = [seeds[i] for i in reihe]
    return [(bracket[2 * k], bracket[2 * k + 1]) for k in range(groesse // 2)]


def auslosen(bots, seed):
    """Die Setzliste per Los — und damit auch, wer ein Freilos bekommt.

    Vor dem Mischen wird nach Datei sortiert: Dieselbe Auswahl mit demselben Seed
    ergibt dieselbe Auslosung, egal in welcher Reihenfolge angeklickt wurde.
    Gemischt wird mit dem eigenen Zufallsgenerator (Fisher-Yates).
    """
    reihe = sorted(bots, key=lambda b: (b.get("kennung", ""), b.get("datei", ""),
                                        b.get("name", "")))
    zufall = Zufall(seed)
    for i in range(len(reihe) - 1, 0, -1):
        j = zufall.zahl(i + 1)
        reihe[i], reihe[j] = reihe[j], reihe[i]
    return reihe


def _ausgespielt(config, a, b, seed, rang, ticks):
    """Ein K.-o.-Duell samt Entscheidung bei dauerhaftem Gleichstand."""
    ergebnis = duell(config, a, b, seed, ticks)
    ergebnis["freilos"] = False
    if ergebnis["unentschieden"]:
        # Nach den Wiederholungen entscheidet der bessere Setzplatz, nicht die
        # Position im Baum — nach einem Upset ist `a` nicht zwingend besser.
        gewinner = a if rang[id(a)] < rang[id(b)] else b
        ergebnis["entschieden_durch"] = "Setzliste"
    else:
        gewinner = a if ergebnis["sieger"] == 0 else b
    ergebnis["sieger_bot"] = gewinner
    return ergebnis


def verlierer(partie):
    """Wer eine ausgespielte Partie verloren hat; bei einem Freilos niemand."""
    if partie.get("freilos"):
        return None
    return partie["b"] if partie["sieger_bot"] is partie["a"] else partie["a"]


def ko_runde(config, paare, seed, runde, rang, ticks=None, melden=None):
    partien = []
    weiter = []
    for nummer, (a, b) in enumerate(paare):
        if a is None and b is None:
            continue
        if b is None or a is None:
            durch = a or b
            partien.append({"a": a, "b": b, "freilos": True, "sieger_bot": durch})
            weiter.append(durch)
            continue
        ergebnis = _ausgespielt(config, a, b, partie_seed(seed, runde, nummer), rang, ticks)
        partien.append(ergebnis)
        weiter.append(ergebnis["sieger_bot"])
        if melden:
            melden(nummer + 1, len(paare))
    return partien, weiter


def ko_turnier(config, bots, seed=1, ticks=None, melden=None, losen=False):
    """K.-o.-Baum samt Spiel um Platz 3 und Podest.

    Mit `losen` wird die Setzliste aus dem Seed ausgelost, sonst ist die
    übergebene Reihenfolge die Setzliste. Das Spiel um Platz 3 bestreiten die
    beiden Verlierer des Halbfinales; hat das Halbfinale nur eine echte Partie
    (drei Roboter), ist deren Verlierer kampflos Dritter.
    """
    if losen:
        bots = auslosen(bots, seed)
    runden = []
    rang = {id(bot): i for i, bot in enumerate(bots)}
    paare = setzliste(bots)
    nummer = 1
    while paare:
        partien, weiter = ko_runde(config, paare, seed, nummer, rang, ticks, melden)
        runden.append({"nummer": nummer, "name": runden_name(len(weiter)), "partien": partien})
        if len(weiter) <= 1:
            break
        paare = [(weiter[i], weiter[i + 1] if i + 1 < len(weiter) else None)
                 for i in range(0, len(weiter), 2)]
        nummer += 1
    sieger = runden[-1]["partien"][-1]["sieger_bot"] if runden else None

    platz3 = None
    dritter = None
    if len(runden) >= 2:
        halbfinale = [verlierer(p) for p in runden[-2]["partien"]]
        halbfinale = [v for v in halbfinale if v is not None]
        if len(halbfinale) == 2:
            # Eigener Seedraum hinter dem Finale, damit keine Partie einen Seed teilt.
            platz3 = _ausgespielt(config, halbfinale[0], halbfinale[1],
                                  partie_seed(seed, nummer + 1, 0), rang, ticks)
            dritter = platz3["sieger_bot"]
        elif len(halbfinale) == 1:
            dritter = halbfinale[0]
    zweiter = verlierer(runden[-1]["partien"][-1]) if runden else None
    return {"art": "ko", "seed": seed, "ausgelost": bool(losen),
            "setzliste": list(bots), "runden": runden, "spiel_um_platz_3": platz3,
            "sieger": sieger, "podest": [sieger, zweiter, dritter]}


def runden_name(verbleibend):
    return {1: "Finale", 2: "Halbfinale", 4: "Viertelfinale",
            8: "Achtelfinale", 16: "Sechzehntelfinale"}.get(verbleibend,
                                                            "Runde der letzten %d" % verbleibend)


# --------------------------------------------------------------------- Ablage

def speichern(daten, art):
    """Legt ein Turnier kollisionsfrei und ohne halb geschriebene Dateien ab."""
    os.makedirs(TURNIER_ORDNER, exist_ok=True)
    with SPEICHER_SPERRE:
        stempel = time.strftime("%Y%m%d_%H%M%S")
        lauf = 0
        while True:
            zusatz = "" if lauf == 0 else "_%d" % lauf
            name = "%s%s_%s.json" % (stempel, zusatz, art)
            pfad = os.path.join(TURNIER_ORDNER, name)
            if not os.path.exists(pfad):
                break
            lauf += 1
        temp = pfad + ".tmp"
        with open(temp, "w", encoding="utf-8") as datei:
            json.dump(daten, datei, ensure_ascii=False, indent=1)
        os.replace(temp, pfad)
    return pfad


def zeit_aus_name(datei):
    """'20260907_232551_ko.json' -> '07.09.2026, 23:25 Uhr'. Leer, wenn es nicht passt."""
    teile = datei.split("_")
    if len(teile) < 2 or len(teile[0]) != 8 or len(teile[1]) != 6:
        return ""
    tag, uhr = teile[0], teile[1]
    if not (tag.isdigit() and uhr.isdigit()):
        return ""
    return "%s.%s.%s, %s:%s Uhr" % (tag[6:8], tag[4:6], tag[:4], uhr[:2], uhr[2:4])


def kurzfassung(pfad):
    """Die paar Zeilen, die im Archiv stehen — ohne die ganze Datei zu übertragen."""
    datei = os.path.basename(pfad)
    eintrag = {"datei": datei, "zeit": zeit_aus_name(datei), "art": "",
               "sieger": "", "teilnehmer": [], "runden": 0, "lesbar": True}
    try:
        with open(pfad, "r", encoding="utf-8") as offen:
            daten = json.load(offen)
    except (OSError, ValueError):
        eintrag["lesbar"] = False
        return eintrag
    if not isinstance(daten, dict):
        eintrag["lesbar"] = False
        return eintrag
    eintrag["art"] = daten.get("art", "")
    if eintrag["art"] == "ko":
        eintrag["sieger"] = (daten.get("sieger") or {}).get("name", "")
        eintrag["runden"] = len(daten.get("runden") or [])
        namen = []
        for runde in daten.get("runden") or []:
            for partie in runde.get("partien") or []:
                for seite in ("a", "b"):
                    bot = partie.get(seite)
                    if bot and bot.get("name") and bot["name"] not in namen:
                        namen.append(bot["name"])
        eintrag["teilnehmer"] = namen
        podest = daten.get("podest")
        if isinstance(podest, list):
            eintrag["podest"] = [b.get("name", "") if isinstance(b, dict) else ""
                                 for b in podest[:3]]
    elif eintrag["art"] == "gruppe":
        tabelle = daten.get("tabelle") or []
        platzierung = daten.get("platzierung") or []
        if tabelle and platzierung:
            platz = platzierung[0]
            if isinstance(platz, int) and 0 <= platz < len(tabelle) \
                    and isinstance(tabelle[platz], dict):
                eintrag["sieger"] = tabelle[platz].get("name", "")
        eintrag["teilnehmer"] = [e.get("name", "") for e in tabelle
                                 if isinstance(e, dict)]
        eintrag["runden"] = len(daten.get("partien") or [])
    else:
        eintrag["lesbar"] = False
    return eintrag


def gespeicherte():
    """Alle abgelegten Turniere, neueste zuerst — nur die Kurzfassung."""
    if not os.path.isdir(TURNIER_ORDNER):
        return []
    dateien = sorted((f for f in os.listdir(TURNIER_ORDNER) if f.endswith(".json")),
                     reverse=True)
    return [kurzfassung(os.path.join(TURNIER_ORDNER, f)) for f in dateien]


def laden(datei):
    pfad = os.path.join(TURNIER_ORDNER, os.path.basename(datei))
    with open(pfad, "r", encoding="utf-8") as offen:
        return json.load(offen)
