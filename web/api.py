"""Die JSON-Schnittstelle.

Jede Route liefert Daten oder stößt eine Berechnung in Python an. Der Browser
entscheidet nichts — er zeigt an, was hier herauskommt.
"""

import copy
import json
import os
import shutil
import tempfile

import balance as balance_modul

from engine import config as config_modul
from engine import laufbericht
from engine import spielleiter
from engine import tournament
from language.compiler import abgabe_stand, aus_python_lesen, uebersetzen
from language.errors import RegelFehler

from .server import Antwort


def _text(daten, schluessel, standard="", grenze=200000):
    wert = daten.get(schluessel, standard)
    if not isinstance(wert, str):
        raise Antwort(400, "Das Feld %r muss Text sein." % schluessel)
    if len(wert) > grenze:
        raise Antwort(400, "Das Feld %r ist zu lang." % schluessel)
    return wert


def _zahl(daten, schluessel, standard, kleinste=None, groesste=None):
    wert = daten.get(schluessel, standard)
    try:
        wert = int(wert)
    except (TypeError, ValueError):
        raise Antwort(400, "Das Feld %r muss eine Zahl sein." % schluessel)
    if (kleinste is not None and wert < kleinste) or \
       (groesste is not None and wert > groesste):
        raise Antwort(400, "Das Feld %r muss zwischen %s und %s liegen."
                      % (schluessel, kleinste, groesste))
    return wert


def dateiname_aus(name):
    erlaubt = "abcdefghijklmnopqrstuvwxyz0123456789_"
    ersatz = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", " ": "_", "-": "_"}
    sauber = []
    for zeichen in (name or "").strip().lower():
        zeichen = ersatz.get(zeichen, zeichen)
        for teil in zeichen:
            if teil in erlaubt:
                sauber.append(teil)
    ergebnis = "".join(sauber).strip("_") or "roboter"
    while "__" in ergebnis:
        ergebnis = ergebnis.replace("__", "_")
    return ergebnis[:40] + ".py"


def bot_datei_schreiben(ordner, quelle, name):
    pfad = os.path.join(ordner, dateiname_aus(name))
    with open(pfad, "w", encoding="utf-8") as datei:
        datei.write(quelle)
    return pfad


def kosten_aus(config):
    """Die Zahlen aus der config.json für die Kostenangabe je Regel."""
    return {
        "bewegung": config.akku.kosten_bewegung,
        "rammen": config.akku.kosten_rammen,
        "presse_anzahl": config.presse.anzahl,
        "presse_dauer": config.presse.dauer_ticks,
        "presse_abschlag": config.presse.abschlag_prozent,
    }


def uebersetzen_oder_fehler(app, daten):
    """Gemeinsamer Weg für Testlauf und Abgabe."""
    quelltext = _text(daten, "quelltext")
    teamname = _text(daten, "teamname", "Namenloser Roboter", grenze=200) or "Namenloser Roboter"
    beschreibung = _text(daten, "beschreibung", "", grenze=400)
    ergebnis = uebersetzen(quelltext, teamname, beschreibung, kosten_aus(app.config))
    return ergebnis, teamname


def config_ohne_passwort(app):
    """Die Konfiguration für die Anzeige — das Passwort geht den Browser nichts an."""
    daten = app.config.als_dict()
    daten.pop("fsr_passwort", None)
    return daten


def ohne_pfade(daten):
    """Entfernt Serverpfade aus einer Antwort — die gehen den Browser nichts an.

    Turnierablage, Aufzeichnungen und Aufgabenergebnisse führen zu jedem Bot den
    absoluten `pfad` mit (er wird serverseitig zum Nachspielen gebraucht). Vor der
    Auslieferung fällt er heraus. Wer eine gespeicherte Struktur besitzt, übergibt
    eine Kopie — das Original behält den Pfad.
    """
    if isinstance(daten, dict):
        daten.pop("pfad", None)
        for wert in daten.values():
            ohne_pfade(wert)
    elif isinstance(daten, list):
        for eintrag in daten:
            ohne_pfade(eintrag)
    return daten


def config_schreiben(pfad, daten):
    """Schreibt die config.json über eine Temp-Datei — nie halb geschrieben."""
    ordner = os.path.dirname(os.path.abspath(pfad)) or "."
    kanal, temp = tempfile.mkstemp(prefix="config_", suffix=".tmp", dir=ordner)
    try:
        with os.fdopen(kanal, "w", encoding="utf-8") as datei:
            json.dump(daten, datei, ensure_ascii=False, indent=2)
            datei.write("\n")
        os.replace(temp, pfad)
    except BaseException:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise


def registriere(anwendung):

    @anwendung.route("/api/status", methoden=("GET", "POST"))
    def status(app, daten):
        cfg = app.config
        return {
            "gegner": [
                {"datei": g["datei"], "name": g["name"], "beschreibung": g["beschreibung"]}
                for g in spielleiter.mitgelieferte_gegner()
            ],
            "spiel": {
                "breite": cfg.spiel.breite,
                "hoehe": cfg.spiel.hoehe,
                "runden_laenge": cfg.spiel.runden_laenge,
                "kapazitaet": cfg.spiel.kapazitaet,
                "sicht_radius": cfg.spiel.sicht_radius,
                "zone_groesse": cfg.zone.groesse,
                "zone_faktor": cfg.zone.faktor,
                "verfall_ticks": cfg.muell.verfall_ticks,
                "akku_langsam_ab": cfg.akku.langsam_ab,
                "zeitlimit_ms": cfg.bots.zeitlimit_ms,
            },
            "sorten": {
                name: {"wert": cfg.muell.sorten[name].wert,
                       "anzeige": cfg.muell.sorten[name].anzeige}
                for name in cfg.muell.sorten.keys()
            },
            "radioaktiv": {"wert": cfg.radioaktiv.wert, "anzeige": cfg.radioaktiv.anzeige},
        }

    @anwendung.route("/api/pruefen")
    def pruefen(app, daten):
        # Derselbe Weg wie Testlauf und Abgabe: Was hier grün ist, lässt sich auch
        # übersetzen. Der erzeugte Python-Quelltext wird dabei nicht ausgeliefert.
        ergebnis = uebersetzen(_text(daten, "quelltext"), kosten=kosten_aus(app.config))
        ergebnis["quelle"] = None
        return ergebnis

    @anwendung.route("/api/testlauf")
    def testlauf(app, daten):
        ergebnis, teamname = uebersetzen_oder_fehler(app, daten)
        if not ergebnis["gueltig"]:
            return {"programm": ergebnis, "aufzeichnung": None}

        # Ohne Angabe fährt der Roboter allein. Wer zum ersten Mal auf Testlauf
        # drückt, will sehen, was sein eigener Roboter tut — ein Gegner, der
        # gleichzeitig einsammelt, verdeckt das nur.
        gegner_datei = _text(daten, "gegner", "", grenze=200)
        gegner_pfad = None
        if gegner_datei:
            gegner_pfad = os.path.join(spielleiter.BOT_ORDNER,
                                       os.path.basename(gegner_datei))
            if not os.path.isfile(gegner_pfad):
                raise Antwort(400, "Diesen Gegner gibt es nicht: %s" % gegner_datei)

        seed = _zahl(daten, "seed", 1, 0, 10 ** 9)
        ticks = _zahl(daten, "ticks", app.config.spiel.runden_laenge, 10, 5000)

        ordner = tempfile.mkdtemp(prefix="werkstatt_")
        try:
            eigener = bot_datei_schreiben(ordner, ergebnis["quelle"], teamname)
            pfade = [eigener] if gegner_pfad is None else [eigener, gegner_pfad]
            namen = [teamname] if gegner_pfad is None else [teamname, None]
            aufzeichnung = spielleiter.match(
                app.config, pfade, seed=seed, ticks=ticks, namen=namen)
        finally:
            shutil.rmtree(ordner, ignore_errors=True)
        # Die Aufzeichnung wird nirgends behalten — das Original darf beschritten werden.
        return {"programm": ergebnis, "aufzeichnung": ohne_pfade(aufzeichnung),
                "bericht": laufbericht.bericht(aufzeichnung, ergebnis["regeln"])}

    @anwendung.route("/api/abgabe")
    def abgabe(app, daten):
        ergebnis, teamname = uebersetzen_oder_fehler(app, daten)
        if not ergebnis["gueltig"]:
            return {"programm": ergebnis, "quelle": None, "dateiname": None}
        return {
            "programm": ergebnis,
            "quelle": ergebnis["quelle"],
            "dateiname": dateiname_aus(teamname),
        }

    @anwendung.route("/api/oeffnen")
    def oeffnen(app, daten):
        inhalt = _text(daten, "inhalt")
        try:
            gelesen = aus_python_lesen(inhalt)
        except RegelFehler as fehler:
            raise Antwort(400, fehler.vollstaendig())
        if not gelesen.get("pseudocode"):
            raise Antwort(400,
                          "In dieser Datei steht kein PSEUDOCODE-Block. Nur Dateien, die "
                          "die Werkstatt erzeugt hat, lassen sich hier wieder öffnen.")
        return gelesen

    @anwendung.route("/api/fsr/anmelden")
    def anmelden(app, daten):
        passwort = _text(daten, "passwort", grenze=200)
        # Kein Sicherheitsmerkmal: das Passwort steht offen in der config.json.
        # Es schützt nur vor versehentlichem Verstellen.
        if passwort != app.config.fsr_passwort:
            raise Antwort(403, "Falsches Passwort.")
        return {"marke": app.marke_anlegen()}

    def marke_pruefen(app, daten):
        if not app.marke_gueltig(daten.get("marke")):
            raise Antwort(403, "Bitte im FSR-Modus anmelden.")

    # ------------------------------------------------------------------ FSR

    def abgaben_mit_stand(app):
        """Die Abgaben, je mit dem Hinweis, ob sie zur jetzigen Werkstatt passen."""
        abgaben = spielleiter.bots_auflisten(spielleiter.ABGABEN_ORDNER)
        for eintrag in abgaben:
            try:
                with open(eintrag["pfad"], "r", encoding="utf-8") as datei:
                    eintrag["stand"] = abgabe_stand(datei.read(), kosten_aus(app.config))
            except (OSError, UnicodeDecodeError):
                eintrag["stand"] = None
        return abgaben

    def bots_sammeln(app):
        return {
            "abgaben": abgaben_mit_stand(app),
            "mitgeliefert": spielleiter.mitgelieferte_gegner(),
            "abgaben_ordner": spielleiter.ABGABEN_ORDNER,
        }

    def bot_finden(app, kennung):
        """kennung ist 'abgaben/datei.py' oder 'bots/datei.py'."""
        if not isinstance(kennung, str) or "/" not in kennung:
            raise Antwort(400, "Ungültige Bot-Angabe: %r" % (kennung,))
        ordner, datei = kennung.split("/", 1)
        if ordner not in ("abgaben", "bots"):
            raise Antwort(400, "Unbekannter Ordner: %s" % ordner)
        basis = spielleiter.ABGABEN_ORDNER if ordner == "abgaben" else spielleiter.BOT_ORDNER
        pfad = os.path.join(basis, os.path.basename(datei))
        if not os.path.isfile(pfad):
            raise Antwort(400, "Diese Bot-Datei gibt es nicht: %s" % kennung)
        eintrag = spielleiter.bot_beschreibung(pfad)
        eintrag["kennung"] = kennung
        return eintrag

    @anwendung.route("/api/fsr/bots")
    def fsr_bots(app, daten):
        marke_pruefen(app, daten)
        # Nur die Antwort wird beschnitten — andere Routen brauchen die echten Pfade.
        sicht = copy.deepcopy(bots_sammeln(app))
        ohne_pfade(sicht)
        sicht["abgaben_ordner"] = "abgaben"
        return sicht

    @anwendung.route("/api/fsr/match")
    def fsr_match(app, daten):
        marke_pruefen(app, daten)
        kennungen = daten.get("bots") or []
        if not 2 <= len(kennungen) <= 4:
            raise Antwort(400, "Ein Match braucht 2 bis 4 Roboter.")
        eintraege = [bot_finden(app, k) for k in kennungen]
        # Die K.-o.-Bühne spielt hier Turnierpartien nach. Deren Seeds kommen aus
        # `tournament.partie_seed` (unter 2**31) plus Gleichstands-Wiederholungen —
        # die Grenze muss alle davon durchlassen, sonst bleibt eine Partie dunkel.
        seed = _zahl(daten, "seed", 1, 0, 2 ** 32)
        ticks = _zahl(daten, "ticks", app.config.spiel.runden_laenge, 10, 5000)
        aufzeichnung = spielleiter.match(
            app.config, [e["pfad"] for e in eintraege], seed=seed, ticks=ticks,
            namen=[e["name"] for e in eintraege])
        return {"aufzeichnung": ohne_pfade(aufzeichnung)}

    @anwendung.route("/api/fsr/gruppe")
    def fsr_gruppe(app, daten):
        marke_pruefen(app, daten)
        kennungen = daten.get("bots") or []
        if len(kennungen) != app.config.turnier.gruppen_groesse:
            raise Antwort(400, "Eine Gruppe besteht aus %d Robotern."
                          % app.config.turnier.gruppen_groesse)
        eintraege = [bot_finden(app, k) for k in kennungen]
        seed = _zahl(daten, "seed", 1, 0, 10 ** 9)
        config = app.config

        def arbeit(melden):
            ergebnis = tournament.gruppe(config, eintraege, seed=seed, melden=melden)
            ergebnis["gespeichert"] = os.path.basename(
                tournament.speichern(ergebnis, "gruppe"))
            return ergebnis

        return {"aufgabe": app.aufgabe_starten("Gruppenphase", arbeit)["id"]}

    @anwendung.route("/api/fsr/ko")
    def fsr_ko(app, daten):
        marke_pruefen(app, daten)
        kennungen = daten.get("bots") or []
        if len(kennungen) < 2:
            raise Antwort(400, "Ein K.-o.-Turnier braucht mindestens 2 Roboter.")
        if len(kennungen) > 32:
            raise Antwort(400, "Mehr als 32 Roboter sind nicht vorgesehen.")
        eintraege = [bot_finden(app, k) for k in kennungen]
        if len(set(kennungen)) != len(kennungen):
            raise Antwort(400, "Jeder Roboter darf nur einmal im Turnier stehen.")
        seed = _zahl(daten, "seed", 1, 0, 10 ** 9)
        losen = daten.get("auslosen") is True
        config = app.config

        def arbeit(melden):
            ergebnis = tournament.ko_turnier(config, eintraege, seed=seed, melden=melden,
                                             losen=losen)
            ergebnis["gespeichert"] = os.path.basename(
                tournament.speichern(ergebnis, "ko"))
            return ergebnis

        return {"aufgabe": app.aufgabe_starten("K.-o.-Turnier", arbeit)["id"]}

    @anwendung.route("/api/fsr/balance")
    def fsr_balance(app, daten):
        marke_pruefen(app, daten)
        ordner = daten.get("ordner", "bots")
        basis = spielleiter.ABGABEN_ORDNER if ordner == "abgaben" else spielleiter.BOT_ORDNER
        bots = spielleiter.bots_auflisten(basis)
        if len(bots) < 2:
            raise Antwort(400, "In diesem Ordner liegen weniger als zwei Roboter.")
        anzahl = _zahl(daten, "seeds", app.config.balance.seeds, 1, 200)
        seeds = list(range(1, anzahl + 1))
        config = app.config
        ticks = config.spiel.runden_laenge

        def arbeit(melden):
            return balance_modul.laufen(bots, seeds, ticks, config=config, melden=melden)

        return {"aufgabe": app.aufgabe_starten("Massenauswertung", arbeit)["id"]}

    @anwendung.route("/api/fsr/aufgabe")
    def fsr_aufgabe(app, daten):
        marke_pruefen(app, daten)
        nummer = _zahl(daten, "id", 0)
        eintrag = app.aufgaben.get(nummer)
        if eintrag is None:
            raise Antwort(404, "Diese Aufgabe gibt es nicht.")
        # Nur die ausgelieferte Kopie wird beschnitten — das gespeicherte Ergebnis
        # braucht die Pfade weiter, z.B. zum Nachspielen einer Partie.
        return ohne_pfade(copy.deepcopy(eintrag))

    @anwendung.route("/api/fsr/config")
    def fsr_config(app, daten):
        marke_pruefen(app, daten)
        neu = daten.get("config")
        if neu is None:
            return {"config": config_ohne_passwort(app)}
        if not isinstance(neu, dict):
            raise Antwort(400, "Die Konfiguration muss ein Objekt sein.")
        neu = dict(neu)
        passwort = neu.get("fsr_passwort")
        if not isinstance(passwort, str) or not passwort:
            neu["fsr_passwort"] = app.config.fsr_passwort
        try:
            app.config_setzen(neu)
        except ValueError as fehler:
            raise Antwort(400, str(fehler))
        if daten.get("dauerhaft"):
            config_schreiben(app.config_pfad, neu)
        return {"config": config_ohne_passwort(app),
                "gespeichert": bool(daten.get("dauerhaft"))}

    @anwendung.route("/api/fsr/turniere")
    def fsr_turniere(app, daten):
        marke_pruefen(app, daten)
        datei = _text(daten, "datei", "", grenze=200)
        if datei:
            try:
                return {"turnier": ohne_pfade(tournament.laden(datei))}
            except (OSError, ValueError):
                raise Antwort(404, "Dieses Turnier gibt es nicht (mehr): %s"
                              % os.path.basename(datei))
        return {"turniere": [ohne_pfade(e) for e in tournament.gespeicherte()]}

    return anwendung
