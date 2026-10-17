"""Übersetzung des Pseudocodes in eine lesbare Python-Datei.

Die Abgabedatei ist zugleich das, was das Turnier ausführt — es gibt keine
Umwandlung dazwischen. Deshalb muss sie erstens funktionieren und zweitens
aussehen wie etwas, das man selbst geschrieben haben könnte: eine Klasse,
eine Methode je Modus, ein `if` je Regel, der Pseudocode als Kommentar darüber.

Über jeder Regel steht außerdem, was sie kostet — in Zügen und Akku. Hängen die
Kosten vom Spielstand ab (ein Weg ist mal kurz und mal lang), sagt der Kommentar
das dazu und nennt den Wert, mit dem man sie selbst ausrechnet.
"""

import ast
import re
import textwrap

from .errors import RegelFehler
from .kosten import aktion_kosten
from .parser import (FLAGGEN, ZAHLWERTE, Modus, Programm, PythonBlock, Regel,
                     zerlegen_programm)

EINRUECKUNG = " " * 8

FLAGGEN_ZU_PYTHON = {name: "zustand." + name for name in sorted(FLAGGEN)}

ZAHLWERTE_ZU_PYTHON = {name: "zustand." + name for name in sorted(ZAHLWERTE)}

PRIORITAET = {"oder": 1, "und": 2, "nicht": 3}
RECHEN_PRIORITAET = {"+": 1, "-": 1, "*": 2, "/": 2, "%": 2}


def konstanten_name(name):
    return name.upper()


# --------------------------------------------------------------------- Ausdrücke

class Bedarf:
    """Was die erzeugte Datei außer den Regeln noch braucht."""

    def __init__(self):
        self.teilen = False          # die Hilfsfunktion für `/`
        self.resten = False          # die Hilfsfunktion für `%`
        self.bestes = False          # die Hilfsmethode für `BEST muell BY ...`
        self.beste_richtung = False  # dieselbe Auswahl für `richtung_zu BEST ...`
        # Die versteckten Modi der Folgen (`fahre links, oben, ...`): Name -> der
        # Modus, in dem die Folge steht. Leer, wenn es keine Folge gibt.
        self.folgen = {}


def rechnung_text(knoten, zeile, bedarf, aussen=0):
    art = knoten.art
    if art == "zahl":
        return str(knoten.wert)
    if art == "konstante":
        return konstanten_name(knoten.name)
    if art == "zahlwert":
        return ZAHLWERTE_ZU_PYTHON[knoten.name]
    if art == "formelwert":
        return knoten.name
    if art == "abstand":
        return ziel_abstand(knoten.ziel, zeile)
    if art == "anzahl":
        return 'zustand.anzahl("%s")' % knoten.sorte
    if art == "negativ":
        return "-%s" % rechnung_text(knoten.inhalt, zeile, bedarf, 3)
    if art == "rechnung":
        if knoten.op in ("/", "%"):
            if knoten.op == "/":
                bedarf.teilen = True
                helfer = "teile"
            else:
                bedarf.resten = True
                helfer = "rest"
            return "%s(%s, %s)" % (
                helfer,
                rechnung_text(knoten.links, zeile, bedarf, 0),
                rechnung_text(knoten.rechts, zeile, bedarf, 0))
        links = rechnung_text(knoten.links, zeile, bedarf, RECHEN_PRIORITAET[knoten.op])
        rechts = rechnung_text(knoten.rechts, zeile, bedarf,
                               RECHEN_PRIORITAET[knoten.op] + 1)
        text = "%s %s %s" % (links, knoten.op, rechts)
        return "(%s)" % text if RECHEN_PRIORITAET[knoten.op] < aussen else text
    raise RegelFehler(zeile, "Diese Rechnung verstehe ich nicht.")


def ziel_fahrt(ziel, zeile, bedarf):
    if ziel.was == "depot":
        return "zustand.fahre_zu_depot()"
    if ziel.was == "gegner":
        return "zustand.fahre_zu_gegner()"
    if ziel.was == "zone":
        return "zustand.fahre_zu_zone()"
    if ziel.was == "weg_von_gegner":
        return "zustand.weg_von_gegner()"
    if ziel.was == "feld":
        return "zustand.fahre_zu_feld(%d, %d)" % (ziel.x, ziel.y)
    if getattr(ziel, "formel", None) is not None:
        bedarf.bestes = True
        formel = rechnung_text(ziel.formel, zeile, bedarf)
        argumente = muell_argumente(ziel)
        return "self._bestes_stueck(zustand, lambda wert, abstand, bonus: %s%s)" % (
            formel, (", " + argumente) if argumente else "")
    return "zustand.fahre_zu_muell(%s)" % muell_argumente(ziel)


def ziel_abstand(ziel, zeile):
    if ziel.was == "depot":
        return "zustand.abstand_zu_depot()"
    if ziel.was == "gegner":
        return "zustand.abstand_zu_gegner()"
    if ziel.was == "zone":
        return "zustand.abstand_zu_zone()"
    if ziel.was == "feld":
        return "zustand.abstand_zu_feld(%d, %d)" % (ziel.x, ziel.y)
    if ziel.was == "muell":
        if getattr(ziel, "formel", None) is not None:
            raise RegelFehler(
                zeile, "`abstand_zu BEST muell BY …` ergibt keinen Sinn — das Stück "
                       "steht ja erst nach der Rechnung fest.",
                beispiel="abstand_zu naechster_muell(metall) < 7")
        return "zustand.abstand_zu_muell(%s)" % muell_argumente(ziel)
    raise RegelFehler(zeile, "`abstand_zu weg_von gegner` ergibt keinen Sinn.",
                      beispiel="IF abstand_zu gegner < 3 THEN fahre_zu weg_von gegner")


def ziel_richtung(ziel, zeile, bedarf):
    """`richtung_zu <ziel>`: dieselbe Wegsuche wie `fahre_zu`, nur als Antwort."""
    if ziel.was == "depot":
        return "zustand.richtung_zu_depot()"
    if ziel.was == "gegner":
        return "zustand.richtung_zu_gegner()"
    if ziel.was == "zone":
        return "zustand.richtung_zu_zone()"
    if ziel.was == "weg_von_gegner":
        return "zustand.richtung_weg_von_gegner()"
    if ziel.was == "feld":
        return "zustand.richtung_zu_feld(%d, %d)" % (ziel.x, ziel.y)
    if getattr(ziel, "formel", None) is not None:
        bedarf.beste_richtung = True
        formel = rechnung_text(ziel.formel, zeile, bedarf)
        argumente = muell_argumente(ziel)
        return "self._beste_richtung(zustand, lambda wert, abstand, bonus: %s%s)" % (
            formel, (", " + argumente) if argumente else "")
    return "zustand.richtung_zu_muell(%s)" % muell_argumente(ziel)


def wortseite_text(knoten, zeile, bedarf):
    if knoten.art == "wortwert":
        return '"%s"' % knoten.wert
    if knoten.art == "richtungsfrage":
        return ziel_richtung(knoten.ziel, zeile, bedarf)
    if knoten.art == "objektfrage":
        return "zustand.objekt_in_richtung(%s)" % wortseite_text(knoten.richtung, zeile,
                                                                  bedarf)
    raise RegelFehler(zeile, "Diesen Vergleich verstehe ich nicht.")


def muell_argumente(ziel):
    teile = []
    if getattr(ziel, "sorte", None):
        teile.append('sorte="%s"' % ziel.sorte)
    if getattr(ziel, "nur_in_zone", False):
        teile.append("nur_in_zone=True")
    return ", ".join(teile)


def bedingung_text(knoten, zeile, bedarf, aussen=0):
    art = knoten.art
    if art == "flagge":
        return FLAGGEN_ZU_PYTHON[knoten.name]
    if art == "habe":
        return 'zustand.habe("%s")' % knoten.sorte
    if art == "random":
        return "zustand.zufall_zahl(100) < %d" % knoten.prozent
    if art == "wortvergleich":
        return "%s %s %s" % (wortseite_text(knoten.links, zeile, bedarf), knoten.op,
                             wortseite_text(knoten.rechts, zeile, bedarf))
    if art == "vergleich":
        return "%s %s %s" % (rechnung_text(knoten.links, zeile, bedarf),
                             knoten.op,
                             rechnung_text(knoten.rechts, zeile, bedarf))
    if art == "nicht":
        return "not %s" % bedingung_text(knoten.inhalt, zeile, bedarf, PRIORITAET["nicht"])
    if art in ("und", "oder"):
        wort = "and" if art == "und" else "or"
        eigene = PRIORITAET[art]
        text = "%s %s %s" % (bedingung_text(knoten.links, zeile, bedarf, eigene), wort,
                             bedingung_text(knoten.rechts, zeile, bedarf, eigene))
        return "(%s)" % text if eigene < aussen else text
    raise RegelFehler(zeile, "Diese Bedingung verstehe ich nicht.")


def aktion_text(knoten, zeile, bedarf):
    if knoten.art == "warte":
        return '"warte"'
    if knoten.art == "presse":
        return '"presse"'
    if knoten.art == "fahre":
        return 'zustand.fahre("%s")' % knoten.richtung
    if knoten.art == "fahre_zu":
        return ziel_fahrt(knoten.ziel, zeile, bedarf)
    raise RegelFehler(zeile, "Diese Aktion verstehe ich nicht.")


# --------------------------------------------------------------------- Datei

def pseudocode_einbetten(quelltext):
    """Macht den Pseudocode als dreifach-zitierte Zeichenkette einbettbar."""
    text = quelltext.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    if not text.endswith("\n"):
        text += "\n"
    return text


def python_block_einruecken(zeilen, einrueckung=EINRUECKUNG):
    ohne_leere = [z for z in zeilen if z.strip()]
    if not ohne_leere:
        return []
    kleinste = min(len(z) - len(z.lstrip()) for z in ohne_leere)
    ergebnis = []
    for zeile in zeilen:
        if not zeile.strip():
            ergebnis.append("")
        else:
            ergebnis.append(einrueckung + zeile[kleinste:].rstrip())
    return ergebnis


class Ausgabe:
    """Sammelt Zeilen und merkt sich, aus welcher Pseudocode-Zeile jede stammt."""

    def __init__(self):
        self.zeilen = []
        self.karte = {}

    def schreibe(self, text="", quellzeile=None):
        self.zeilen.append(text)
        if quellzeile:
            self.karte[len(self.zeilen)] = quellzeile

    def kommentar(self, einrueckung, kopf, text, quellzeile=None):
        """Ein umgebrochener Kommentarblock — die Folgezeilen bündig unter dem ersten."""
        breite = 96 - len(einrueckung) - len(kopf)
        stuecke = textwrap.wrap(text, max(30, breite)) or [""]
        self.schreibe("%s# %s%s" % (einrueckung, kopf, stuecke[0]), quellzeile)
        for weiter in stuecke[1:]:
            self.schreibe("%s# %s%s" % (einrueckung, " " * len(kopf), weiter), quellzeile)

    def text(self):
        return "\n".join(self.zeilen) + "\n"


def modus_wache(regel, modus, folgen=None):
    """Der Zusatz, der ein `GOTO` in den eigenen Modus wirkungslos macht.

    `GOTO` in den Modus, in dem der Roboter schon ist, tut nichts: Die Regel wird
    übersprungen, und es geht mit der nächsten weiter. Geprüft werden muss das nur
    da, wo der Modus überhaupt ein anderer sein kann — vor dem ersten `STATE`
    (`modus` ist None) und bei einem `GOTO` auf den eigenen Modus. Innerhalb eines
    Modus auf einen anderen zu wechseln braucht die Prüfung nicht; sie wäre dort
    immer wahr und stünde nur als totes `if` in der Abgabedatei.

    Läuft gerade eine Folge, die in Modus `ziel` steht, ist der Roboter auch dann
    noch „in `ziel`" — sonst würde ein `GOTO ziel` vor dem ersten STATE die Folge
    in jedem Tick wieder von vorn anstoßen, und sie käme nie über Schritt 1 hinaus.
    """
    if regel.aktion.art != "goto":
        return None
    ziel = regel.aktion.modus
    if modus is None or modus == ziel:
        if folgen and ziel in folgen.values():
            return 'self._grundmodus() != "%s"' % ziel
        return 'self.modus != "%s"' % ziel
    return None


def regel_schreiben(aus, regel, einrueckung, bedarf, kosten, in_automat, modus=None):
    """Ein `if` je Regel — mit Pseudocode und Kosten als Kommentar darüber."""
    aus.kommentar(einrueckung, "Regel %d: " % regel.nummer, regel.quelle, regel.zeile)
    aus.kommentar(einrueckung, "Kosten:   ", aktion_kosten(regel.aktion, kosten),
                  regel.zeile)

    wache = modus_wache(regel, modus, bedarf.folgen)
    tiefer = einrueckung + "    "
    if regel.art == "if":
        # Vor dem `and` muss ein ODER geklammert werden, sonst bindet es falsch.
        bedingung = bedingung_text(regel.bedingung, regel.zeile, bedarf,
                                   PRIORITAET["und"] if wache else 0)
        if wache:
            bedingung = "%s and %s" % (bedingung, wache)
        aus.schreibe("%sif %s:" % (einrueckung, bedingung), regel.zeile)
        rumpf = tiefer
    elif wache:
        aus.schreibe("%sif %s:" % (einrueckung, wache), regel.zeile)
        rumpf = tiefer
    else:
        rumpf = einrueckung

    aus.schreibe("%szustand.regel(%d)" % (rumpf, regel.nummer), regel.zeile)
    if regel.aktion.art == "goto":
        aus.schreibe('%sself.modus = "%s"' % (rumpf, regel.aktion.modus), regel.zeile)
        aus.schreibe("%sreturn None" % rumpf, regel.zeile)
    else:
        text = aktion_text(regel.aktion, regel.zeile, bedarf)
        if in_automat and regel.aktion.art == "warte":
            aus.schreibe('%sreturn "warte"' % rumpf, regel.zeile)
        else:
            aus.schreibe("%sreturn %s" % (rumpf, text), regel.zeile)
    return wache is None


def teile_schreiben(aus, teile, einrueckung, bedarf, kosten, in_automat, modus=None):
    """Regeln und PYTHON-Blöcke eines Blocks. Gibt zurück, ob ein ELSE abschließt.

    Ein `ELSE GOTO <eigener Modus>` schließt **nicht** ab: Es tut nichts, also muss
    dahinter noch das `warte` stehen, sonst fällt die Methode ohne Rückgabe heraus.

    Nach einem unbedingten `ELSE` ist alles Weitere toter Code. Regeln dahinter
    werden nicht mehr übersetzt; PYTHON-Blöcke bleiben stehen, damit die Datei
    vollständig ist.
    """
    erster = True
    abschluss = False
    for teil in teile:
        if not erster:
            aus.schreibe("")
        erster = False
        if isinstance(teil, PythonBlock):
            aus.schreibe("%s# --- eigener PYTHON-Block aus Zeile %d ---"
                         % (einrueckung, teil.zeile), teil.zeile)
            for zeile, nummer in zip(python_block_einruecken(teil.zeilen, einrueckung),
                                     teil.nummern):
                aus.schreibe(zeile, nummer)
            aus.schreibe("%s# --- Ende des PYTHON-Blocks ---" % einrueckung, teil.zeile)
            continue
        if abschluss:
            continue
        unbedingt = regel_schreiben(aus, teil, einrueckung, bedarf, kosten, in_automat,
                                    modus)
        if teil.art == "else" and unbedingt:
            abschluss = True
    return abschluss


def hilfen_schreiben(aus, bedarf):
    if bedarf.beste_richtung:
        aus.schreibe("    def _beste_richtung(self, zustand, bewerten, sorte=None,")
        aus.schreibe("                        nur_in_zone=False):")
        aus.schreibe('        """Wohin `BEST muell BY …` als Nächstes fahren würde."""')
        aus.schreibe("        bestes = self._bestes_feld(zustand, bewerten, sorte, nur_in_zone)")
        aus.schreibe("        if bestes is None:")
        aus.schreibe('            return "keine"')
        aus.schreibe('        return zustand.richtung_zu_feld(bestes["x"], bestes["y"])')
        aus.schreibe("")
    if bedarf.bestes:
        aus.schreibe("    def _bestes_stueck(self, zustand, bewerten, sorte=None,")
        aus.schreibe("                       nur_in_zone=False):")
        aus.schreibe('        """Fährt zum Müllstück mit dem besten Ergebnis der Formel."""')
        aus.schreibe("        bestes = self._bestes_feld(zustand, bewerten, sorte, nur_in_zone)")
        aus.schreibe("        if bestes is None:")
        aus.schreibe('            return "warte"')
        aus.schreibe('        return zustand.fahre_zu_feld(bestes["x"], bestes["y"])')
        aus.schreibe("")
    if bedarf.bestes or bedarf.beste_richtung:
        aus.schreibe("    def _bestes_feld(self, zustand, bewerten, sorte=None, nur_in_zone=False):")
        aus.schreibe('        """Rechnet die Formel für jedes Müllstück aus und nimmt das beste.')
        aus.schreibe("")
        aus.schreibe("        `wert` ist der Wert, den das Stück gerade hat, `abstand` die")
        aus.schreibe("        Weglänge dorthin und `bonus`, um wie viel es in der Zone mehr zählt.")
        aus.schreibe('        """')
        aus.schreibe("        bestes = None")
        aus.schreibe("        beste_marke = None")
        aus.schreibe("        for stueck in zustand.muell_auswahl(")
        aus.schreibe("                sorte=sorte, nur_in_zone=nur_in_zone,")
        aus.schreibe('                nur_positiv=sorte != "radioaktiv"):')
        aus.schreibe('            abstand = zustand.abstand_zu_feld(stueck["x"], stueck["y"])')
        aus.schreibe("            if abstand >= zustand.unerriechbar:")
        aus.schreibe("                continue    # dahin führt gerade kein Weg")
        aus.schreibe('            bonus = (zustand.zone_faktor')
        aus.schreibe('                     if zustand.ist_in_zone(stueck["x"], stueck["y"]) else 1)')
        aus.schreibe('            marke = bewerten(stueck["wert"], abstand, bonus)')
        aus.schreibe("            if beste_marke is None or marke > beste_marke:")
        aus.schreibe("                bestes, beste_marke = stueck, marke")
        aus.schreibe("        return bestes")
        aus.schreibe("")


def nach_python(programm, teamname, quelltext, beschreibung="", kosten=None):
    """Erzeugt den Quelltext der Abgabedatei. Wirft RegelFehler bei Restproblemen."""
    name = (teamname or "Namenloser Roboter").strip()[:60] or "Namenloser Roboter"
    beschreibung = (beschreibung or "").strip().replace("\n", " ")[:120]
    bedarf = Bedarf()
    for versteckt in programm.modi:
        if getattr(versteckt, "versteckt", False) and versteckt.regeln:
            bedarf.folgen[versteckt.name] = versteckt.regeln[0].modus

    # Erst den Rumpf bauen: dabei stellt sich heraus, welche Hilfen gebraucht werden.
    rumpf = Ausgabe()
    if programm.hat_modi:
        automat_schreiben(rumpf, programm, bedarf, kosten)
    else:
        flach_schreiben(rumpf, programm, bedarf, kosten)

    aus = Ausgabe()
    aus.schreibe("# -*- coding: utf-8 -*-")
    aus.schreibe('"""Roboter für das Müllsammel-Turnier.')
    aus.schreibe("")
    aus.schreibe("Diese Datei wurde in der Werkstatt aus Regeln erzeugt. Der Pseudocode steht")
    aus.schreibe("unten in PSEUDOCODE — damit lässt sich die Datei dort wieder öffnen und")
    aus.schreibe("weiterbearbeiten. Der Rest ist ganz normales Python.")
    aus.schreibe('"""')
    aus.schreibe("")
    aus.schreibe("NAME = %r" % name)
    aus.schreibe("BESCHREIBUNG = %r" % beschreibung)
    aus.schreibe("")
    aus.schreibe('PSEUDOCODE = """\\')
    for zeile in pseudocode_einbetten(quelltext).rstrip("\n").split("\n"):
        aus.schreibe(zeile)
    aus.schreibe('"""')
    aus.schreibe("")

    # Die Konstanten erst in Text verwandeln: dabei stellt sich heraus, ob `teile`
    # und `rest` gebraucht werden. Die Hilfsfunktionen müssen dann **vor** den
    # Konstanten stehen — `LET half = 7 / 2` ruft `teile` schon beim Laden auf.
    konstante_zeilen = [
        (konstanten_name(konstante.name),
         rechnung_text(konstante.ausdruck, konstante.zeile, bedarf),
         konstante.zeile)
        for konstante in programm.konstanten
    ]

    if bedarf.teilen:
        aus.schreibe("")
        aus.schreibe("def teile(a, b):")
        aus.schreibe('    """Ganzzahlig teilen. Durch 0 zu teilen ergibt hier 0, damit der')
        aus.schreibe('    Roboter mitten im Spiel nicht abstürzt."""')
        aus.schreibe("    return a // b if b else 0")

    if bedarf.resten:
        aus.schreibe("")
        aus.schreibe("def rest(a, b):")
        aus.schreibe('    """Ganzzahliger Rest. Ein Rest durch 0 ergibt hier 0, damit der')
        aus.schreibe('    Roboter mitten im Spiel nicht abstürzt."""')
        aus.schreibe("    return a % b if b else 0")

    if konstante_zeilen:
        aus.schreibe("")
        aus.schreibe("# Die Zahlen aus den LET-Zeilen. Hier dreht man an einer Stelle.")
        for name, text, zeile in konstante_zeilen:
            aus.schreibe("%s = %s" % (name, text), zeile)

    aus.schreibe("")
    for zeile_nr, zeile in enumerate(rumpf.zeilen, 1):
        aus.schreibe(zeile, rumpf.karte.get(zeile_nr))

    quelle = aus.text()
    pruefe_syntax(quelle, aus.karte)
    return quelle


def flach_schreiben(aus, programm, bedarf, kosten):
    """Ohne STATE: eine Methode, ein `if` je Regel — wie in der ersten Fassung."""
    aus.schreibe("class Roboter:")
    aus.schreibe('    """Der Roboter wird in jedem Tick einmal nach seiner Aktion gefragt.')
    aus.schreibe("")
    aus.schreibe("    Die Regeln werden von oben nach unten geprüft. Die erste, die zutrifft,")
    aus.schreibe("    bestimmt die Aktion — genau wie im Pseudocode.")
    aus.schreibe('    """')
    aus.schreibe("")
    aus.schreibe("    NAME = NAME")
    aus.schreibe("")
    aus.schreibe("    def entscheide(self, zustand):")

    hat_abschluss = teile_schreiben(aus, programm.teile, EINRUECKUNG, bedarf, kosten,
                                    in_automat=False)
    if not hat_abschluss:
        aus.schreibe("")
        aus.schreibe("%s# Keine Regel hat gegriffen — dann wird gewartet." % EINRUECKUNG)
        aus.schreibe("%szustand.regel(0)" % EINRUECKUNG)
        aus.schreibe('%sreturn "warte"' % EINRUECKUNG)
    if bedarf.bestes or bedarf.beste_richtung:
        aus.schreibe("")
        hilfen_schreiben(aus, bedarf)


def automat_schreiben(aus, programm, bedarf, kosten):
    """Mit STATE: ein Zustandsautomat, eine Methode je Modus."""
    start = programm.modi[0].name
    aus.schreibe("class Roboter:")
    aus.schreibe('    """Ein Roboter mit mehreren Modi — ein Zustandsautomat.')
    aus.schreibe("")
    aus.schreibe("    `self.modus` sagt, in welchem Zustand der Roboter gerade ist. In jedem")
    aus.schreibe("    Tick werden die Regeln dieses Modus von oben nach unten geprüft. `GOTO`")
    aus.schreibe("    wechselt den Modus, ohne einen Zug zu verbrauchen: danach geht es sofort")
    aus.schreibe("    mit den Regeln des neuen Modus weiter. Ein `GOTO` in den Modus, in dem")
    aus.schreibe("    er schon ist, tut nichts — dann geht es mit der nächsten Regel weiter.")
    aus.schreibe('    """')
    aus.schreibe("")
    aus.schreibe("    NAME = NAME")
    aus.schreibe('    START_MODUS = "%s"' % start, programm.modi[0].zeile)
    aus.schreibe("")
    if bedarf.folgen:
        aus.schreibe("    # Die Schritte der Folgen und der Modus, in dem jede Folge steht.")
        aus.schreibe("    FOLGEN = {")
        for name, herkunft in bedarf.folgen.items():
            aus.schreibe('        "%s": "%s",' % (name, herkunft))
        aus.schreibe("    }")
        aus.schreibe("")
    aus.schreibe("    def __init__(self):")
    aus.schreibe("        self.modus = self.START_MODUS")
    aus.schreibe("")
    if bedarf.folgen:
        aus.schreibe("    def _grundmodus(self):")
        aus.schreibe('        """Der Modus — während einer Folge der, in dem die Folge steht."""')
        aus.schreibe("        return self.FOLGEN.get(self.modus, self.modus)")
        aus.schreibe("")
    aus.schreibe("    def entscheide(self, zustand):")
    aus.schreibe("        # Notbremse gegen Modi, die im Kreis wechseln (config.json: "
                 "sprache.max_wechsel).")
    aus.schreibe("        for _ in range(zustand.max_wechsel):")
    aus.schreibe("            aktion = self._weiterleiten(zustand)")
    aus.schreibe("            if aktion is not None:")
    aus.schreibe("                return aktion")
    aus.schreibe("        # Die Modi haben sich im Kreis gewechselt, ohne etwas zu tun.")
    aus.schreibe('        print("Achtung: die Modi wechseln im Kreis (zuletzt %s)." % self.modus)')
    aus.schreibe('        return "warte"')
    aus.schreibe("")
    aus.schreibe("    def _weiterleiten(self, zustand):")
    aus.schreibe('        """Die Aktion für diesen Tick — oder None, wenn nur der Modus wechselte."""')

    if programm.teile:
        aus.schreibe("        # Diese Regeln stehen vor dem ersten STATE und gelten in jedem Modus.")
        teile_schreiben(aus, programm.teile, EINRUECKUNG, bedarf, kosten, in_automat=True)
        aus.schreibe("")

    for modus in programm.modi:
        aus.schreibe('        if self.modus == "%s":' % modus.name, modus.zeile)
        aus.schreibe("            return self._modus_%s(zustand)" % modus.name, modus.zeile)
    aus.schreibe('        return "warte"')

    for modus in programm.modi:
        aus.schreibe("")
        aus.schreibe("    def _modus_%s(self, zustand):" % modus.name, modus.zeile)
        aus.kommentar("        ", "", modus.quelle, modus.zeile)
        hat_abschluss = teile_schreiben(aus, modus.teile, EINRUECKUNG, bedarf, kosten,
                                        in_automat=True, modus=modus.name)
        if not hat_abschluss:
            aus.schreibe("")
            aus.schreibe("%s# Keine Regel hat gegriffen — dann wird gewartet." % EINRUECKUNG)
            aus.schreibe("%szustand.regel(0)" % EINRUECKUNG)
            aus.schreibe('%sreturn "warte"' % EINRUECKUNG)

    if bedarf.bestes or bedarf.beste_richtung:
        aus.schreibe("")
        hilfen_schreiben(aus, bedarf)


def pruefe_syntax(quelle, karte):
    """Fängt Syntaxfehler aus PYTHON-Blöcken ab und übersetzt sie zurück."""
    try:
        compile(quelle, "<abgabe>", "exec")
    except SyntaxError as fehler:
        zeile = karte.get(fehler.lineno or 0)
        text = (fehler.msg or "Syntaxfehler").strip()
        if zeile:
            raise RegelFehler(
                zeile,
                "Der PYTHON-Block hat einen Syntaxfehler: %s" % text)
        raise RegelFehler(
            0, "Aus diesen Regeln lässt sich kein gültiges Python bauen: %s" % text)


def uebersetzen(quelltext, teamname="Namenloser Roboter", beschreibung="", kosten=None):
    """Der ganze Weg: Pseudocode prüfen und übersetzen."""
    try:
        return _uebersetzen(quelltext, teamname, beschreibung, kosten)
    except RecursionError:
        programm = Programm()
        programm.fehler.append(RegelFehler(
            0, "Zu viele verschachtelte Klammern — daraus lässt sich kein Python bauen."))
        ergebnis = programm.als_dict(kosten)
        ergebnis["quelle"] = None
        return ergebnis


def _uebersetzen(quelltext, teamname, beschreibung, kosten):
    programm = zerlegen_programm(quelltext)
    ergebnis = programm.als_dict(kosten)
    ergebnis["quelle"] = None
    if not programm.gueltig:
        return ergebnis
    try:
        ergebnis["quelle"] = nach_python(programm, teamname, quelltext, beschreibung,
                                         kosten)
    except RegelFehler as fehler:
        ergebnis["gueltig"] = False
        ergebnis["fehler"].append(fehler.als_dict())
    return ergebnis


# --------------------------------------------------------------------- Rückweg

def aus_python_lesen(text):
    """Holt NAME, BESCHREIBUNG und PSEUDOCODE aus einer Abgabedatei — ohne sie auszuführen."""
    ergebnis = {"name": None, "beschreibung": None, "pseudocode": None}
    try:
        baum = ast.parse(text)
    except SyntaxError as fehler:
        raise RegelFehler(fehler.lineno or 0,
                          "Diese Datei ist kein gültiges Python: %s" % (fehler.msg or ""))
    for knoten in baum.body:
        if not isinstance(knoten, ast.Assign):
            continue
        for ziel in knoten.targets:
            if not isinstance(ziel, ast.Name):
                continue
            if not isinstance(knoten.value, ast.Constant) or \
                    not isinstance(knoten.value.value, str):
                continue
            if ziel.id == "NAME":
                ergebnis["name"] = knoten.value.value
            elif ziel.id == "BESCHREIBUNG":
                ergebnis["beschreibung"] = knoten.value.value
            elif ziel.id == "PSEUDOCODE":
                ergebnis["pseudocode"] = knoten.value.value
    return ergebnis


# --------------------------------------------------------------------- Abgabestand

def _ohne_docstrings(baum):
    """Der Baum ohne Docstrings — deren Wortlaut ändert am Verhalten nichts."""
    for knoten in ast.walk(baum):
        rumpf = getattr(knoten, "body", None)
        if isinstance(rumpf, list) and rumpf and isinstance(rumpf[0], ast.Expr) \
                and isinstance(rumpf[0].value, ast.Constant) \
                and isinstance(rumpf[0].value.value, str):
            rumpf.pop(0)
    return ast.dump(baum)


def abgabe_stand(text, kosten=None):
    """Passt eine Abgabedatei zur jetzigen Werkstatt?

    Die Datei ist das, was im Turnier läuft — nicht ihr Pseudocode. Wurde sie mit
    einer älteren Fassung der Werkstatt erzeugt, kann sie sich anders verhalten als
    derselbe Pseudocode heute. Darum wird der PSEUDOCODE-Block frisch übersetzt und
    mit der Datei verglichen, ohne Kommentare und Docstrings.

    Gibt "aktuell", "veraltet" oder "ungueltig" (der Pseudocode lässt sich heute
    nicht mehr übersetzen) zurück — None, wenn die Datei keinen PSEUDOCODE trägt.
    """
    try:
        gelesen = aus_python_lesen(text)
    except RegelFehler:
        return None
    if not gelesen.get("pseudocode"):
        return None
    ergebnis = uebersetzen(gelesen["pseudocode"], gelesen.get("name") or "",
                           gelesen.get("beschreibung") or "", kosten)
    if not ergebnis["gueltig"] or not ergebnis["quelle"]:
        return "ungueltig"
    try:
        gleich = _ohne_docstrings(ast.parse(text)) == _ohne_docstrings(
            ast.parse(ergebnis["quelle"]))
    except SyntaxError:
        return "ungueltig"
    return "aktuell" if gleich else "veraltet"
