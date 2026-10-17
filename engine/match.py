"""Ein Match auf der Konsole.

    python3 -m engine.match bots/fleissig.py bots/rumpelstilzchen.py --seed 1
    python3 -m engine.match bots/*.py --seed 4 --zeigen --aufzeichnung /tmp/lauf.json
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import config as config_modul          # noqa: E402
from engine import recording                       # noqa: E402
from engine.game import Spiel                      # noqa: E402
from engine.runner import Anschlussgruppe          # noqa: E402
from engine.world import SORTE_RADIOAKTIV          # noqa: E402

ZEICHEN = {"papier": "p", "bio": "b", "metall": "M", "elektro": "E",
           SORTE_RADIOAKTIV: "X"}


def feld_zeichnen(spiel):
    welt = spiel.welt
    zeilen = []
    for y in range(welt.hoehe):
        zeile = []
        for x in range(welt.breite):
            if welt.ist_wand(x, y):
                zeichen = "#"
            elif welt.ist_hindernis(x, y):
                zeichen = "▓"
            else:
                roboter = welt.roboter_auf(x, y)
                stueck = welt.muell.get((x, y))
                if roboter is not None:
                    zeichen = str(roboter.index)
                elif stueck is not None:
                    zeichen = ZEICHEN.get(stueck.sorte, "?")
                elif welt.ist_depot(x, y):
                    zeichen = "_"
                elif welt.in_zone(x, y):
                    zeichen = "·"
                else:
                    zeichen = " "
            zeile.append(zeichen)
        zeilen.append("".join(zeile))
    return "\n".join(zeilen)


def ergebnis_zeigen(spiel, anschluesse):
    ergebnis = spiel.ergebnis
    print()
    print("Endstand nach %d Ticks (Seed %d)" % (ergebnis.ticks, ergebnis.seed))
    print("-" * 68)
    print("%-22s %8s %6s %8s %8s %7s" %
          ("Roboter", "Punkte", "Akku", "Teile", "Gerammt", "Geklaut"))
    for i in ergebnis.reihenfolge:
        eintrag = ergebnis.roboter[i]
        s = eintrag["statistik"]
        print("%-22s %8d %6d %8d %8d %7d" % (
            eintrag["name"][:22], eintrag["punkte"], eintrag["akku"],
            s["abgeliefert_stueck"], s["rammangriffe"], s["geklaut"]))
    print("-" * 68)
    if ergebnis.unentschieden:
        print("Unentschieden.")
    else:
        print("Sieger: %s" % ergebnis.roboter[ergebnis.sieger]["name"])

    for anschluss in anschluesse or []:
        if anschluss.fehler:
            print("\n[%s] Probleme:" % anschluss.name)
            for text in anschluss.fehler[:3]:
                print("   " + text.strip().replace("\n", "\n   "))
        if anschluss.statistik["ueberzogen"]:
            print("[%s] %d Züge über dem Zeitlimit."
                  % (anschluss.name, anschluss.statistik["ueberzogen"]))
        if anschluss.meldungen:
            print("[%s] Ausgaben: %d Zeilen (erste: %s)"
                  % (anschluss.name, len(anschluss.meldungen), anschluss.meldungen[0][:60]))


def main(argv=None):
    zerleger = argparse.ArgumentParser(description="Ein Match auf der Konsole spielen.")
    zerleger.add_argument("bots", nargs="+", help="Pfade zu 1 bis 4 Bot-Dateien")
    zerleger.add_argument("--seed", type=int, default=1)
    zerleger.add_argument("--ticks", type=int, default=None, help="Rundenlänge überschreiben")
    zerleger.add_argument("--config", default=None)
    zerleger.add_argument("--zeigen", action="store_true", help="Spielfeld als Text ausgeben")
    zerleger.add_argument("--alle", type=int, default=50, help="mit --zeigen: alle N Ticks")
    zerleger.add_argument("--aufzeichnung", default=None, help="Aufzeichnung als JSON speichern")
    args = zerleger.parse_args(argv)

    if not 1 <= len(args.bots) <= 4:
        zerleger.error("Es sind 1 bis 4 Bots möglich.")
    if args.alle < 1:
        zerleger.error("--alle muss mindestens 1 sein.")
    if args.ticks is not None and args.ticks < 1:
        zerleger.error("--ticks muss mindestens 1 sein.")
    for pfad in args.bots:
        if not os.path.isfile(pfad):
            zerleger.error("Diese Bot-Datei gibt es nicht: %s" % pfad)
    try:
        config = config_modul.lade(args.config)
    except ValueError as fehler:
        zerleger.error(str(fehler))

    with Anschlussgruppe(args.bots, config) as anschluesse:
        spiel = Spiel(config, anschluesse, seed=args.seed, runden_laenge=args.ticks)
        if args.zeigen:
            print("Tick 0")
            print(feld_zeichnen(spiel))
        while not spiel.beendet:
            spiel.schritt()
            if args.zeigen and spiel.welt.tick % args.alle == 0:
                punkte = "  ".join("%s %d" % (r.name, r.punkte) for r in spiel.welt.roboter)
                print("\nTick %d   %s" % (spiel.welt.tick, punkte))
                print(feld_zeichnen(spiel))
        ergebnis_zeigen(spiel, anschluesse)
        if args.aufzeichnung:
            recording.speichern(args.aufzeichnung, recording.aufzeichnung(spiel, anschluesse))
            print("\nAufzeichnung: %s" % args.aufzeichnung)
    return 0


if __name__ == "__main__":
    sys.exit(main())
