#!/usr/bin/env python3
"""Massenauswertung: alle Paarungen über viele Seeds, Siegquoten-Matrix.

    python3 balance.py                        # mitgelieferte Gegner, Seeds aus config.json
    python3 balance.py --seeds 50
    python3 balance.py --ordner abgaben       # die Abgaben der Teams
    python3 balance.py --nur hausmeister      # nur Paarungen mit diesem Bot
    python3 balance.py --json bericht.json

Jede Paarung wird mit getauschten Startplätzen gespielt, damit die Startposition
das Ergebnis nicht verzerrt. Deshalb sind es je Seed zwei Spiele.

Faustregel: Wenn einer der mitgelieferten Gegner alle anderen
schlägt, stimmen die Zahlen in der config.json nicht.
"""

import argparse
import itertools
import json
import multiprocessing
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine import config as config_modul      # noqa: E402
from engine import spielleiter                 # noqa: E402

_config_daten = None


def _kind_vorbereiten(config_daten):
    global _config_daten
    _config_daten = config_daten


def _ein_spiel(auftrag):
    """Läuft im Kindprozess. Gibt (a, b, punkte_a, punkte_b, ergebnis) zurück."""
    a_index, b_index, a_pfad, b_pfad, seed, ticks = auftrag
    config = config_modul.aus_dict(_config_daten)
    ergebnis = spielleiter.nur_ergebnis(config, [a_pfad, b_pfad], seed=seed, ticks=ticks)
    punkte = [r["punkte"] for r in ergebnis["roboter"]]
    if ergebnis["unentschieden"]:
        ausgang = "unentschieden"
    else:
        ausgang = "a" if ergebnis["sieger"] == 0 else "b"
    return (a_index, b_index, punkte[0], punkte[1], ausgang,
            [r["tot"] for r in ergebnis["bots"]])


def auftraege_bauen(bots, seeds, ticks, nur=None):
    auftraege = []
    for i, j in itertools.combinations(range(len(bots)), 2):
        if nur and nur not in (bots[i]["datei"], bots[j]["datei"],
                               os.path.splitext(bots[i]["datei"])[0],
                               os.path.splitext(bots[j]["datei"])[0]):
            continue
        for seed in seeds:
            auftraege.append((i, j, bots[i]["pfad"], bots[j]["pfad"], seed, ticks))
            auftraege.append((j, i, bots[j]["pfad"], bots[i]["pfad"], seed, ticks))
    return auftraege


def auswerten(bots, ergebnisse):
    anzahl = len(bots)
    siege = [[0] * anzahl for _ in range(anzahl)]
    spiele = [[0] * anzahl for _ in range(anzahl)]
    remis = [[0] * anzahl for _ in range(anzahl)]
    punkte_summe = [0] * anzahl
    punkte_spiele = [0] * anzahl
    tote = set()

    for a, b, pa, pb, ausgang, tot in ergebnisse:
        spiele[a][b] += 1
        spiele[b][a] += 1
        if ausgang == "a":
            siege[a][b] += 1
        elif ausgang == "b":
            siege[b][a] += 1
        else:
            remis[a][b] += 1
            remis[b][a] += 1
        punkte_summe[a] += pa
        punkte_summe[b] += pb
        punkte_spiele[a] += 1
        punkte_spiele[b] += 1
        if tot[0]:
            tote.add(a)
        if tot[1]:
            tote.add(b)

    quoten = []
    for i in range(anzahl):
        zeile = []
        for j in range(anzahl):
            if i == j or spiele[i][j] == 0:
                zeile.append(None)
            else:
                zeile.append(round(100.0 * (siege[i][j] + 0.5 * remis[i][j])
                                   / spiele[i][j], 1))
        quoten.append(zeile)

    gesamt = []
    for i in range(anzahl):
        gespielt = sum(spiele[i])
        gewonnen = sum(siege[i]) + 0.5 * sum(remis[i])
        gesamt.append({
            "name": bots[i]["name"],
            "datei": bots[i]["datei"],
            "massstab": bots[i].get("massstab", True),
            "spiele": gespielt,
            "siegquote": round(100.0 * gewonnen / gespielt, 1) if gespielt else None,
            "punkte_schnitt": round(punkte_summe[i] / punkte_spiele[i])
                              if punkte_spiele[i] else None,
            "kaputt": i in tote,
        })
    return {"quoten": quoten, "gesamt": gesamt,
            "bots": [{"name": b["name"], "datei": b["datei"]} for b in bots]}


def matrix_drucken(bericht):
    bots = bericht["bots"]
    if not bots:
        print("Keine Paarungen gespielt.")
        return
    breite = max(len(b["name"]) for b in bots) + 1
    kopf = " " * (breite + 2) + "".join("%8s" % b["name"][:7] for b in bots)
    print(kopf)
    print("-" * len(kopf))
    for i, bot in enumerate(bots):
        zeile = "%-*s |" % (breite, bot["name"][:breite])
        for j in range(len(bots)):
            wert = bericht["quoten"][i][j]
            zeile += "%8s" % ("   —" if wert is None else "%5.1f%%" % wert)
        print(zeile)
    print("-" * len(kopf))
    print("\nGelesen als: Zeile gewinnt gegen Spalte in x % der Spiele.\n")
    print("%-24s %9s %9s %9s" % ("Roboter", "Spiele", "Siegquote", "Ø Punkte"))
    for eintrag in sorted(bericht["gesamt"], key=lambda e: -(e["siegquote"] or 0)):
        print("%-24s %9d %8.1f%% %9s%s" % (
            eintrag["name"][:24], eintrag["spiele"], eintrag["siegquote"] or 0,
            eintrag["punkte_schnitt"], "  (lief nicht!)" if eintrag["kaputt"] else ""))


def urteil(bericht):
    """Die Faustregel als Satz."""
    # Absichtlich triviale Bots (Rumpelstilzchen) sind kein Maßstab für die Zahlen.
    gesamt = sorted((e for e in bericht["gesamt"] if e.get("massstab", True)),
                    key=lambda e: -(e["siegquote"] or 0))
    if not gesamt:
        return "Keine Paarungen gespielt."
    bester, schlechtester = gesamt[0], gesamt[-1]
    zeilen = []
    if bester["siegquote"] is not None and bester["siegquote"] >= 85:
        zeilen.append("%s gewinnt fast immer (%.1f%%) — die Zahlen in der config.json "
                      "stimmen so nicht." % (bester["name"], bester["siegquote"]))
    if schlechtester["siegquote"] is not None and schlechtester["siegquote"] <= 15:
        zeilen.append("%s verliert fast immer (%.1f%%) — entweder ist der Bot kaputt "
                      "oder seine Strategie trägt nicht." % (schlechtester["name"],
                                                             schlechtester["siegquote"]))
    if not zeilen:
        zeilen.append("Kein Bot dominiert und keiner geht unter — die Balance ist brauchbar.")
    return "\n".join(zeilen)


def laufen(bots, seeds, ticks, nur=None, config=None, prozesse=None, melden=None):
    config = config or config_modul.lade()
    auftraege = auftraege_bauen(bots, seeds, ticks, nur)
    if not auftraege:
        return {"quoten": [], "gesamt": [], "bots": []}
    ergebnisse = []
    prozesse = prozesse or min(os.cpu_count() or 2, 8)
    # "spawn" ist die einzige Startmethode, die auf allen Python-Versionen ab 3.10
    # gleich funktioniert — ab 3.14 ist unter Linux nicht mehr "fork" die Vorgabe.
    kontext = multiprocessing.get_context("spawn")
    try:
        with kontext.Pool(prozesse, initializer=_kind_vorbereiten,
                          initargs=(config.als_dict(),)) as pool:
            for nummer, ergebnis in enumerate(pool.imap_unordered(_ein_spiel, auftraege), 1):
                ergebnisse.append(ergebnis)
                if melden:
                    melden(nummer, len(auftraege))
    except Exception:
        # Lieber langsam als gar nicht: notfalls der Reihe nach.
        _kind_vorbereiten(config.als_dict())
        ergebnisse = []
        for nummer, auftrag in enumerate(auftraege, 1):
            ergebnisse.append(_ein_spiel(auftrag))
            if melden:
                melden(nummer, len(auftraege))
    bericht = auswerten(bots, ergebnisse)
    bericht["seeds"] = list(seeds)
    bericht["ticks"] = ticks
    bericht["spiele_gesamt"] = len(auftraege)
    bericht["urteil"] = urteil(bericht)
    return bericht


def main(argv=None):
    zerleger = argparse.ArgumentParser(description="Siegquoten-Matrix über viele Seeds")
    zerleger.add_argument("--seeds", type=int, default=None)
    zerleger.add_argument("--ab-seed", type=int, default=1)
    zerleger.add_argument("--ticks", type=int, default=None)
    zerleger.add_argument("--ordner", default=None, help="Ordner mit Bot-Dateien")
    zerleger.add_argument("--nur", default=None, help="nur Paarungen mit diesem Bot")
    zerleger.add_argument("--prozesse", type=int, default=None)
    zerleger.add_argument("--json", default=None, help="Bericht zusätzlich als JSON ablegen")
    zerleger.add_argument("--config", default=None)
    args = zerleger.parse_args(argv)

    config = config_modul.lade(args.config)
    if args.seeds is not None and args.seeds < 1:
        zerleger.error("--seeds muss mindestens 1 sein.")
    if args.prozesse is not None and args.prozesse < 1:
        zerleger.error("--prozesse muss mindestens 1 sein.")
    ordner = args.ordner or spielleiter.BOT_ORDNER
    bots = spielleiter.bots_auflisten(ordner)
    if len(bots) < 2:
        print("In %s liegen weniger als zwei Bots." % ordner)
        return 1

    anzahl_seeds = args.seeds if args.seeds is not None else config.balance.seeds
    seeds = list(range(args.ab_seed, args.ab_seed + anzahl_seeds))
    ticks = args.ticks or config.spiel.runden_laenge

    print("%d Bots, %d Seeds, %d Ticks je Spiel." % (len(bots), len(seeds), ticks))

    zustand = {"letzte": 0}

    def melden(fertig, gesamt):
        prozent = fertig * 100 // gesamt
        if prozent >= zustand["letzte"] + 5:
            zustand["letzte"] = prozent
            print("  %3d%% (%d/%d)" % (prozent, fertig, gesamt), flush=True)

    bericht = laufen(bots, seeds, ticks, nur=args.nur, config=config,
                     prozesse=args.prozesse, melden=melden)
    print()
    if not bericht["bots"]:
        if args.nur:
            print("Keine Paarungen für --nur %s gefunden — prüfe den Bot-Namen." % args.nur)
        else:
            print("Keine Paarungen gefunden — prüfe --nur und die Bot-Namen.")
        return 1
    matrix_drucken(bericht)
    print()
    print(bericht["urteil"])
    if args.json:
        with open(args.json, "w", encoding="utf-8") as datei:
            json.dump(bericht, datei, ensure_ascii=False, indent=2)
        print("\nBericht: %s" % args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
