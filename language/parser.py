"""Der Parser der Regelsprache.

Regeln werden von oben nach unten geprüft, die erste zutreffende wird ausgeführt.

    IF ladung_ist_voll THEN fahre_zu depot
    IF akku < 30 THEN fahre_zu depot
    IF gegner_sichtbar AND gegner_ladung >= 4 THEN ramme gegner
    ELSE fahre_zu naechster_muell

Wer mehr will, gibt seinem Roboter Modi — einen Zustandsautomaten:

    STATE sammeln
      IF ladung_ist_voll THEN GOTO heimweg
      ELSE fahre_zu naechster_muell

    STATE heimweg
      IF abstand_zu depot == 0 THEN GOTO sammeln
      ELSE fahre_zu depot

Innerhalb eines Modus darf eine Regel auch eine **Folge** von Aktionen haben, mit
Komma getrennt. Jede Aktion kostet einen eigenen Tick, ein `GOTO` darf am Ende
stehen. Ohne `GOTO` geht es danach im selben Modus weiter. In einer Folge darf
man `fahre` vor einer Richtung weglassen:

    STATE start
      IF abstand_zu depot == 0 THEN fahre rechts, rechts, unten, GOTO sammeln

Die Folge ist nur eine Abkürzung: Der Parser macht daraus für jeden Schritt einen
kleinen versteckten Modus (`folge_z12_schritt1`, `..._schritt2`, ...). Darum gilt
alles wie bei normalen Regeln: ein Zug pro Tick, Akku je Schritt, und die Regeln
vor dem ersten STATE werden in jedem Tick zuerst geprüft. Springt so eine Regel mit
`GOTO` woandershin, ist die Folge abgebrochen.

Die Schlüsselwörter sind englisch (IF, THEN, ELSE, AND, STATE, GOTO), die Begriffe
aus dem Spiel deutsch (ladung, akku, naechster_muell). Genau so sieht Code aus, den
man später im Studium schreibt.

Die Sprache ist absichtlich fehlertolerant: Groß-/Kleinschreibung egal, Leerzeichen
egal, Umlaute egal, `THEN` optional. Fehler werden gesammelt, nicht beim ersten
Problem abgebrochen — sonst sieht man immer nur einen Fehler auf einmal.
"""

import re

from .errors import Hinweis, RegelFehler, vorschlag

# --------------------------------------------------------------------- Wortschatz

RICHTUNGEN = {
    "oben": "oben", "hoch": "oben", "rauf": "oben", "norden": "oben", "nord": "oben",
    "unten": "unten", "runter": "unten", "sueden": "unten", "sued": "unten",
    "links": "links", "westen": "links", "west": "links",
    "rechts": "rechts", "osten": "rechts", "ost": "rechts",
}

SORTEN = {
    "papier": "papier", "papiermuell": "papier",
    "bio": "bio", "biomuell": "bio",
    "metall": "metall", "metallschrott": "metall", "schrott": "metall",
    "elektro": "elektro", "elektroschrott": "elektro", "elektronik": "elektro",
    "radioaktiv": "radioaktiv", "fass": "radioaktiv", "atommuell": "radioaktiv",
    "ballen": "ballen", "gepresst": "ballen",
}

ZAHLWERTE = {"ladung", "akku", "gegner_ladung", "tick", "punkte",
             "restliche_ticks", "ladung_wert", "freie_plaetze"}

FLAGGEN = {"gegner_sichtbar", "bin_in_zone", "muell_in_zone",
           "ladung_ist_voll", "ladung_ist_leer", "kann_pressen"}

ZIELWOERTER = {"depot", "gegner", "zone", "naechster_muell", "muell", "weg_von", "feld"}

AKTIONSWOERTER = {"fahre_zu", "fahre", "ramme", "warte", "presse", "goto"}

SCHLUESSELWOERTER = {"if", "then", "else", "and", "or", "not", "state", "goto", "let",
                     "best", "by", "random", "habe", "anzahl", "abstand_zu",
                     "richtung_zu", "objekt_in_richtung", "python", "end"}

# Fragen, die ein Wort statt einer Zahl liefern — nur mit `==` und `!=` vergleichbar.
WORTFRAGEN = {"richtung_zu", "objekt_in_richtung"}

# Was `richtung_zu` liefert: eine Richtung, `hier` (schon da) oder `keine` (kein Weg).
RICHTUNGSANTWORTEN = {"hier", "keine"}

# Was `objekt_in_richtung` liefert, außer den Müllsorten.
OBJEKTE = {"frei", "wand", "gegner", "depot"}

# Nur innerhalb von `BEST muell BY ...` gültig.
FORMELWOERTER = {"wert", "abstand", "bonus"}

# Diese Namen vergibt die Werkstatt in der Abgabedatei selbst. Als LET-Name würden
# sie die Team-Kennung oder den eingebetteten Pseudocode überschreiben.
RESERVIERTE_KONSTANTEN = {"name", "beschreibung", "pseudocode"}

# Die deutschen Schlüsselwörter der ersten Fassung. Sie bleiben nicht als Alias
# stehen — sonst kursieren zwei Dialekte —, aber der Parser erkennt sie und sagt,
# wie es jetzt heißt.
ALTE_SCHLUESSELWOERTER = {
    "wenn": "IF", "dann": "THEN", "sonst": "ELSE",
    "und": "AND", "oder": "OR", "nicht": "NOT", "ende": "END",
}

ALLE_WOERTER = (set(RICHTUNGEN) | set(SORTEN) | ZAHLWERTE | FLAGGEN | ZIELWOERTER
                | AKTIONSWOERTER | SCHLUESSELWOERTER | RICHTUNGSANTWORTEN | OBJEKTE
                | {"in_zone"})

VERGLEICHE = {"<": "<", ">": ">", "==": "==", "<=": "<=", ">=": ">=", "!=": "!="}

RECHENZEICHEN = {"+", "-", "*", "/", "%"}

UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
                         "Ä": "ae", "Ö": "oe", "Ü": "ue"})

TOKEN = re.compile(
    r"\s*(?:(?P<zahl>\d+)"
    r"|(?P<wort>[A-Za-zÄÖÜäöüß_][A-Za-zÄÖÜäöüß0-9_]*)"
    r"|(?P<sym><=|>=|!=|<>|==|[<>=(),+\-*/%])"
    r"|(?P<rest>\S))"
)


def normal(text):
    return text.translate(UMLAUTE).lower()


class Token:
    __slots__ = ("art", "wert", "roh", "spalte")

    def __init__(self, art, wert, roh, spalte):
        self.art = art          # "wort" | "zahl" | "sym"
        self.wert = wert
        self.roh = roh
        self.spalte = spalte

    def __repr__(self):
        return "Token(%s, %r)" % (self.art, self.wert)


def zerlegen(zeile, zeilennummer):
    tokens = []
    stelle = 0
    while stelle < len(zeile):
        treffer = TOKEN.match(zeile, stelle)
        if treffer is None:
            if not zeile[stelle:].strip():
                break
            raise RegelFehler(zeilennummer,
                              "Das Zeichen `%s` gehört nicht in eine Regel."
                              % zeile[stelle],
                              spalte=stelle + 1)
        stelle = treffer.end()
        if treffer.group("rest"):
            raise RegelFehler(zeilennummer,
                              "Das Zeichen `%s` gehört nicht in eine Regel."
                              % treffer.group("rest"),
                              spalte=treffer.start("rest") + 1)
        if treffer.group("zahl"):
            roh = treffer.group("zahl")
            if len(roh) > 18:
                raise RegelFehler(zeilennummer,
                                  "Die Zahl `%s` ist zu groß — höchstens 18 Ziffern."
                                  % roh,
                                  spalte=treffer.start("zahl") + 1)
            tokens.append(Token("zahl", int(roh),
                                roh, treffer.start("zahl") + 1))
        elif treffer.group("wort"):
            roh = treffer.group("wort")
            tokens.append(Token("wort", normal(roh), roh, treffer.start("wort") + 1))
        else:
            roh = treffer.group("sym")
            tokens.append(Token("sym", roh, roh, treffer.start("sym") + 1))
    return tokens


# --------------------------------------------------------------------- Baum

class Knoten:
    def __init__(self, art, **felder):
        self.art = art
        self.__dict__.update(felder)

    def __repr__(self):
        felder = {k: v for k, v in self.__dict__.items() if k != "art"}
        return "%s(%s)" % (self.art, felder)


class Regel:
    def __init__(self, nummer, art, bedingung, aktion, quelle, zeile, modus=None):
        self.nummer = nummer
        self.art = art              # "if" | "else"
        self.bedingung = bedingung
        self.aktion = aktion
        self.quelle = quelle
        self.zeile = zeile
        self.modus = modus          # None = gilt in jedem Modus
        self.bedingung_text = None  # die Bedingung, wie sie im Quelltext steht
        self.folge = None           # bei einem Schritt einer Folge: woher und welcher


class PythonBlock:
    def __init__(self, zeilen, zeile, nummern=None):
        self.zeilen = zeilen
        self.zeile = zeile
        self.nummern = list(nummern) if nummern is not None else [zeile] * len(zeilen)


class Konstante:
    def __init__(self, name, ausdruck, zeile, quelle):
        self.name = name
        self.ausdruck = ausdruck
        self.zeile = zeile
        self.quelle = quelle


class Modus:
    """Ein Zustand des Roboters: ein Name und die Regeln, die darin gelten."""

    def __init__(self, name, zeile, quelle, versteckt=False):
        self.name = name
        self.zeile = zeile
        self.quelle = quelle
        self.teile = []
        # Versteckte Modi legt der Parser selbst an — einen je Schritt einer Folge.
        self.versteckt = versteckt

    @property
    def regeln(self):
        return [t for t in self.teile if isinstance(t, Regel)]


class Programm:
    def __init__(self):
        self.teile = []             # Regeln und PythonBlöcke vor dem ersten STATE
        self.modi = []
        self.konstanten = []
        self.fehler = []
        self.hinweise = []
        # Das `GOTO` am Ende einer Folge steht in keiner Regel, sondern im letzten
        # Schritt. Damit es trotzdem geprüft wird: (Zeile, goto-Knoten).
        self.folge_spruenge = []
        # Jede Folge einmal, für die Erklärung unter dem Editor.
        self.folgen = []

    @property
    def bloecke(self):
        """Der globale Teil und danach jeder Modus — in Quelltextreihenfolge."""
        return [(None, self.teile)] + [(m, m.teile) for m in self.modi]

    @property
    def regeln(self):
        alle = []
        for _, teile in self.bloecke:
            alle.extend(t for t in teile if isinstance(t, Regel))
        return alle

    @property
    def python_bloecke(self):
        alle = []
        for _, teile in self.bloecke:
            alle.extend(t for t in teile if isinstance(t, PythonBlock))
        return alle

    @property
    def hat_modi(self):
        return bool(self.modi)

    def modus_namen(self):
        return [m.name for m in self.modi]

    @property
    def gueltig(self):
        return not self.fehler

    def als_dict(self, kosten=None):
        from .kosten import aktion_kosten
        return {
            "gueltig": self.gueltig,
            "modi": [{"name": m.name, "zeile": m.zeile} for m in self.modi
                     if not m.versteckt],
            "konstanten": [{"name": k.name, "zeile": k.zeile} for k in self.konstanten],
            "regeln": [
                {"nummer": r.nummer, "zeile": r.zeile, "art": r.art, "quelle": r.quelle,
                 "modus": r.modus, "kosten": aktion_kosten(r.aktion, kosten),
                 "folge": r.folge}
                for r in self.regeln
            ],
            "erklaerungen": [folge_erklaeren(self, f) for f in self.folgen],
            "python_bloecke": len(self.python_bloecke),
            "fehler": [f.als_dict() for f in self.fehler],
            "hinweise": [h.als_dict() for h in self.hinweise],
        }


# --------------------------------------------------------------------- Zeilenparser

class Zeilenleser:
    def __init__(self, tokens, zeilennummer, konstanten=(), in_formel=False):
        self.tokens = tokens
        self.stelle = 0
        self.zeile = zeilennummer
        self.konstanten = set(konstanten)
        self.in_formel = in_formel

    def fertig(self):
        return self.stelle >= len(self.tokens)

    def schau(self, versatz=0):
        stelle = self.stelle + versatz
        return self.tokens[stelle] if stelle < len(self.tokens) else None

    def nimm(self):
        token = self.schau()
        if token is not None:
            self.stelle += 1
        return token

    def ist_wort(self, *woerter):
        token = self.schau()
        return token is not None and token.art == "wort" and token.wert in woerter

    def nimm_wort(self, *woerter):
        if self.ist_wort(*woerter):
            return self.nimm()
        return None

    def ist_sym(self, *symbole):
        token = self.schau()
        return token is not None and token.art == "sym" and token.wert in symbole

    def nimm_sym(self, *symbole):
        if self.ist_sym(*symbole):
            return self.nimm()
        return None

    def fehler(self, text, **rest):
        token = self.schau()
        spalte = token.spalte if token else None
        return RegelFehler(self.zeile, text, spalte=spalte, **rest)

    def unbekanntes_wort(self, token, bekannte, was, beispiel=None):
        return RegelFehler(
            self.zeile,
            "%s `%s` kenne ich nicht." % (was, token.roh),
            vorschlag=vorschlag(token.wert, bekannte),
            spalte=token.spalte,
            beispiel=beispiel)

    def alt_pruefen(self, token):
        """`WENN` und Geschwister gibt es nicht mehr — aber wir sagen, wie es heißt."""
        if token is not None and token.art == "wort" and token.wert in ALTE_SCHLUESSELWOERTER:
            neu = ALTE_SCHLUESSELWOERTER[token.wert]
            raise RegelFehler(
                self.zeile,
                "`%s` heißt jetzt `%s`." % (token.roh.upper(), neu),
                spalte=token.spalte,
                beispiel="IF akku < 30 THEN fahre_zu depot")


# --------------------------------------------------------------------- Ziele

def muell_argumente_lesen(leser, ziel_beispiel):
    """Die Klammern hinter naechster_muell: Sorte und/oder in_zone."""
    sorte = None
    sorte_token = None
    nur_in_zone = False

    def zweite_sorte(token):
        raise RegelFehler(
            leser.zeile,
            "Nur eine Sorte erlaubt — zusammen mit `in_zone` geht höchstens eine Sorte, "
            "z.B. `naechster_muell(metall, in_zone)`.",
            spalte=token.spalte, beispiel=ziel_beispiel)

    def zweites_in_zone(token):
        raise RegelFehler(
            leser.zeile,
            "Zu viele Argumente: `in_zone` steht schon da.",
            spalte=token.spalte, beispiel=ziel_beispiel)

    if leser.nimm_sym("("):
        while True:
            inhalt = leser.nimm()
            if inhalt is None or inhalt.art != "wort":
                raise RegelFehler(leser.zeile,
                                  "In den Klammern muss eine Müllsorte oder `in_zone` stehen.",
                                  beispiel=ziel_beispiel)
            if inhalt.wert == "in_zone":
                if nur_in_zone:
                    zweites_in_zone(inhalt)
                nur_in_zone = True
            elif inhalt.wert in SORTEN:
                if sorte is not None:
                    zweite_sorte(inhalt)
                sorte, sorte_token = SORTEN[inhalt.wert], inhalt
            else:
                raise leser.unbekanntes_wort(inhalt, set(SORTEN) | {"in_zone"},
                                             "Die Müllsorte")
            if leser.nimm_sym(","):
                continue
            break
        if not leser.nimm_sym(")"):
            raise RegelFehler(leser.zeile, "Hier fehlt die schließende Klammer `)`.",
                              beispiel=ziel_beispiel)
    while leser.ist_wort("in_zone", *SORTEN):
        weiter = leser.nimm()
        if weiter.wert == "in_zone":
            if nur_in_zone:
                zweites_in_zone(weiter)
            nur_in_zone = True
        else:
            if sorte is not None:
                zweite_sorte(weiter)
            sorte, sorte_token = SORTEN[weiter.wert], weiter

    if sorte == "ballen":
        raise RegelFehler(
            leser.zeile,
            "Ballen liegen nie auf dem Feld — sie entstehen erst beim Pressen in eurer "
            "Ladung. Als Ziel geht `ballen` deshalb nicht.",
            spalte=sorte_token.spalte, beispiel="fahre_zu naechster_muell(metall)")
    return sorte, nur_in_zone


def ziel_lesen(leser):
    token = leser.nimm()
    if token is None:
        raise RegelFehler(leser.zeile, "Hier fehlt ein Ziel.",
                          beispiel="fahre_zu depot")
    if token.art != "wort":
        raise RegelFehler(leser.zeile, "`%s` ist kein Ziel." % token.roh,
                          spalte=token.spalte, beispiel="fahre_zu naechster_muell")

    wort = token.wert
    if wort == "depot":
        return Knoten("ziel", was="depot")
    if wort == "gegner":
        return Knoten("ziel", was="gegner")
    if wort == "zone":
        return Knoten("ziel", was="zone")
    if wort in ("naechster_muell", "muell"):
        sorte, nur_in_zone = muell_argumente_lesen(
            leser, "fahre_zu naechster_muell(metall)")
        return Knoten("ziel", was="muell", sorte=sorte, nur_in_zone=nur_in_zone,
                      formel=None)
    if wort == "best":
        return bestes_ziel_lesen(leser)
    if wort == "weg_von":
        geklammert = bool(leser.nimm_sym("("))
        ziel = leser.nimm()
        if ziel is None:
            raise RegelFehler(leser.zeile, "Nach `weg_von` fehlt `gegner`.",
                              beispiel="fahre_zu weg_von gegner")
        if ziel.art != "wort" or ziel.wert != "gegner":
            raise RegelFehler(leser.zeile, "`weg_von` gilt nur für `gegner`.",
                              spalte=ziel.spalte,
                              beispiel="fahre_zu weg_von gegner")
        if geklammert and not leser.nimm_sym(")"):
            raise RegelFehler(leser.zeile, "Hier fehlt die schließende Klammer `)`.",
                              beispiel="fahre_zu weg_von(gegner)")
        return Knoten("ziel", was="weg_von_gegner")
    if wort == "feld":
        if not leser.nimm_sym("("):
            raise RegelFehler(leser.zeile, "`feld` braucht Klammern mit zwei Zahlen.",
                              beispiel="fahre_zu feld(12, 8)")
        x = leser.nimm()
        komma = leser.nimm_sym(",")
        y = leser.nimm()
        if x is None or x.art != "zahl" or komma is None or y is None or y.art != "zahl":
            raise RegelFehler(leser.zeile, "`feld` braucht zwei Zahlen, durch Komma getrennt.",
                              beispiel="fahre_zu feld(12, 8)")
        if leser.nimm_sym(","):
            raise RegelFehler(leser.zeile,
                              "Zu viele Argumente: `feld` braucht genau zwei Zahlen.",
                              beispiel="fahre_zu feld(12, 8)")
        if not leser.nimm_sym(")"):
            raise RegelFehler(leser.zeile, "Hier fehlt die schließende Klammer `)`.",
                              beispiel="fahre_zu feld(12, 8)")
        return Knoten("ziel", was="feld", x=x.wert, y=y.wert)
    raise leser.unbekanntes_wort(token, ZIELWOERTER | {"best"}, "Das Ziel")


BEST_BEISPIEL = "fahre_zu BEST muell BY wert - 3 * abstand"


def bestes_ziel_lesen(leser):
    """`BEST muell BY <formel>` — das Stück mit dem höchsten Ergebnis gewinnt."""
    if not leser.ist_wort("naechster_muell", "muell"):
        token = leser.schau()
        raise RegelFehler(
            leser.zeile,
            "Nach `BEST` kommt `muell` — nur unter Müllstücken lässt sich rechnen.",
            spalte=token.spalte if token else None, beispiel=BEST_BEISPIEL)
    leser.nimm()
    sorte, nur_in_zone = muell_argumente_lesen(leser, BEST_BEISPIEL)
    if not leser.nimm_wort("by"):
        token = leser.schau()
        raise RegelFehler(
            leser.zeile,
            "Nach `BEST muell` fehlt `BY` und die Rechnung, nach der ausgewählt wird.",
            spalte=token.spalte if token else None, beispiel=BEST_BEISPIEL)
    formel_leser = Zeilenleser(leser.tokens, leser.zeile, leser.konstanten, in_formel=True)
    formel_leser.stelle = leser.stelle
    formel = ausdruck_lesen(formel_leser)
    leser.stelle = formel_leser.stelle
    return Knoten("ziel", was="muell", sorte=sorte, nur_in_zone=nur_in_zone, formel=formel)


# --------------------------------------------------------------------- Rechnen

def ausdruck_lesen(leser):
    links = produkt_lesen(leser)
    while leser.ist_sym("+", "-"):
        op = leser.nimm().wert
        rechts = produkt_lesen(leser)
        links = Knoten("rechnung", op=op, links=links, rechts=rechts)
    return links


def produkt_lesen(leser):
    links = faktor_lesen(leser)
    while leser.ist_sym("*", "/", "%"):
        op = leser.nimm().wert
        rechts = faktor_lesen(leser)
        if op in ("/", "%") and rechts.art == "zahl" and rechts.wert == 0:
            raise RegelFehler(leser.zeile, "Durch 0 kann man nicht teilen.",
                              beispiel="wert / 2")
        links = Knoten("rechnung", op=op, links=links, rechts=rechts)
    return links


def konstante_ausdruck_pruefen(knoten, zeilennummer):
    """In `LET` dürfen nur Zahlen und andere Konstanten stehen.

    Alles andere (`akku`, `anzahl(...)`, `abstand_zu ...`) ändert sich erst im
    Spiel. Stünde es in einer `LET`-Zeile, würde es beim Laden der Abgabedatei
    ausgewertet — und das kann nicht gutgehen.
    """
    if knoten.art == "negativ":
        return konstante_ausdruck_pruefen(knoten.inhalt, zeilennummer)
    if knoten.art == "rechnung":
        konstante_ausdruck_pruefen(knoten.links, zeilennummer)
        konstante_ausdruck_pruefen(knoten.rechts, zeilennummer)
        return
    if knoten.art in ("zahl", "konstante"):
        return
    raise RegelFehler(
        zeilennummer,
        "In einer `LET`-Zeile dürfen nur Zahlen und andere Konstanten stehen — "
        "Werte wie `akku` oder `anzahl(...)` ändern sich erst im Spiel.",
        beispiel="LET grenze = 30")


def fehlender_wert(leser):
    """Der Fehler, wenn an dieser Stelle gar kein Wert stehen kann.

    Vor `THEN` ist „Den Wert `THEN` kenne ich nicht" irreführend — dort fehlt
    schlicht der Wert. Dasselbe gilt für die Verknüpfungen, die schließende Klammer
    und das Zeilenende.
    """
    vorher = leser.tokens[leser.stelle - 1] if leser.stelle else None
    if vorher is not None and vorher.art == "sym" and vorher.wert in VERGLEICHE:
        text = "Nach dem Vergleichszeichen fehlt ein Wert (Zahl oder Bedingung)."
    else:
        text = "Hier fehlt ein Wert (Zahl oder Bedingung)."
    token = leser.schau()
    return RegelFehler(
        leser.zeile, text,
        spalte=token.spalte if token else None,
        beispiel=BEST_BEISPIEL if leser.in_formel else "IF akku < 30 THEN fahre_zu depot")


def faktor_lesen(leser):
    if leser.nimm_sym("-"):
        return Knoten("negativ", inhalt=faktor_lesen(leser))
    if leser.nimm_sym("+"):
        return faktor_lesen(leser)
    if leser.nimm_sym("("):
        inhalt = ausdruck_lesen(leser)
        if not leser.nimm_sym(")"):
            raise RegelFehler(leser.zeile, "Hier fehlt die schließende Klammer `)`.")
        return inhalt

    token = leser.schau()
    if token is None or (token.art == "wort" and token.wert in
                         ("then", "and", "or", "else", "by")) \
            or (token.art == "sym" and token.wert in (")", ",")):
        raise fehlender_wert(leser)
    if token.art == "zahl":
        leser.nimm()
        return Knoten("zahl", wert=token.wert)
    if token.art != "wort":
        raise RegelFehler(leser.zeile,
                          "`%s` ist hier kein Wert, mit dem sich rechnen lässt." % token.roh,
                          spalte=token.spalte,
                          beispiel="IF akku < 30 THEN fahre_zu depot")

    leser.alt_pruefen(token)
    wort = token.wert

    if wort in ZAHLWERTE:
        leser.nimm()
        return Knoten("zahlwert", name=wort)
    if wort == "abstand_zu":
        leser.nimm()
        return Knoten("abstand", ziel=ziel_lesen(leser))
    if wort == "anzahl":
        leser.nimm()
        if not leser.nimm_sym("("):
            raise RegelFehler(leser.zeile, "`anzahl` braucht Klammern mit einer Müllsorte.",
                              beispiel="IF anzahl(elektro) > 0 THEN fahre_zu depot")
        sorte = leser.nimm()
        if sorte is None or sorte.art != "wort":
            raise RegelFehler(leser.zeile, "In den Klammern muss eine Müllsorte stehen.",
                              beispiel="IF anzahl(elektro) > 0 THEN fahre_zu depot")
        if sorte.wert not in SORTEN:
            raise leser.unbekanntes_wort(
                sorte, set(SORTEN), "Die Müllsorte",
                beispiel="IF anzahl(elektro) > 0 THEN fahre_zu depot")
        if not leser.nimm_sym(")"):
            raise RegelFehler(leser.zeile, "Hier fehlt die schließende Klammer `)`.",
                              beispiel="IF anzahl(elektro) > 0 THEN fahre_zu depot")
        return Knoten("anzahl", sorte=SORTEN[sorte.wert])
    if wort in leser.konstanten:
        leser.nimm()
        return Knoten("konstante", name=wort)
    if wort in FORMELWOERTER:
        if not leser.in_formel:
            raise RegelFehler(
                leser.zeile,
                "`%s` gibt es nur in der Rechnung hinter `BY`." % token.roh,
                spalte=token.spalte, beispiel=BEST_BEISPIEL)
        leser.nimm()
        return Knoten("formelwert", name=wort)
    if wort in WORTFRAGEN:
        raise RegelFehler(
            leser.zeile,
            "`%s` liefert ein Wort, keine Zahl — vergleiche es mit `==` oder `!=`."
            % token.roh,
            spalte=token.spalte, beispiel=WORTFRAGE_BEISPIEL[wort])
    if wort in FLAGGEN or wort == "habe" or wort == "random":
        raise RegelFehler(
            leser.zeile,
            "`%s` ist keine Zahl, sondern eine Ja/Nein-Frage — damit lässt sich nicht "
            "rechnen." % token.roh,
            spalte=token.spalte, beispiel="IF %s THEN fahre_zu depot" % token.roh)

    bekannte = (ZAHLWERTE | FLAGGEN | {"abstand_zu", "anzahl", "habe", "random"}
                | set(leser.konstanten))
    if leser.in_formel:
        bekannte = bekannte | FORMELWOERTER
    raise leser.unbekanntes_wort(token, bekannte, "Den Wert")


# --------------------------------------------------------------------- Bedingungen

def bedingung_lesen(leser):
    return oder_lesen(leser)


def oder_lesen(leser):
    links = und_lesen(leser)
    while leser.nimm_wort("or"):
        rechts = und_lesen(leser)
        links = Knoten("oder", links=links, rechts=rechts)
    return links


def und_lesen(leser):
    links = nicht_lesen(leser)
    while leser.nimm_wort("and"):
        rechts = nicht_lesen(leser)
        links = Knoten("und", links=links, rechts=rechts)
    return links


def nicht_lesen(leser):
    if leser.nimm_wort("not"):
        return Knoten("nicht", inhalt=nicht_lesen(leser))
    return grund_lesen(leser)


def grund_lesen(leser):
    if leser.ist_sym("("):
        # `(akku < 30 OR ...)` oder `(akku + 5) > 30`? Erst als Bedingung versuchen,
        # und wenn danach ein Vergleich folgt, war es doch eine Rechnung.
        marke = leser.stelle
        try:
            leser.nimm()
            inhalt = bedingung_lesen(leser)
            if leser.nimm_sym(")") and not leser.ist_sym(*VERGLEICHE):
                return inhalt
        except RegelFehler:
            pass
        leser.stelle = marke
        return vergleich_lesen(leser)

    token = leser.schau()
    if token is None:
        raise RegelFehler(leser.zeile, "Nach `IF` fehlt eine Bedingung.",
                          beispiel="IF akku < 30 THEN fahre_zu depot")
    leser.alt_pruefen(token)
    if token.art != "wort":
        return vergleich_lesen(leser)

    wort = token.wert

    if wort in FLAGGEN:
        leser.nimm()
        return Knoten("flagge", name=wort)

    if wort == "habe":
        leser.nimm()
        if not leser.nimm_sym("("):
            raise RegelFehler(leser.zeile, "`habe` braucht Klammern mit einer Müllsorte.",
                              beispiel="IF habe(elektro) THEN fahre_zu depot")
        sorte = leser.nimm()
        if sorte is None or sorte.art != "wort":
            raise RegelFehler(leser.zeile, "In den Klammern muss eine Müllsorte stehen.",
                              beispiel="IF habe(elektro) THEN fahre_zu depot")
        if sorte.wert not in SORTEN:
            raise leser.unbekanntes_wort(sorte, set(SORTEN), "Die Müllsorte")
        if not leser.nimm_sym(")"):
            raise RegelFehler(leser.zeile, "Hier fehlt die schließende Klammer `)`.",
                              beispiel="IF habe(elektro) THEN fahre_zu depot")
        return Knoten("habe", sorte=SORTEN[sorte.wert])

    if wort == "random":
        leser.nimm()
        if not leser.nimm_sym("("):
            raise RegelFehler(leser.zeile, "`RANDOM` braucht Klammern mit einer Prozentzahl.",
                              beispiel="IF RANDOM(30) THEN fahre oben")
        zahl = leser.nimm()
        if zahl is None or zahl.art != "zahl" or zahl.wert > 100:
            raise RegelFehler(leser.zeile,
                              "In den Klammern steht, wie oft die Regel greifen soll — "
                              "eine Prozentzahl von 0 bis 100.",
                              beispiel="IF RANDOM(30) THEN fahre oben")
        if not leser.nimm_sym(")"):
            raise RegelFehler(leser.zeile, "Hier fehlt die schließende Klammer `)`.",
                              beispiel="IF RANDOM(30) THEN fahre oben")
        return Knoten("random", prozent=zahl.wert)

    if wort in WORTFRAGEN:
        return wortvergleich_lesen(leser)
    # `links == richtung_zu depot`: das Wort darf auch vorne stehen.
    danach, frage = leser.schau(1), leser.schau(2)
    if danach is not None and danach.art == "sym" and danach.wert in ("==", "!=", "=") \
            and frage is not None and frage.art == "wort" and frage.wert in WORTFRAGEN:
        return wortvergleich_lesen(leser)

    if wort == "ladung" and leser.schau(1) is not None and \
            leser.schau(1).art == "wort" and leser.schau(1).wert in ("ist", "voll", "leer"):
        raise RegelFehler(
            leser.zeile,
            "`ladung ist voll` heißt jetzt `ladung_ist_voll` (und `ladung_ist_leer`).",
            spalte=token.spalte,
            beispiel="IF ladung_ist_voll THEN fahre_zu depot")

    return vergleich_lesen(leser)


def vergleich_lesen(leser):
    links = ausdruck_lesen(leser)
    symbol = leser.schau()
    if symbol is None or symbol.art != "sym" or symbol.wert not in VERGLEICHE:
        if symbol is not None and symbol.art == "wort":
            leser.alt_pruefen(symbol)
        if symbol is not None and symbol.art == "sym" and symbol.wert == "=":
            raise RegelFehler(
                leser.zeile,
                "Vergleichen heißt `==` mit zwei Gleichheitszeichen. Ein einzelnes `=` "
                "gibt es nur bei `LET`.",
                spalte=symbol.spalte, beispiel="IF ladung == 6 THEN fahre_zu depot")
        if symbol is not None and symbol.art == "sym" and symbol.wert == "<>":
            raise RegelFehler(leser.zeile, "`ungleich` schreibt man `!=`.",
                              spalte=symbol.spalte,
                              beispiel="IF ladung != 0 THEN fahre_zu depot")
        raise RegelFehler(
            leser.zeile,
            "Hier fehlt ein Vergleich wie `<`, `>` oder `==`.",
            spalte=symbol.spalte if symbol else None,
            beispiel="IF akku < 30 THEN fahre_zu depot")
    leser.nimm()
    rechts = ausdruck_lesen(leser)
    return Knoten("vergleich", links=links, op=VERGLEICHE[symbol.wert], rechts=rechts)


# --------------------------------------------------------------------- Wortfragen

WORTFRAGE_BEISPIEL = {
    "richtung_zu": "IF richtung_zu depot == links THEN GOTO ausweichen",
    "objekt_in_richtung": "IF objekt_in_richtung(oben) == wand THEN fahre unten",
}


def wortseite_lesen(leser):
    """Eine Seite eines Wortvergleichs: eine der beiden Fragen oder ein Wort."""
    token = leser.schau()
    if token is None:
        raise RegelFehler(leser.zeile, "Nach dem Vergleichszeichen fehlt ein Wort.",
                          beispiel=WORTFRAGE_BEISPIEL["richtung_zu"])
    if token.art == "wort" and token.wert == "richtung_zu":
        leser.nimm()
        return Knoten("richtungsfrage", ziel=ziel_lesen(leser))
    if token.art == "wort" and token.wert == "objekt_in_richtung":
        leser.nimm()
        return Knoten("objektfrage", richtung=objekt_richtung_lesen(leser))
    if token.art != "wort":
        raise RegelFehler(
            leser.zeile,
            "Hier gehört ein Wort hin, etwa `links` oder `frei` — keine Zahl.",
            spalte=token.spalte, beispiel=WORTFRAGE_BEISPIEL["objekt_in_richtung"])
    leser.nimm()
    return Knoten("wort", token=token)


def objekt_richtung_lesen(leser):
    """Die Klammer hinter `objekt_in_richtung`: eine Richtung oder `richtung_zu …`."""
    beispiel = WORTFRAGE_BEISPIEL["objekt_in_richtung"]
    geklammert = bool(leser.nimm_sym("("))
    if leser.ist_wort("richtung_zu"):
        leser.nimm()
        richtung = Knoten("richtungsfrage", ziel=ziel_lesen(leser))
    else:
        token = leser.nimm()
        if token is None or token.art != "wort":
            raise RegelFehler(
                leser.zeile,
                "`objekt_in_richtung` braucht eine Richtung: oben, unten, links, rechts "
                "— oder `richtung_zu` mit einem Ziel.", beispiel=beispiel)
        if token.wert not in RICHTUNGEN:
            raise leser.unbekanntes_wort(token, set(RICHTUNGEN) | {"richtung_zu"},
                                         "Die Richtung", beispiel=beispiel)
        richtung = Knoten("wortwert", wert=RICHTUNGEN[token.wert])
    if geklammert and not leser.nimm_sym(")"):
        raise RegelFehler(leser.zeile, "Hier fehlt die schließende Klammer `)`.",
                          beispiel=beispiel)
    return richtung


def wort_als_antwort(leser, knoten, art):
    """Prüft ein Wort gegen das, was die Frage überhaupt antworten kann."""
    token = knoten.token
    if art == "richtung":
        if token.wert in RICHTUNGEN:
            return Knoten("wortwert", wert=RICHTUNGEN[token.wert])
        if token.wert in RICHTUNGSANTWORTEN:
            return Knoten("wortwert", wert=token.wert)
        raise leser.unbekanntes_wort(
            token, set(RICHTUNGEN) | RICHTUNGSANTWORTEN,
            "`richtung_zu` antwortet oben, unten, links, rechts, hier oder keine — "
            "die Antwort", beispiel=WORTFRAGE_BEISPIEL["richtung_zu"])
    if token.wert in OBJEKTE:
        return Knoten("wortwert", wert=token.wert)
    if token.wert in SORTEN:
        if SORTEN[token.wert] == "ballen":
            raise RegelFehler(
                leser.zeile,
                "Ballen liegen nie auf dem Feld — sie entstehen erst beim Pressen.",
                spalte=token.spalte, beispiel=WORTFRAGE_BEISPIEL["objekt_in_richtung"])
        return Knoten("wortwert", wert=SORTEN[token.wert])
    raise leser.unbekanntes_wort(
        token, OBJEKTE | (set(SORTEN) - {"ballen", "gepresst"}),
        "`objekt_in_richtung` antwortet frei, wand, gegner, depot oder mit einer "
        "Müllsorte — die Antwort", beispiel=WORTFRAGE_BEISPIEL["objekt_in_richtung"])


def wortvergleich_lesen(leser):
    """`richtung_zu depot == links` oder `objekt_in_richtung(oben) != frei`."""
    links = wortseite_lesen(leser)
    symbol = leser.schau()
    frage = links if links.art != "wort" else None
    wortfrage = "objekt_in_richtung" if (frage and frage.art == "objektfrage") \
        else "richtung_zu"
    beispiel = WORTFRAGE_BEISPIEL[wortfrage]
    if symbol is not None and symbol.art == "sym" and symbol.wert == "=":
        raise RegelFehler(
            leser.zeile,
            "Vergleichen heißt `==` mit zwei Gleichheitszeichen. Ein einzelnes `=` "
            "gibt es nur bei `LET`.", spalte=symbol.spalte, beispiel=beispiel)
    if symbol is None or symbol.art != "sym" or symbol.wert not in ("==", "!="):
        if symbol is not None and symbol.art == "sym" and symbol.wert in VERGLEICHE:
            text = ("Eine Richtung oder ein Objekt ist keine Zahl — vergleichen geht nur "
                    "mit `==` (gleich) oder `!=` (ungleich).")
        else:
            text = "Hier fehlt `==` oder `!=` und das Wort, mit dem verglichen wird."
        raise RegelFehler(leser.zeile, text,
                          spalte=symbol.spalte if symbol else None, beispiel=beispiel)
    leser.nimm()
    rechts = wortseite_lesen(leser)

    def art_von(knoten):
        if knoten.art == "richtungsfrage":
            return "richtung"
        if knoten.art == "objektfrage":
            return "objekt"
        return None

    arten = [art_von(links), art_von(rechts)]
    if arten == [None, None]:
        raise RegelFehler(
            leser.zeile,
            "Hier werden zwei Wörter verglichen — eins davon muss `richtung_zu` oder "
            "`objekt_in_richtung` sein.", beispiel=beispiel)
    if None not in arten and arten[0] != arten[1]:
        raise RegelFehler(
            leser.zeile,
            "Eine Richtung lässt sich nicht mit einem Objekt vergleichen.",
            beispiel=beispiel)
    art = arten[0] or arten[1]
    if links.art == "wort":
        links = wort_als_antwort(leser, links, art)
    if rechts.art == "wort":
        rechts = wort_als_antwort(leser, rechts, art)
    return Knoten("wortvergleich", links=links, op=symbol.wert, rechts=rechts)


# --------------------------------------------------------------------- Aktionen

def aktion_lesen(leser, modus_namen=()):
    token = leser.nimm()
    if token is None:
        raise RegelFehler(leser.zeile, "Hier fehlt noch, was der Roboter tun soll.",
                          beispiel="IF akku < 30 THEN fahre_zu depot")
    leser.alt_pruefen(token)
    if token.art != "wort":
        if token.art == "sym" and token.wert in VERGLEICHE:
            raise RegelFehler(
                leser.zeile,
                "`%s` ist ein Vergleich, keine Aktion — die Bedingung endet zu früh."
                % token.roh,
                spalte=token.spalte, beispiel="IF gegner_sichtbar THEN warte")
        raise RegelFehler(leser.zeile, "`%s` ist keine Aktion." % token.roh,
                          spalte=token.spalte, beispiel="fahre_zu depot")

    wort = token.wert
    if wort == "warte":
        return Knoten("warte")
    if wort == "presse":
        return Knoten("presse")
    if wort == "goto":
        ziel = leser.nimm()
        if ziel is None or ziel.art != "wort":
            raise RegelFehler(leser.zeile, "Nach `GOTO` fehlt der Name eines Modus.",
                              beispiel="IF ladung_ist_voll THEN GOTO heimweg")
        return Knoten("goto", modus=ziel.wert, roh=ziel.roh, spalte=ziel.spalte)
    if wort == "ramme":
        leser.nimm_wort("gegner")
        return Knoten("fahre_zu", ziel=Knoten("ziel", was="gegner"), rammen=True)
    if wort == "fahre_zu":
        if leser.fertig():
            raise RegelFehler(leser.zeile, "`fahre_zu` braucht ein Ziel.",
                              beispiel="fahre_zu depot")
        return Knoten("fahre_zu", ziel=ziel_lesen(leser), rammen=False)
    if wort == "fahre":
        richtung = leser.nimm()
        if richtung is None or richtung.art != "wort":
            raise RegelFehler(leser.zeile,
                              "`fahre` braucht eine Richtung: oben, unten, links oder rechts.",
                              beispiel="fahre rechts")
        if richtung.wert in RICHTUNGEN:
            return Knoten("fahre", richtung=RICHTUNGEN[richtung.wert])
        if richtung.wert in ZIELWOERTER:
            raise RegelFehler(
                leser.zeile,
                "`fahre` erwartet eine Richtung. Zu einem Ziel fährt man mit `fahre_zu`.",
                spalte=richtung.spalte, beispiel="fahre_zu %s" % richtung.roh)
        raise leser.unbekanntes_wort(richtung, set(RICHTUNGEN), "Die Richtung")
    raise leser.unbekanntes_wort(token, AKTIONSWOERTER, "Die Aktion")


# --------------------------------------------------------------------- Folgen

FOLGE_BEISPIEL = "IF abstand_zu depot == 0 THEN fahre rechts, rechts, unten, GOTO sammeln"

# Ab so vielen Schritten erinnert ein Hinweis daran, dass eine Folge nicht hinschaut.
# Kein Spielwert, nur eine Schwelle für die Werkstatt.
FOLGE_LANG_AB = 6

GEGENRICHTUNG = {"oben": "unten", "unten": "oben", "links": "rechts", "rechts": "links"}
VERSATZ = {"oben": (0, -1), "unten": (0, 1), "links": (-1, 0), "rechts": (1, 0)}
ZIFFERN = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"


def schritt_text(leser, von, bis, ersatz=None):
    """Der Originaltext der Tokens von..bis — für Kommentare und die Anzeige."""
    if ersatz:
        return ersatz
    tokens = leser.tokens[von:bis]
    if not tokens:
        return ""
    zeile = getattr(leser, "text", None)
    if zeile is None:
        return " ".join(t.roh for t in tokens)
    return zeile[tokens[0].spalte - 1:tokens[-1].spalte - 1 + len(tokens[-1].roh)]


def aktionen_lesen(leser):
    """Eine Aktion — oder mehrere, mit Komma getrennt. Gibt [(knoten, text)] zurück.

    In einer Folge darf `fahre` fehlen: `fahre links, links, oben` ist dasselbe wie
    dreimal `fahre ...`. Allein (ohne Komma) bleibt `links` ein Fehler wie bisher.
    """
    schritte = []
    while True:
        token = leser.schau()
        danach = leser.schau(1)
        kurz = (token is not None and token.art == "wort" and token.wert in RICHTUNGEN
                and (schritte or (danach is not None and danach.art == "sym"
                                  and danach.wert == ",")))
        start = leser.stelle
        if kurz:
            leser.nimm()
            knoten = Knoten("fahre", richtung=RICHTUNGEN[token.wert])
            text = "fahre %s" % RICHTUNGEN[token.wert]
        else:
            knoten = aktion_lesen(leser)
            text = schritt_text(leser, start, leser.stelle)
        schritte.append((knoten, text))
        if not leser.nimm_sym(","):
            return schritte
        if leser.fertig():
            raise RegelFehler(leser.zeile, "Nach dem letzten Komma fehlt noch eine Aktion.",
                              beispiel=FOLGE_BEISPIEL)


def regel_aus_aktionen(nummer, art, bedingung, schritte, quelle, zeilennummer, modus,
                       bedingung_text=None):
    """Eine Aktion ergibt eine normale Regel, mehrere eine Regel mit einer Folge."""
    if len(schritte) == 1:
        aktion = schritte[0][0]
    else:
        for index, (knoten, _) in enumerate(schritte):
            if knoten.art == "goto" and index < len(schritte) - 1:
                raise RegelFehler(
                    zeilennummer,
                    "In einer Folge darf `GOTO` nur ganz am Ende stehen — danach ist der "
                    "Roboter ja schon in einem anderen Modus.",
                    spalte=knoten.spalte, beispiel=FOLGE_BEISPIEL)
        aktion = Knoten("folge", schritte=schritte)
    regel = Regel(nummer, art, bedingung, aktion, quelle, zeilennummer, modus)
    regel.bedingung_text = bedingung_text
    return regel


def folge_name(zeilennummer, schritt):
    return "folge_z%d_schritt%d" % (zeilennummer, schritt)


def folge_aufloesen(programm, regel, modus):
    """Macht aus einer Regel mit Folge eine Regel mit `GOTO` und je Schritt einen Modus.

        STATE ausweichen
          IF x THEN fahre links, fahre oben, GOTO sammeln

    wird zu

        STATE ausweichen
          IF x THEN GOTO folge_z2_schritt1
        STATE folge_z2_schritt1          (versteckt)
          PYTHON: self.modus = "folge_z2_schritt2"
          ELSE fahre links
        STATE folge_z2_schritt2          (versteckt)
          PYTHON: self.modus = "sammeln"
          ELSE fahre oben

    Der PYTHON-Teil schaltet schon auf den nächsten Schritt um, die ELSE-Regel liefert
    die Aktion für diesen Tick. So kostet jeder Schritt genau einen Tick, und im
    nächsten Tick geht es mit dem nächsten Schritt weiter.
    """
    zeile = regel.zeile
    if modus is None:
        raise RegelFehler(
            zeile,
            "Eine Folge (mehrere Aktionen mit Komma) geht nur innerhalb eines `STATE` — "
            "nach dem letzten Schritt geht es in diesem Modus weiter.",
            beispiel="STATE ausweichen")

    schritte = list(regel.aktion.schritte)
    sprung = None
    if schritte[-1][0].art == "goto":
        sprung = schritte.pop()[0]
        programm.folge_spruenge.append((zeile, sprung))
    if not schritte:
        raise RegelFehler(zeile, "In der Folge steht keine Aktion.", beispiel=FOLGE_BEISPIEL)

    belegt = set(programm.modus_namen())
    namen = []
    for index in range(1, len(schritte) + 1):
        name = folge_name(zeile, index)
        if name in belegt:
            raise RegelFehler(
                zeile,
                "Den Modus `%s` braucht die Folge in dieser Zeile selbst — gib deinem "
                "Modus einen anderen Namen." % name)
        namen.append(name)
    danach = sprung.modus if sprung else modus.name

    anzahl = len(schritte)
    for index, ((knoten, text), name) in enumerate(zip(schritte, namen)):
        naechster = namen[index + 1] if index + 1 < anzahl else danach
        wohin = ("dann Schritt %d" % (index + 2) if index + 1 < anzahl
                 else "danach weiter in Modus `%s`" % danach)
        versteckt = Modus(
            name, zeile,
            "Schritt %d von %d der Folge aus Zeile %d (Modus %s) — %s."
            % (index + 1, anzahl, zeile, modus.name, wohin),
            versteckt=True)
        versteckt.teile.append(PythonBlock(
            ['self.modus = "%s"    # im nächsten Tick: %s' % (naechster, wohin)], zeile))
        # Die Nummer wird am Ende vergeben, damit die sichtbaren Regeln ihre behalten.
        # `modus` ist der Modus, in dem die Folge steht — so zeigt ihn die Werkstatt an.
        schritt = Regel(
            None, "else", None, knoten,
            "%s   (Schritt %d/%d der Folge aus Zeile %d)" % (text, index + 1, anzahl, zeile),
            zeile, modus.name)
        schritt.folge = {"zeile": zeile, "schritt": index + 1, "von": anzahl,
                         "richtung": knoten.richtung if knoten.art == "fahre" else None}
        versteckt.teile.append(schritt)
        programm.modi.append(versteckt)

    programm.folgen.append({
        "zeile": zeile, "modus": modus.name, "art": regel.art,
        "bedingung": regel.bedingung_text, "schritte": schritte,
        "danach": danach, "mit_goto": sprung is not None})
    folge_hinweise(programm, zeile, schritte)
    regel.aktion = Knoten("goto", modus=namen[0], roh=namen[0], spalte=None, folge=True,
                          anzahl=anzahl, danach=danach)
    return regel


def folge_hinweise(programm, zeile, schritte):
    """Was an einer Folge schon beim Schreiben auffällt — Hinweise, keine Fehler."""
    richtungen = [k.richtung if k.art == "fahre" else None for k, _ in schritte]
    for index in range(1, len(richtungen)):
        vorher, jetzt = richtungen[index - 1], richtungen[index]
        if vorher and jetzt == GEGENRICHTUNG[vorher]:
            programm.hinweise.append(Hinweis(
                zeile,
                "In der Folge macht `%s` direkt nach `%s` den Schritt wieder rückgängig — "
                "das kostet zwei Züge für nichts." % (jetzt, vorher)))
            break
    else:
        # Nur Richtungen (und Warten/Pressen): Wo kommt der Roboter an?
        if all(k.art in ("fahre", "warte", "presse") for k, _ in schritte) \
                and sum(1 for r in richtungen if r) >= 2:
            dx = sum(VERSATZ[r][0] for r in richtungen if r)
            dy = sum(VERSATZ[r][1] for r in richtungen if r)
            if dx == 0 and dy == 0:
                programm.hinweise.append(Hinweis(
                    zeile,
                    "Nach dieser Folge steht dein Roboter wieder da, wo er angefangen hat."))
    if len(schritte) >= FOLGE_LANG_AB:
        programm.hinweise.append(Hinweis(
            zeile,
            "Eine Folge mit %d Schritten ist lang. Solange sie läuft, schaut dein Roboter "
            "nicht hin — was sich unterwegs ändert, merkt er erst danach." % len(schritte)))


def schritt_beschreiben(knoten, text):
    """Ein Schritt in Alltagssprache: „nach links", „warten", „`fahre_zu depot`"."""
    if knoten.art == "fahre":
        return "nach %s" % knoten.richtung
    if knoten.art == "warte":
        return "warten"
    if knoten.art == "presse":
        return "pressen"
    return "`%s`" % text


def folge_erklaeren(programm, folge):
    """Was eine Folge tut und was danach passiert — für den Kasten unter dem Editor."""
    schritte = folge["schritte"]
    if schritte and schritte[-1][0].art == "goto":
        schritte = schritte[:-1]
    anzahl = len(schritte)
    teile = []
    for index, (knoten, text) in enumerate(schritte):
        marke = ZIFFERN[index] if index < len(ZIFFERN) else "(%d)" % (index + 1)
        teile.append("%s %s" % (marke, schritt_beschreiben(knoten, text)))
    if folge["bedingung"]:
        wann = "Wenn `%s` stimmt" % folge["bedingung"]
    else:
        wann = "Wenn in Modus `%s` keine Regel davor greift" % folge["modus"]
    zeilen = [
        "Zeile %d ist eine Folge mit %d Zügen." % (folge["zeile"], anzahl),
        "%s, macht dein Roboter nacheinander: %s." % (wann, "  ".join(teile)),
        "Jeder Schritt ist ein eigener Zug. Dazwischen schaut er nicht hin: Ist ein Weg "
        "versperrt, bleibt er stehen und macht trotzdem mit dem nächsten Schritt weiter.",
    ]
    if any(k.art in ("fahre_zu",) for k, _ in schritte):
        zeilen.append("`fahre_zu …` ist auch in einer Folge nur ein Schritt — der Weg wird "
                      "in diesem Zug neu gesucht.")
    if folge["mit_goto"]:
        zeilen.append("Danach: wechselt er in den Modus `%s`." % folge["danach"])
    elif folge["bedingung"]:
        zeilen.append("Danach: ist er wieder in Modus `%s` und prüft dessen Regeln von oben. "
                      "Stimmt `%s` dann immer noch, fängt die Folge von vorn an."
                      % (folge["modus"], folge["bedingung"]))
    else:
        zeilen.append("Danach: ist er wieder in Modus `%s` und prüft dessen Regeln von oben. "
                      "Greift keine davor, fängt die Folge von vorn an." % folge["modus"])
    if any(isinstance(t, Regel) for t in programm.teile):
        zeilen.append("Deine Regeln vor dem ersten `STATE` werden trotzdem in jedem Zug zuerst "
                      "geprüft. Greift eine davon, gehört ihr der Zug und die Folge wartet; "
                      "springt sie mit `GOTO` in einen anderen Modus, ist die Folge "
                      "abgebrochen.")
    return {"zeile": folge["zeile"], "titel": zeilen[0], "text": "\n".join(zeilen[1:])}


# --------------------------------------------------------------------- Programm

def zerlegen_programm(quelltext):
    try:
        return _zerlegen_programm(quelltext)
    except RecursionError:
        programm = Programm()
        programm.fehler.append(RegelFehler(
            0, "Zu viele verschachtelte Klammern — so tief ist die Regel nicht lesbar."))
        return programm


def _zerlegen_programm(quelltext):
    programm = Programm()
    zeilen = quelltext.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    nummer = 0
    index = 0
    python_offen = None
    python_zeilen = []
    python_nummern = []
    modus = None                     # der Modus, in dem die nächsten Regeln landen

    while index < len(zeilen):
        rohzeile = zeilen[index]
        zeilennummer = index + 1
        index += 1

        if python_offen is not None:
            # `END # fertig` schließt den Block genauso wie `END` — das `#` ist ein
            # Python-Kommentar und darf die Schlusszeile nicht unkenntlich machen.
            wort = normal(rohzeile.split("#", 1)[0].strip())
            if wort in ("end", "end python"):
                ziel = modus.teile if modus else programm.teile
                ziel.append(PythonBlock(python_zeilen, python_offen, python_nummern))
                python_offen = None
                python_zeilen = []
                python_nummern = []
            elif wort in ("ende", "ende python"):
                programm.fehler.append(RegelFehler(
                    zeilennummer, "`ENDE` heißt jetzt `END`.",
                    beispiel="PYTHON ... END"))
                ziel = modus.teile if modus else programm.teile
                ziel.append(PythonBlock(python_zeilen, python_offen, python_nummern))
                python_offen = None
                python_zeilen = []
                python_nummern = []
            else:
                python_zeilen.append(rohzeile)
                python_nummern.append(zeilennummer)
            continue

        ohne_kommentar = rohzeile.split("#", 1)[0]
        if not ohne_kommentar.strip():
            continue

        if normal(ohne_kommentar.strip()) == "python":
            python_offen = zeilennummer
            python_zeilen = []
            python_nummern = []
            continue

        try:
            tokens = zerlegen(ohne_kommentar, zeilennummer)
        except RegelFehler as fehler:
            programm.fehler.append(fehler)
            continue
        if not tokens:
            continue

        namen = [k.name for k in programm.konstanten]
        leser = Zeilenleser(tokens, zeilennummer, namen)
        leser.text = ohne_kommentar

        gezaehlt = False
        try:
            if leser.ist_wort("state"):
                modus = modus_lesen(leser, programm, rohzeile.strip(), zeilennummer)
                continue
            if leser.ist_wort("let"):
                konstante_lesen(leser, programm, rohzeile.strip(), zeilennummer)
                continue
            nummer += 1
            gezaehlt = True
            regel = regel_lesen(leser, nummer, rohzeile.strip(), zeilennummer,
                                modus.name if modus else None)
            if regel.aktion.art == "folge":
                regel = folge_aufloesen(programm, regel, modus)
            (modus.teile if modus else programm.teile).append(regel)
        except RegelFehler as fehler:
            # Nur zurückzählen, wenn diese Zeile die Nummer überhaupt vergeben hat.
            # Eine kaputte STATE-/LET-Zeile tut das nicht.
            if gezaehlt:
                nummer -= 1
            programm.fehler.append(fehler)

    if python_offen is not None:
        programm.fehler.append(RegelFehler(
            python_offen, "Der PYTHON-Block wurde nie mit `END` geschlossen.",
            beispiel="PYTHON ... END"))

    # Die Schritte der Folgen bekommen ihre Nummern erst jetzt, hinter allen
    # sichtbaren Regeln — so bleibt „Regel 3" die dritte Regel im Quelltext.
    for versteckt in programm.modi:
        if versteckt.versteckt:
            for regel in versteckt.regeln:
                nummer += 1
                regel.nummer = nummer

    pruefen(programm)
    return programm


def modus_lesen(leser, programm, quelle, zeilennummer):
    leser.nimm()
    name = leser.nimm()
    if name is None or name.art != "wort":
        raise RegelFehler(zeilennummer, "Nach `STATE` fehlt der Name des Modus.",
                          beispiel="STATE sammeln")
    if name.wert in ALLE_WOERTER or name.wert in ALTE_SCHLUESSELWOERTER:
        raise RegelFehler(zeilennummer,
                          "`%s` ist schon ein Befehl — such dem Modus einen eigenen "
                          "Namen." % name.roh,
                          spalte=name.spalte, beispiel="STATE heimweg")
    versteckte = [m for m in programm.modi if m.versteckt and m.name == name.wert]
    if versteckte:
        raise RegelFehler(zeilennummer,
                          "Den Namen `%s` braucht schon die Folge aus Zeile %d — such "
                          "dem Modus einen anderen Namen." % (name.roh, versteckte[0].zeile),
                          spalte=name.spalte, beispiel="STATE heimweg")
    if name.wert in programm.modus_namen():
        raise RegelFehler(zeilennummer,
                          "Den Modus `%s` gibt es schon weiter oben." % name.roh,
                          spalte=name.spalte)
    rest_pruefen(leser, zeilennummer)
    modus = Modus(name.wert, zeilennummer, quelle)
    programm.modi.append(modus)
    return modus


def konstante_lesen(leser, programm, quelle, zeilennummer):
    leser.nimm()
    name = leser.nimm()
    if name is None or name.art != "wort":
        raise RegelFehler(zeilennummer, "Nach `LET` fehlt ein Name.",
                          beispiel="LET grenze = 30")
    if name.wert in ALLE_WOERTER or name.wert in ALTE_SCHLUESSELWOERTER \
            or name.wert in FORMELWOERTER:
        raise RegelFehler(zeilennummer,
                          "`%s` ist schon ein Befehl — such der Zahl einen eigenen "
                          "Namen." % name.roh,
                          spalte=name.spalte, beispiel="LET grenze = 30")
    if name.wert in RESERVIERTE_KONSTANTEN:
        raise RegelFehler(zeilennummer,
                          "`%s` vergibt die Werkstatt selbst — such der Zahl einen "
                          "anderen Namen." % name.roh.upper(),
                          spalte=name.spalte, beispiel="LET grenze = 30")
    if name.wert in [k.name for k in programm.konstanten]:
        raise RegelFehler(zeilennummer,
                          "`%s` steht schon weiter oben." % name.roh, spalte=name.spalte)
    if not leser.nimm_sym("="):
        raise RegelFehler(zeilennummer, "Nach dem Namen fehlt ein `=`.",
                          beispiel="LET grenze = 30")
    ausdruck = ausdruck_lesen(leser)
    rest_pruefen(leser, zeilennummer)
    konstante_ausdruck_pruefen(ausdruck, zeilennummer)
    programm.konstanten.append(Konstante(name.wert, ausdruck, zeilennummer, quelle))


def regel_lesen(leser, nummer, quelle, zeilennummer, modus=None):
    if leser.nimm_wort("if"):
        anfang = leser.stelle
        bedingung = bedingung_lesen(leser)
        text = schritt_text(leser, anfang, leser.stelle)
        leser.nimm_wort("then")
        if leser.fertig():
            raise RegelFehler(zeilennummer,
                              "Nach der Bedingung fehlt, was der Roboter tun soll.",
                              beispiel="IF akku < 30 THEN fahre_zu depot")
        schritte = aktionen_lesen(leser)
        rest_pruefen(leser, zeilennummer)
        return regel_aus_aktionen(nummer, "if", bedingung, schritte, quelle, zeilennummer,
                                  modus, text)

    if leser.nimm_wort("else"):
        if leser.nimm_wort("if"):
            anfang = leser.stelle
            bedingung = bedingung_lesen(leser)
            text = schritt_text(leser, anfang, leser.stelle)
            leser.nimm_wort("then")
            schritte = aktionen_lesen(leser)
            rest_pruefen(leser, zeilennummer)
            return regel_aus_aktionen(nummer, "if", bedingung, schritte, quelle,
                                      zeilennummer, modus, text)
        schritte = aktionen_lesen(leser)
        rest_pruefen(leser, zeilennummer)
        return regel_aus_aktionen(nummer, "else", None, schritte, quelle, zeilennummer,
                                  modus)

    token = leser.schau()
    leser.alt_pruefen(token)
    if token is not None and token.art == "wort" and token.wert in AKTIONSWOERTER:
        raise RegelFehler(
            zeilennummer,
            "Jede Regel fängt mit `IF` oder `ELSE` an.",
            spalte=token.spalte,
            beispiel="ELSE %s" % quelle.strip())
    raise RegelFehler(
        zeilennummer,
        "Jede Regel fängt mit `IF` oder `ELSE` an.",
        vorschlag=vorschlag(token.wert if token and token.art == "wort" else "",
                            {"if", "else", "state", "let", "python"}),
        spalte=token.spalte if token else None,
        beispiel="IF ladung_ist_voll THEN fahre_zu depot")


def rest_pruefen(leser, zeilennummer):
    if not leser.fertig():
        token = leser.schau()
        if token.art == "wort" and (token.wert in AKTIONSWOERTER or token.wert in RICHTUNGEN):
            raise RegelFehler(
                zeilennummer,
                "Nach der Aktion steht noch `%s`. Mehrere Aktionen hintereinander "
                "trennt man mit Komma — jede kostet einen eigenen Tick." % token.roh,
                spalte=token.spalte, beispiel=FOLGE_BEISPIEL)
        raise RegelFehler(
            zeilennummer,
            "Nach der Aktion steht noch `%s` — pro Zeile ist genau eine Regel erlaubt."
            % token.roh,
            spalte=token.spalte)


# --------------------------------------------------------------------- Prüfungen

def pruefen(programm):
    regeln = programm.regeln
    if not regeln and not programm.python_bloecke and not programm.fehler:
        programm.hinweise.append(Hinweis(
            0, "Es steht noch keine Regel da. Fang mit "
               "`ELSE fahre_zu naechster_muell` an."))
        return

    for modus, teile in programm.bloecke:
        block_pruefen(programm, modus, teile)

    if programm.hat_modi:
        modi_pruefen(programm)
    else:
        for regel in regeln:
            if regel.aktion.art == "goto":
                programm.fehler.append(RegelFehler(
                    regel.zeile,
                    "`GOTO` wechselt den Modus — aber es gibt noch keinen. Modi legt man "
                    "mit `STATE` an.",
                    beispiel="STATE heimweg"))
                break


def block_pruefen(programm, modus, teile):
    regeln = [t for t in teile if isinstance(t, Regel)]
    python_bloecke = [t for t in teile if isinstance(t, PythonBlock)]
    wo = "in Modus `%s`" % modus.name if modus else ""

    for index, regel in enumerate(regeln):
        if regel.art == "else" and index < len(regeln) - 1:
            programm.hinweise.append(Hinweis(
                regeln[index + 1].zeile,
                "Diese Regel wird nie erreicht: die `ELSE`-Regel in Zeile %d greift "
                "immer%s." % (regel.zeile, " " + wo if wo else "")))
            break

    if modus is None and programm.hat_modi:
        for regel in regeln:
            if regel.art == "else":
                programm.fehler.append(RegelFehler(
                    regel.zeile,
                    "Eine `ELSE`-Regel vor dem ersten `STATE` würde jeden Modus "
                    "überstimmen. Schreib sie in den Modus, in den sie gehört.",
                    beispiel="STATE sammeln"))
                break
        if regeln:
            programm.hinweise.append(Hinweis(
                regeln[0].zeile,
                "Diese Regel steht vor dem ersten `STATE` und wird darum in jedem Modus "
                "zuerst geprüft."))
        return

    if regeln and regeln[-1].art != "else" and not python_bloecke:
        programm.hinweise.append(Hinweis(
            regeln[-1].zeile,
            "Wenn keine Regel zutrifft, wartet der Roboter%s. Eine `ELSE`-Regel am Ende "
            "verhindert das." % (" " + wo if wo else "")))


def modi_pruefen(programm):
    namen = programm.modus_namen()
    sichtbare = [m.name for m in programm.modi if not m.versteckt]
    erreicht = {namen[0]}
    spruenge = [(regel.zeile, regel.aktion) for regel in programm.regeln
                if regel.aktion.art == "goto"] + programm.folge_spruenge
    for zeile, sprung in spruenge:
        if sprung.modus not in namen:
            programm.fehler.append(RegelFehler(
                zeile,
                "Den Modus `%s` gibt es nicht." % sprung.roh,
                vorschlag=vorschlag(sprung.modus, sichtbare),
                spalte=sprung.spalte,
                beispiel="STATE %s" % sprung.roh))
        else:
            erreicht.add(sprung.modus)
    # Die Schritte einer Folge erreicht man über den Schritt davor.
    erreicht.update(m.name for m in programm.modi if m.versteckt)

    for modus in programm.modi:
        if modus.versteckt:
            continue
        if not modus.regeln:
            programm.hinweise.append(Hinweis(
                modus.zeile,
                "Der Modus `%s` hat keine Regel — darin wartet der Roboter nur."
                % modus.name))
        if modus.name not in erreicht:
            programm.hinweise.append(Hinweis(
                modus.zeile,
                "In den Modus `%s` führt kein `GOTO` — er wird nie betreten."
                % modus.name))

    for regel in programm.regeln:
        if regel.aktion.art == "goto" and regel.aktion.modus == regel.modus:
            programm.hinweise.append(Hinweis(
                regel.zeile,
                "`GOTO %s` steht im Modus `%s` selbst — das ändert nichts."
                % (regel.aktion.roh, regel.modus)))
