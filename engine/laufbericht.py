"""Was nach einem Testlauf auffällt — als Hinweise für die Werkstatt.

Die Werkstatt zeigt das Spiel, aber 400 Züge schaut sich niemand Feld für Feld an.
Ein Roboter, der 300 Züge lang am selben Fleck steht, fällt dann erst im Turnier
auf. Hier wird die Aufzeichnung des eigenen Roboters (Index 0) nach drei Mustern
durchsucht:

- **Stillstand:** lange nicht vom Fleck, oder zwischen zwei Feldern hin und her.
- **Folge ins Leere:** ein Schritt einer Folge wollte fahren und kam nicht weiter
  (Wand oder Gegner) — die Folge lief trotzdem weiter.
- **Kreis:** die Modi haben sich im Kreis gewechselt, und der Zug ging verloren.

Reine Auswertung einer fertigen Aufzeichnung: keine Spielregel, kein Zufall. Die
Regeln kommen als Liste von Wörterbüchern, so wie `Programm.als_dict()` sie liefert.
"""

import re
from collections import Counter

# Ab so vielen Zügen am selben Fleck gibt es einen Hinweis. Kein Spielwert, nur eine
# Schwelle für die Werkstatt: kurzes Warten auf Nachschub soll nicht auffallen.
STILLSTAND_AB = 20
# Mehr als so viele Stillstände nennt der Bericht nicht — der längste zuerst.
STILLSTAENDE_HOECHSTENS = 2

KREIS = re.compile(r"^Achtung: die Modi wechseln im Kreis \(zuletzt (.*)\)\.$")
FOLGE_MODUS = re.compile(r"^folge_z(\d+)_schritt\d+$")


def _regel_text(nummer, regeln):
    """„Regel 13 (Zeile 31)", „die Folge aus Zeile 7" oder „keine Regel"."""
    if not nummer:
        return "keine Regel", None
    for regel in regeln:
        if regel.get("nummer") == nummer:
            folge = regel.get("folge")
            if folge:
                return "die Folge aus Zeile %d" % folge["zeile"], folge["zeile"]
            return "Regel %d (Zeile %d)" % (nummer, regel["zeile"]), regel["zeile"]
    return "Regel %d" % nummer, None


def _stillstaende(ticks, index):
    """Abschnitte, in denen der Roboter auf höchstens zwei Feldern blieb."""
    funde = []
    k = 0
    while k < len(ticks):
        if ticks[k]["roboter"][index]["laedt"]:
            k += 1
            continue
        felder = set()
        ende = k
        while ende < len(ticks):
            roboter = ticks[ende]["roboter"][index]
            felder.add((roboter["x"], roboter["y"]))
            if len(felder) > 2 or roboter["laedt"]:
                break
            ende += 1
        if ende - k >= STILLSTAND_AB:
            funde.append((k, ende))
            k = ende
        else:
            k += 1
    return funde


def _stillstand_meldungen(ticks, regeln, index):
    funde = sorted(_stillstaende(ticks, index), key=lambda f: f[0] - f[1])
    meldungen = []
    for anfang, ende in funde[:STILLSTAENDE_HOECHSTENS]:
        haeufig = Counter(ticks[k]["regeln"][index] for k in range(anfang, ende))
        nummer = haeufig.most_common(1)[0][0]
        welche, zeile = _regel_text(nummer, regeln)
        von, bis = ticks[anfang]["tick"], ticks[ende - 1]["tick"]
        meldungen.append({
            "klasse": "hinweis", "zeile": zeile,
            "text": "Dein Roboter kam von Zug %d bis %d (%d Züge) nicht vom Fleck — er "
                    "stand still oder pendelte zwischen zwei Feldern. Meist griff dabei %s. "
                    "Zieh den Schieber auf Zug %d und schau, was er dort sieht."
                    % (von, bis, bis - von + 1, welche, von)})
    return meldungen


def _folgen_ins_leere(ticks, start, regeln, index):
    """Schritte einer Folge, die fahren wollten und auf demselben Feld blieben."""
    schritte = {r["nummer"]: r["folge"] for r in regeln
                if r.get("folge") and r["folge"].get("richtung")}
    if not schritte:
        return []
    je_folge = {}
    vorher = start["roboter"][index]
    for tick in ticks:
        roboter = tick["roboter"][index]
        folge = schritte.get(tick["regeln"][index])
        # `aktionen` ist das, was wirklich ausgeführt wurde: In einem langsamen Zug
        # (wenig Akku) steht dort `warte` — das ist kein versperrter Weg.
        if folge and tick["aktionen"][index] == folge["richtung"] \
                and (roboter["x"], roboter["y"]) == (vorher["x"], vorher["y"]):
            eintrag = je_folge.setdefault(folge["zeile"],
                                          {"anzahl": 0, "erster": tick["tick"],
                                           "schritte": {}})
            eintrag["anzahl"] += 1
            eintrag["schritte"][folge["schritt"]] = folge["richtung"]
        vorher = roboter

    meldungen = []
    for zeile in sorted(je_folge):
        eintrag = je_folge[zeile]
        welche = ", ".join("Schritt %d (nach %s)" % (nummer, richtung)
                           for nummer, richtung in sorted(eintrag["schritte"].items()))
        mal = "einmal" if eintrag["anzahl"] == 1 else "%d-mal" % eintrag["anzahl"]
        kam = "kam" if len(eintrag["schritte"]) == 1 else "kamen"
        meldungen.append({
            "klasse": "hinweis", "zeile": zeile,
            "text": "Die Folge aus Zeile %d lief %s ins Leere: %s %s nicht vom Fleck, "
                    "weil der Weg versperrt war (Wand oder Gegner) — zum ersten Mal in "
                    "Zug %d. Die Folge lief trotzdem bis zum Ende weiter."
                    % (zeile, mal, welche, kam, eintrag["erster"])})
    return meldungen


def _kreis_meldung(bot):
    if not bot:
        return []
    treffer = [KREIS.match(m) for m in bot.get("meldungen", [])]
    treffer = [t for t in treffer if t]
    if not treffer:
        return []
    zuletzt = treffer[-1].group(1)
    folge = FOLGE_MODUS.match(zuletzt)
    wo = ("in der Folge aus Zeile %s" % folge.group(1)) if folge \
        else "zuletzt in Modus `%s`" % zuletzt
    # Der Runner nimmt nur eine begrenzte Zahl Ausgaben auf — dann sind es mehr.
    abgeschnitten = any(m.startswith("... weitere Ausgaben") for m in bot.get("meldungen", []))
    anzahl = ("mindestens %d" if abgeschnitten else "%d") % len(treffer)
    return [{
        "klasse": "hinweis", "zeile": int(folge.group(1)) if folge else None,
        "text": "In %s Zügen haben sich deine Modi im Kreis gewechselt (%s), ohne dass "
                "eine Aktion herauskam — in diesen Zügen hat dein Roboter gewartet. Schau, "
                "welche Regeln dorthin und wieder zurück springen." % (anzahl, wo)}]


def bericht(aufzeichnung, regeln, index=0):
    """Die Hinweise zu einem Testlauf, in der Reihenfolge Kreis, Folgen, Stillstand."""
    ticks = aufzeichnung.get("ticks") or []
    start = aufzeichnung.get("start") or {}
    if not ticks or not start.get("roboter"):
        return []
    bots = aufzeichnung.get("bots") or []
    meldungen = _kreis_meldung(bots[index] if index < len(bots) else None)
    meldungen += _folgen_ins_leere(ticks, start, regeln, index)
    meldungen += _stillstand_meldungen(ticks, regeln, index)
    return meldungen
