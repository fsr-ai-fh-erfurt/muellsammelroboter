"""Laden und Prüfen der config.json.

Im Spielcode darf kein Zahlenwert fest verdrahtet sein. Alles kommt hier durch.
"""

import copy
import json
import os

PROJEKT_ORDNER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STANDARD_PFAD = os.path.join(PROJEKT_ORDNER, "config.json")


class Abschnitt:
    """Bequemer Lesezugriff: config.muell.verfall_ticks statt config['muell'][...]."""

    __slots__ = ("_daten",)

    def __init__(self, daten):
        object.__setattr__(self, "_daten", daten)

    def __getattr__(self, name):
        daten = object.__getattribute__(self, "_daten")
        if name not in daten:
            raise AttributeError(
                "In der config.json fehlt der Eintrag %r (bekannt: %s)"
                % (name, ", ".join(sorted(daten)))
            )
        wert = daten[name]
        return Abschnitt(wert) if isinstance(wert, dict) else wert

    def __getitem__(self, name):
        return getattr(self, name)

    def __contains__(self, name):
        return name in object.__getattribute__(self, "_daten")

    def keys(self):
        return sorted(object.__getattribute__(self, "_daten"))

    def als_dict(self):
        return copy.deepcopy(object.__getattribute__(self, "_daten"))

    def __repr__(self):
        return "Abschnitt(%r)" % (sorted(object.__getattribute__(self, "_daten")),)


GANZZAHLFELDER = [
    "server.port",
    "spiel.breite", "spiel.hoehe", "spiel.runden_laenge", "spiel.depot_abstand",
    "spiel.kapazitaet", "spiel.sicht_radius",
    "bots.zeitlimit_ms", "bots.start_zeitlimit_ms", "bots.kill_nach_ueberzogen",
    "bots.neustarts_max",
    "akku.max", "akku.start", "akku.kosten_bewegung", "akku.kosten_rammen",
    "akku.langsam_ab", "akku.langsam_modulo", "akku.langsam_rest",
    "akku.laden_prozent_pro_tick",
    "muell.start_anzahl", "muell.nachschub_intervall", "muell.nachschub_anzahl",
    "muell.max_auf_feld", "muell.verfall_ticks", "muell.verfall_strafe_max",
    "radioaktiv.anzahl_pro_spieler", "radioaktiv.wert",
    "zone.groesse", "zone.wechsel_alle", "zone.faktor",
    "rundenende.positiv_teiler",
    "presse.anzahl", "presse.dauer_ticks", "presse.abschlag_prozent",
    "sprache.max_wechsel",
    "turnier.gruppen_groesse", "turnier.gleichstand_wiederholungen",
    "balance.seeds",
]


def _ganzzahl_pruefen(daten, pfad):
    """Wirft ValueError, wenn unter `pfad` keine ganze Zahl steht (bool zählt nicht)."""
    ziel = daten
    for teil in pfad.split("."):
        ziel = ziel[teil]
    if isinstance(ziel, bool) or not isinstance(ziel, int):
        raise ValueError("config.json: %s muss eine ganze Zahl sein." % pfad)


PFLICHTFELDER = [
    ("spiel", ["breite", "hoehe", "runden_laenge", "kapazitaet", "sicht_radius",
               "depot_abstand", "karten"]),
    ("bots", ["zeitlimit_ms", "start_zeitlimit_ms", "kill_nach_ueberzogen", "neustarts_max"]),
    ("akku", ["max", "start", "kosten_bewegung", "kosten_rammen", "langsam_ab",
              "langsam_modulo", "langsam_rest", "laden_prozent_pro_tick",
              "leer_verliert_ladung"]),
    ("muell", ["sorten", "start_anzahl", "nachschub_intervall", "nachschub_anzahl",
               "max_auf_feld", "verfall_ticks", "verfall_strafe_max"]),
    ("radioaktiv", ["anzahl_pro_spieler", "wert", "anzeige"]),
    ("zone", ["groesse", "wechsel_alle", "faktor"]),
    ("rundenende", ["positiv_teiler"]),
    ("presse", ["anzahl", "dauer_ticks", "abschlag_prozent"]),
    ("sprache", ["max_wechsel"]),
    ("turnier", ["gruppen_groesse", "punkte_je_platz", "gleichstand_wiederholungen"]),
    ("balance", ["seeds"]),
]

# Jeder Pflicht-Abschnitt muss ein Objekt sein. `server` steht nicht in
# PFLICHTFELDER, wird aber genauso geprüft.
ABSCHNITTE = ("server",) + tuple(abschnitt for abschnitt, _ in PFLICHTFELDER)


def _karten_pruefen(daten):
    """Jede Karte muss für 2 **und** 4 Spieler ein zusammenhängendes Feld ergeben.

    Die Karten stehen nur als Grundfelder in der `config.json`; die Symmetrie
    erzeugt daraus die Wände. Ein Feld, das eine Wand auf ein Depot oder mitten
    durch die einzige Verbindung legt, fällt damit beim Laden auf — nicht erst,
    wenn ein Roboter sein Depot nicht mehr erreicht.
    """
    from .world import symmetrie_felder

    spiel = daten["spiel"]
    b, h, a = spiel["breite"], spiel["hoehe"], spiel["depot_abstand"]
    karten = spiel["karten"]
    if not isinstance(karten, list) or not karten:
        raise ValueError("config.json: spiel.karten braucht mindestens eine Karte.")

    for karte in karten:
        if not isinstance(karte, dict) or not isinstance(karte.get("name"), str) \
                or not karte["name"].strip():
            raise ValueError("config.json: jede Karte in spiel.karten braucht einen Namen.")
        waende = karte.get("waende")
        if not isinstance(waende, list):
            raise ValueError(
                "config.json: spiel.karten[%r].waende muss eine Liste sein."
                % karte["name"])
        for punkt in waende:
            if (not isinstance(punkt, list) or len(punkt) != 2
                    or any(not isinstance(wert, int) or isinstance(wert, bool)
                           for wert in punkt)):
                raise ValueError(
                    "config.json: jede Wand in spiel.karten[%r] braucht zwei ganze "
                    "Zahlen [x, y]." % karte["name"])
            if not (1 <= punkt[0] <= b - 2 and 1 <= punkt[1] <= h - 2):
                raise ValueError(
                    "config.json: die Wand %s in spiel.karten[%r] liegt außerhalb des "
                    "bespielbaren Feldes." % (punkt, karte["name"]))

        for spieler in (2, 4):
            ordnung = 2 if spieler == 2 else 4
            if spieler == 2:
                depots = {(a, a), (b - 1 - a, h - 1 - a)}
            else:
                depots = set(symmetrie_felder(b, h, a, a, 4))
            felder = set()
            for punkt in waende:
                bahn = symmetrie_felder(b, h, punkt[0], punkt[1], ordnung)
                if len(set(bahn)) != ordnung:
                    raise ValueError(
                        "config.json: die Wand %s in spiel.karten[%r] geht mit %d "
                        "Spielern nicht sauber auf." % (punkt, karte["name"], spieler))
                felder.update(bahn)
            if felder & depots:
                raise ValueError(
                    "config.json: die Karte %r legt eine Wand auf ein Depot."
                    % karte["name"])
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                for (px, py) in depots:
                    nachbar = (px + dx, py + dy)
                    if nachbar in felder:
                        raise ValueError(
                            "config.json: die Karte %r verbaut das Feld neben einem "
                            "Depot — ein Besetzer wäre dort nicht mehr zu verdrängen."
                            % karte["name"])
            _karte_verbunden_pruefen(karte["name"], b, h, felder)


def _karte_verbunden_pruefen(name, b, h, felder):
    start = None
    for y in range(1, h - 1):
        for x in range(1, b - 1):
            if (x, y) not in felder:
                start = (x, y)
                break
        if start is not None:
            break
    if start is None:
        raise ValueError("config.json: die Karte %r hat kein freies Feld." % name)
    gesehen = {start}
    stapel = [start]
    while stapel:
        x, y = stapel.pop()
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            nachbar = (x + dx, y + dy)
            if (1 <= nachbar[0] <= b - 2 and 1 <= nachbar[1] <= h - 2
                    and nachbar not in felder and nachbar not in gesehen):
                gesehen.add(nachbar)
                stapel.append(nachbar)
    frei = (b - 2) * (h - 2) - len(felder)
    if len(gesehen) != frei:
        raise ValueError(
            "config.json: die Karte %r zerreißt das Feld — nicht alle freien Felder "
            "sind erreichbar." % name)


def pruefe(daten):
    """Wirft ValueError mit deutscher Meldung, wenn etwas fehlt oder unsinnig ist."""
    if not isinstance(daten, dict):
        raise ValueError("config.json: die oberste Ebene muss ein Objekt sein.")
    for abschnitt in ABSCHNITTE:
        if abschnitt not in daten:
            raise ValueError("config.json: Abschnitt %r fehlt." % abschnitt)
        if not isinstance(daten[abschnitt], dict):
            raise ValueError(
                "config.json: Abschnitt %r muss ein Objekt sein." % abschnitt)
    if "fsr_passwort" not in daten:
        raise ValueError("config.json: fsr_passwort fehlt.")
    if not isinstance(daten["fsr_passwort"], str) or not daten["fsr_passwort"]:
        raise ValueError("config.json: fsr_passwort muss ein nicht leerer Text sein.")
    if "sorten" in daten["muell"]:
        if not isinstance(daten["muell"]["sorten"], dict):
            raise ValueError("config.json: muell.sorten muss ein Objekt sein.")
        for name, sorte in daten["muell"]["sorten"].items():
            if not isinstance(name, str) or "." in name:
                raise ValueError(
                    "config.json: der Sortenname %r in muell.sorten darf keinen Punkt "
                    "enthalten." % (name,))
            if not isinstance(sorte, dict):
                raise ValueError(
                    "config.json: muell.sorten.%s muss ein Objekt sein." % name)
    for feld in ("port", "browser_oeffnen"):
        if feld not in daten["server"]:
            raise ValueError("config.json: server.%s fehlt." % feld)
    for abschnitt, felder in PFLICHTFELDER:
        for feld in felder:
            if feld not in daten[abschnitt]:
                raise ValueError("config.json: %s.%s fehlt." % (abschnitt, feld))

    for pfad in GANZZAHLFELDER:
        _ganzzahl_pruefen(daten, pfad)
    if not 1 <= daten["server"]["port"] <= 65535:
        raise ValueError(
            "config.json: server.port muss zwischen 1 und 65535 liegen.")

    spiel = daten["spiel"]
    if spiel["breite"] != spiel["hoehe"]:
        raise ValueError(
            "config.json: breite und hoehe müssen gleich sein — die Drehsymmetrie für "
            "4 Spieler setzt ein quadratisches Feld voraus."
        )
    if spiel["breite"] < 8:
        raise ValueError("config.json: das Feld muss mindestens 8 Felder breit sein.")
    if spiel["breite"] > 64:
        raise ValueError("config.json: das Feld darf höchstens 64 Felder breit sein.")
    if not 2 <= spiel["depot_abstand"] <= spiel["breite"] // 3:
        raise ValueError(
            "config.json: spiel.depot_abstand muss mindestens 2 sein — an der Wand "
            "ließe sich ein Roboter, der ein fremdes Depot besetzt, nicht wegschieben.")
    if spiel["runden_laenge"] < 1:
        raise ValueError("config.json: spiel.runden_laenge muss mindestens 1 sein.")
    if spiel["runden_laenge"] > 10000:
        raise ValueError(
            "config.json: spiel.runden_laenge darf höchstens 10000 sein.")
    if spiel["kapazitaet"] < 1:
        raise ValueError("config.json: spiel.kapazitaet muss mindestens 1 sein.")
    if spiel["sicht_radius"] < 0:
        raise ValueError("config.json: spiel.sicht_radius darf nicht negativ sein.")
    _karten_pruefen(daten)

    bots = daten["bots"]
    for feld in ("zeitlimit_ms", "start_zeitlimit_ms"):
        if bots[feld] < 1:
            raise ValueError("config.json: bots.%s muss mindestens 1 sein." % feld)
    if bots["kill_nach_ueberzogen"] < 1:
        raise ValueError(
            "config.json: bots.kill_nach_ueberzogen muss mindestens 1 sein.")
    if bots["neustarts_max"] < 0:
        raise ValueError("config.json: bots.neustarts_max darf nicht negativ sein.")

    zone = daten["zone"]
    if zone["groesse"] < 1:
        raise ValueError("config.json: zone.groesse muss mindestens 1 sein.")
    if zone["groesse"] >= spiel["breite"] - 2:
        raise ValueError("config.json: die Bonuszone passt nicht auf das Feld.")
    if zone["wechsel_alle"] < 1:
        raise ValueError("config.json: zone.wechsel_alle muss mindestens 1 sein.")
    if zone["faktor"] < 1:
        raise ValueError("config.json: zone.faktor muss mindestens 1 sein.")

    muell = daten["muell"]
    if muell["verfall_ticks"] <= 0:
        raise ValueError("config.json: muell.verfall_ticks muss größer als 0 sein.")
    if muell["nachschub_intervall"] < 1:
        raise ValueError("config.json: muell.nachschub_intervall muss mindestens 1 sein.")
    if muell["nachschub_intervall"] > 10000:
        raise ValueError(
            "config.json: muell.nachschub_intervall darf höchstens 10000 sein.")
    if muell["nachschub_anzahl"] < 1:
        raise ValueError("config.json: muell.nachschub_anzahl muss mindestens 1 sein.")
    for feld in ("start_anzahl", "max_auf_feld", "verfall_strafe_max"):
        if muell[feld] < 0:
            raise ValueError("config.json: muell.%s darf nicht negativ sein." % feld)
    if muell["start_anzahl"] < 1:
        raise ValueError("config.json: muell.start_anzahl muss mindestens 1 sein.")
    if muell["start_anzahl"] % 4 != 0:
        raise ValueError(
            "config.json: muell.start_anzahl muss durch 4 teilbar sein — der Startmüll "
            "wird in Symmetriebahnen von 2 bzw. 4 Feldern gelegt.")

    if daten["radioaktiv"]["anzahl_pro_spieler"] < 0:
        raise ValueError(
            "config.json: radioaktiv.anzahl_pro_spieler darf nicht negativ sein.")

    akku = daten["akku"]
    if not isinstance(akku["leer_verliert_ladung"], bool):
        raise ValueError("config.json: akku.leer_verliert_ladung muss true oder false sein.")
    if akku["max"] < 1:
        raise ValueError("config.json: akku.max muss mindestens 1 sein.")
    if not 0 <= akku["start"] <= akku["max"]:
        raise ValueError("config.json: akku.start muss zwischen 0 und akku.max liegen.")
    for feld in ("kosten_bewegung", "kosten_rammen", "langsam_ab"):
        if akku[feld] < 0:
            raise ValueError("config.json: akku.%s darf nicht negativ sein." % feld)
    if akku["laden_prozent_pro_tick"] < 1:
        raise ValueError(
            "config.json: akku.laden_prozent_pro_tick muss mindestens 1 sein.")
    if akku["langsam_modulo"] <= 0:
        raise ValueError("config.json: akku.langsam_modulo muss größer als 0 sein.")
    if not 0 <= akku["langsam_rest"] < akku["langsam_modulo"]:
        raise ValueError(
            "config.json: akku.langsam_rest muss zwischen 0 und langsam_modulo - 1 liegen.")
    if daten["sprache"]["max_wechsel"] <= 0:
        raise ValueError("config.json: sprache.max_wechsel muss größer als 0 sein.")
    if daten["rundenende"]["positiv_teiler"] <= 0:
        raise ValueError("config.json: rundenende.positiv_teiler muss größer als 0 sein.")
    presse = daten["presse"]
    if presse["anzahl"] < 2:
        raise ValueError("config.json: presse.anzahl muss mindestens 2 sein.")
    if presse["dauer_ticks"] < 1:
        raise ValueError("config.json: presse.dauer_ticks muss mindestens 1 sein.")
    if not 0 <= presse["abschlag_prozent"] < 100:
        raise ValueError(
            "config.json: presse.abschlag_prozent muss zwischen 0 und 99 liegen.")
    turnier = daten["turnier"]
    if turnier["gruppen_groesse"] < 2:
        raise ValueError("config.json: turnier.gruppen_groesse muss mindestens 2 sein.")
    if turnier["gruppen_groesse"] > 4:
        raise ValueError(
            "config.json: turnier.gruppen_groesse darf höchstens 4 sein — es sind "
            "1 bis 4 Roboter vorgesehen.")
    plaetze = turnier["punkte_je_platz"]
    if not isinstance(plaetze, list) or len(plaetze) < turnier["gruppen_groesse"]:
        raise ValueError(
            "config.json: turnier.punkte_je_platz braucht einen Wert je Platz, also "
            "mindestens %d Zahlen." % turnier["gruppen_groesse"])
    if any(not isinstance(wert, int) or isinstance(wert, bool) or wert < 0
           for wert in plaetze):
        raise ValueError(
            "config.json: turnier.punkte_je_platz darf nur ganze Zahlen ab 0 enthalten.")
    if turnier["gleichstand_wiederholungen"] < 0:
        raise ValueError(
            "config.json: turnier.gleichstand_wiederholungen darf nicht negativ sein.")
    if turnier["gleichstand_wiederholungen"] > 100:
        raise ValueError(
            "config.json: turnier.gleichstand_wiederholungen darf höchstens 100 sein.")
    if daten["balance"]["seeds"] < 1:
        raise ValueError("config.json: balance.seeds muss mindestens 1 sein.")
    if daten["balance"]["seeds"] > 1000:
        raise ValueError("config.json: balance.seeds darf höchstens 1000 sein.")
    if not daten["muell"]["sorten"]:
        raise ValueError("config.json: es muss mindestens eine Müllsorte geben.")
    for name, sorte in daten["muell"]["sorten"].items():
        for feld in ("wert", "gewicht"):
            if feld not in sorte:
                raise ValueError("config.json: muell.sorten.%s.%s fehlt." % (name, feld))
            _ganzzahl_pruefen(daten, "muell.sorten.%s.%s" % (name, feld))
        if "anzeige" not in sorte:
            raise ValueError("config.json: muell.sorten.%s.anzeige fehlt." % name)
        if sorte["gewicht"] <= 0:
            raise ValueError("config.json: muell.sorten.%s.gewicht muss > 0 sein." % name)
    return daten


def lade(pfad=None):
    """Liest die config.json und gibt einen Abschnitt zurück."""
    pfad = pfad or STANDARD_PFAD
    try:
        with open(pfad, "r", encoding="utf-8") as datei:
            daten = json.load(datei)
    except FileNotFoundError:
        raise ValueError("config.json: Datei nicht gefunden: %s" % pfad) from None
    except IsADirectoryError:
        raise ValueError("config.json: keine Datei: %s" % pfad) from None
    except PermissionError:
        raise ValueError("config.json: keine Leseberechtigung: %s" % pfad) from None
    except json.JSONDecodeError as fehler:
        raise ValueError(
            "config.json: kein gültiges JSON (Zeile %d, Spalte %d)."
            % (fehler.lineno, fehler.colno)) from None
    pruefe(daten)
    return Abschnitt(daten)


def aus_dict(daten):
    """Für den FSR-Modus: Konfiguration zur Laufzeit aus einem Dict bauen."""
    pruefe(daten)
    return Abschnitt(daten)
