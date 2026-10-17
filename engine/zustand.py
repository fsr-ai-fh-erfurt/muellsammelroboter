"""Das `zustand`-Objekt, das ein Bot in `entscheide(zustand)` bekommt.

Hier steckt alles, was den Erstsemestern abgenommen wird: Wegfindung, Zielsuche,
Abstände. Läuft im Bot-Prozess und zählt damit auf dessen Zeitkonto — eine
Breitensuche auf 22x22 kostet Bruchteile einer Millisekunde.

Wichtig: Diese Datei enthält KEINE Spielregeln, nur Sicht und Wegfindung. Regeln
stehen in engine/game.py. Nach einem umstrittenen Zug (SPEC §7 C/E) weicht die
Wegfindung im nächsten Tick deterministisch auf ein freies Nachbarfeld aus.
"""

from collections import deque

from .rng import Zufall
from .world import RICHTUNGEN, RICHTUNGS_REIHENFOLGE, SORTE_RADIOAKTIV

SORTEN_ALIASE = {
    "papiermuell": "papier", "papiermüll": "papier", "papier": "papier",
    "biomuell": "bio", "biomüll": "bio", "bio": "bio",
    "metallschrott": "metall", "metall": "metall", "schrott": "metall",
    "elektroschrott": "elektro", "elektro": "elektro", "elektronik": "elektro",
    "radioaktiv": "radioaktiv", "fass": "radioaktiv", "atommuell": "radioaktiv",
    "atommüll": "radioaktiv", "radioaktiver abfall": "radioaktiv",
    "radioaktives fass": "radioaktiv",
    "ballen": "ballen", "gepresst": "ballen",
}

UNERREICHBAR = 9999


def sorte_normal(name):
    if name is None:
        return None
    schluessel = str(name).strip().lower()
    return SORTEN_ALIASE.get(schluessel, schluessel)


class Zustand:
    """Alles, was ein Roboter sieht und kann."""

    def __init__(self, daten):
        self._d = daten
        ich = daten["ich"]
        self.x = ich["x"]
        self.y = ich["y"]
        self.akku = ich["akku"]
        self.akku_max = ich["akku_max"]
        self.punkte = ich["punkte"]
        self.kapazitaet = ich["kapazitaet"]
        self.laedt = ich["laedt"]
        self.langsam = ich["langsam"]
        self.tick = daten["tick"]
        self.runden_laenge = daten["runden_laenge"]
        self.max_wechsel = daten["max_wechsel"]
        self.breite = daten["breite"]
        self.hoehe = daten["hoehe"]
        self.sicht_radius = daten["sicht_radius"]
        self.zone = daten["zone"]
        self.muell = daten["muell"]
        self.gegner = daten["gegner"]
        self.depot = (daten["depot"]["x"], daten["depot"]["y"])
        self.fremde_depots = [(d["x"], d["y"]) for d in daten["fremde_depots"]]
        self.teile = list(ich["ladung"])
        self._presse_anzahl = daten.get("presse_anzahl", 3)
        self.blockiert = ich.get("blockiert", False)
        self.aktive_regel = None
        self._zufall = None
        self._karte_werte = None
        self._hindernisse = {(h["x"], h["y"]) for h in daten.get("hindernisse", [])}
        self._gegner_felder = {(g["x"], g["y"]) for g in self.gegner}

    # ------------------------------------------------------------------ Zahlen

    @property
    def ladung(self):
        """Anzahl der geladenen Teile."""
        return len(self.teile)

    @property
    def ladung_ist_voll(self):
        return len(self.teile) >= self.kapazitaet

    @property
    def ladung_ist_leer(self):
        return not self.teile

    @property
    def freie_plaetze(self):
        return self.kapazitaet - len(self.teile)

    @property
    def ladung_wert(self):
        return sum(teil["wert"] for teil in self.teile)

    @property
    def kann_pressen(self):
        """Trägt der Roboter genug gleiche Teile mit positivem Wert für einen Ballen?"""
        zaehler = {}
        for teil in self.teile:
            if teil.get("gepresst") or teil["sorte"] == SORTE_RADIOAKTIV \
                    or teil["wert"] <= 0:
                continue
            zaehler[teil["sorte"]] = zaehler.get(teil["sorte"], 0) + 1
        return any(anzahl >= self._presse_anzahl for anzahl in zaehler.values())

    @property
    def gegner_sichtbar(self):
        return bool(self.gegner)

    @property
    def gegner_ladung(self):
        """Anzahl der Teile des nächsten sichtbaren Gegners; 0 wenn keiner zu sehen ist."""
        naechster = self.naechster_gegner()
        return naechster["ladung"] if naechster else 0

    @property
    def zone_faktor(self):
        """Um wie viel Müll in der Bonuszone mehr zählt (config.json: zone.faktor)."""
        return self.zone.get("faktor", 1)

    @property
    def unerriechbar(self):
        """Der Abstand, den `abstand_zu_*` für unerreichbare Ziele liefert."""
        return UNERREICHBAR

    @property
    def bin_in_zone(self):
        return self.ist_in_zone(self.x, self.y)

    @property
    def muell_in_zone(self):
        """Liegt in der Zone Müll, den `naechster_muell(in_zone)` auch ansteuern würde?

        Nur Stücke mit Wert über 0 zählen — sonst trifft `IF muell_in_zone THEN
        fahre_zu naechster_muell(in_zone)` bei verrottetem Müll zu, die Fahrt findet
        aber kein Ziel, und der Roboter wartet mit voller Ladung bis Rundenende.
        """
        for stueck in self.muell:
            if not stueck["radioaktiv"] and stueck["wert"] > 0 \
                    and self.ist_in_zone(stueck["x"], stueck["y"]):
                return True
        return False

    @property
    def restliche_ticks(self):
        return self.runden_laenge - self.tick

    def habe(self, sorte):
        gesucht = sorte_normal(sorte)
        return any(teil["sorte"] == gesucht for teil in self.teile)

    def anzahl(self, sorte):
        gesucht = sorte_normal(sorte)
        return sum(1 for teil in self.teile if teil["sorte"] == gesucht)

    # ------------------------------------------------------------------ Geometrie

    def ist_in_zone(self, x, y):
        z = self.zone
        return z["x"] <= x < z["x"] + z["groesse"] and z["y"] <= y < z["y"] + z["groesse"]

    def ist_wand(self, x, y):
        return x <= 0 or y <= 0 or x >= self.breite - 1 or y >= self.hoehe - 1

    def begehbar(self, x, y):
        if self.ist_wand(x, y):
            return False
        if (x, y) in self._gegner_felder:
            return False
        return (x, y) not in self._hindernisse

    @staticmethod
    def entfernung(x1, y1, x2, y2):
        return abs(x1 - x2) + abs(y1 - y2)

    def naechster_gegner(self):
        bester = None
        beste = None
        for g in self.gegner:
            d = self.entfernung(self.x, self.y, g["x"], g["y"])
            if beste is None or d < beste:
                beste, bester = d, g
        return bester

    # ------------------------------------------------------------------ Müllsuche

    def muell_auswahl(self, sorte=None, nur_in_zone=False, nur_positiv=False,
                      mindestwert=None, ohne_radioaktiv=True):
        """Alle sichtbaren Müllstücke, die zu den Vorgaben passen."""
        gesucht = sorte_normal(sorte)
        treffer = []
        for stueck in self.muell:
            if ohne_radioaktiv and stueck["radioaktiv"] and gesucht != "radioaktiv":
                continue
            if gesucht is not None and stueck["sorte"] != gesucht:
                continue
            if nur_in_zone and not self.ist_in_zone(stueck["x"], stueck["y"]):
                continue
            if nur_positiv and stueck["wert"] <= 0:
                continue
            if mindestwert is not None and stueck["wert"] < mindestwert:
                continue
            treffer.append(stueck)
        return treffer

    # ------------------------------------------------------------------ Wegfindung

    def _karte(self):
        """Eine Breitensuche je Tick, gemerkt: Abstand und erster Schritt zu jedem Feld.

        Ohne das würde eine Regel wie „nimm das beste Stück aus Wert minus Weg" für
        jedes Müllstück eine eigene Suche starten — bei 90 Stücken reicht das dicht an
        das Zeitlimit heran.
        """
        if self._karte_werte is None:
            start = (self.x, self.y)
            abstand = {start: 0}
            erster = {start: "warte"}
            schlange = deque([start])
            while schlange:
                feld = schlange.popleft()
                for name in RICHTUNGS_REIHENFOLGE:
                    dx, dy = RICHTUNGEN[name]
                    nachbar = (feld[0] + dx, feld[1] + dy)
                    if nachbar in abstand or not self.begehbar(*nachbar):
                        continue
                    abstand[nachbar] = abstand[feld] + 1
                    erster[nachbar] = name if feld == start else erster[feld]
                    schlange.append(nachbar)
            self._karte_werte = (abstand, erster)
        return self._karte_werte

    def _ausweichrichtung(self, vermeiden):
        """Nach einem umstrittenen Zug eine begehbare Nebenrichtung.

        Die feste Richtungsreihenfolge wird um `saat % 4` gedreht — deterministisch
        und ohne den Zufallsgenerator zu belegen. `vermeiden` ist die Richtung, an
        der der Wunsch gescheitert ist; gibt es sonst nichts Freies, `"warte"`.
        """
        reihe = RICHTUNGS_REIHENFOLGE
        drehung = self._d.get("saat", 0) % len(reihe)
        gedreht = reihe[drehung:] + reihe[:drehung]
        for name in gedreht:
            if name == vermeiden:
                continue
            dx, dy = RICHTUNGEN[name]
            if self.begehbar(self.x + dx, self.y + dy):
                return name
        return "warte"

    def _suche(self, ziele, ausweichen=True):
        """Gibt (abstand, erste_richtung) zum nächstgelegenen Ziel zurück.

        Bei gleichem Abstand gewinnt das Ziel mit der kleineren (y, x)-Koordinate —
        eine feste Regel, damit der Spielverlauf reproduzierbar bleibt. Ist der
        eigene Wunsch im letzten Tick an einem Standstreit gescheitert
        (`self.blockiert`), weicht die Suche auf eine begehbare Nebenrichtung aus;
        `ausweichen=False` schaltet das ab (beim gewollten Rammen).
        """
        felder = sorted({tuple(z) for z in ziele if not self.ist_wand(*z)},
                        key=lambda z: (z[1], z[0]))
        if not felder:
            return (None, "warte")
        start = (self.x, self.y)
        if start in felder:
            return (0, "warte")

        abstand, erster = self._karte()
        bestes = None
        for ziel in felder:
            if ziel in abstand:
                kandidat = (abstand[ziel], erster[ziel])
            else:
                # Unbegehbares Ziel (ein Gegner): über ein Nachbarfeld anfahren.
                kandidat = None
                for name in RICHTUNGS_REIHENFOLGE:
                    dx, dy = RICHTUNGEN[name]
                    davor = (ziel[0] - dx, ziel[1] - dy)
                    if davor not in abstand:
                        continue
                    schritt = name if davor == start else erster[davor]
                    moeglich = (abstand[davor] + 1, schritt)
                    if kandidat is None or moeglich[0] < kandidat[0]:
                        kandidat = moeglich
                if kandidat is None:
                    continue
            if bestes is None or kandidat[0] < bestes[0]:
                bestes = kandidat
        if bestes is None:
            return (None, "warte")
        if ausweichen and self.blockiert and bestes[1] != "warte":
            return (bestes[0], self._ausweichrichtung(bestes[1]))
        return bestes

    def _ziel_felder_muell(self, sorte=None, nur_in_zone=False, **rest):
        """Angesteuert wird nur Müll, der noch etwas wert ist.

        Sonst führe `fahre_zu naechster_muell` den Roboter zielstrebig auf verrotteten
        Müll, der Minuspunkte bringt — und die Regelsprache hätte keine Möglichkeit,
        das zu verhindern. Ausnahme ist `naechster_muell(radioaktiv)`: das Fass will
        man ja gerade wegen seines negativen Werts.
        """
        if sorte_normal(sorte) != "radioaktiv":
            rest.setdefault("nur_positiv", True)
        treffer = self.muell_auswahl(sorte, nur_in_zone, **rest)
        return [(s["x"], s["y"]) for s in treffer]

    def _zone_felder(self):
        z = self.zone
        felder = []
        for dy in range(z["groesse"]):
            for dx in range(z["groesse"]):
                x, y = z["x"] + dx, z["y"] + dy
                if not self.ist_wand(x, y) and (x, y) not in self._hindernisse:
                    felder.append((x, y))
        return felder

    # -------- Aktionen: fahre_zu ...

    def fahre_zu_depot(self):
        return self._suche([self.depot])[1]

    def fahre_zu_muell(self, sorte=None, nur_in_zone=False, **rest):
        return self._suche(self._ziel_felder_muell(sorte, nur_in_zone, **rest))[1]

    def fahre_zu_gegner(self):
        """Auf den nächsten sichtbaren Gegner zu — mit gelegentlichem Innehalten.

        Warum das Innehalten sein muss: Ziehen beide Roboter in jedem Tick, bleibt die
        Parität ihres Abstands unverändert. Aus einem geraden Abstand könnte damit nie
        ein Treffer werden, und zwei aufeinander zufahrende Roboter würden sich
        obendrein dauerhaft dasselbe Zwischenfeld streitig machen (SPEC §7 C) und für
        den Rest der Runde festhängen. Das Innehalten läuft über den runden-eigenen
        Zufall: reproduzierbar, aber für beide Roboter verschieden.
        """
        gegner = self.naechster_gegner()
        if gegner is None:
            return "warte"
        abstand = self.entfernung(self.x, self.y, gegner["x"], gegner["y"])
        if abstand % 2 == 0 and abstand <= 4 and self.zufall_zahl(2) == 0:
            return "warte"
        # Kein Ausweichen: Das Rammen ist gewollt, hier gilt weiter die Paritäts-Pause.
        return self._suche([(g["x"], g["y"]) for g in self.gegner], ausweichen=False)[1]

    def fahre_zu_zone(self):
        if self.bin_in_zone:
            return "warte"
        return self._suche(self._zone_felder())[1]

    def fahre_zu_feld(self, x, y):
        return self._suche([(int(x), int(y))])[1]

    def weg_von_gegner(self):
        naechster = self.naechster_gegner()
        if naechster is None:
            return "warte"
        jetzt = self.entfernung(self.x, self.y, naechster["x"], naechster["y"])
        beste_richtung = "warte"
        # Bei gleichem Manhattan-Abstand gewinnt die Richtung, die auch in der Luftlinie
        # am weitesten wegführt: sonst würde man seitwärts ausweichen statt zu fliehen.
        beste_marke = (jetzt, (self.x - naechster["x"]) ** 2 + (self.y - naechster["y"]) ** 2)
        for name in RICHTUNGS_REIHENFOLGE:
            dx, dy = RICHTUNGEN[name]
            x, y = self.x + dx, self.y + dy
            if not self.begehbar(x, y):
                continue
            marke = (self.entfernung(x, y, naechster["x"], naechster["y"]),
                     (x - naechster["x"]) ** 2 + (y - naechster["y"]) ** 2)
            if marke > beste_marke:
                beste_marke = marke
                beste_richtung = name
        return beste_richtung

    def fahre(self, richtung):
        name = str(richtung).strip().lower()
        return name if name in RICHTUNGEN else "warte"

    def warte(self):
        return "warte"

    # -------- Abstände

    def abstand_zu_depot(self):
        d = self._suche([self.depot])[0]
        return UNERREICHBAR if d is None else d

    def abstand_zu_muell(self, sorte=None, nur_in_zone=False, **rest):
        d = self._suche(self._ziel_felder_muell(sorte, nur_in_zone, **rest))[0]
        return UNERREICHBAR if d is None else d

    def abstand_zu_gegner(self):
        naechster = self.naechster_gegner()
        if naechster is None:
            return UNERREICHBAR
        return self.entfernung(self.x, self.y, naechster["x"], naechster["y"])

    def abstand_zu_zone(self):
        if self.bin_in_zone:
            return 0
        d = self._suche(self._zone_felder())[0]
        return UNERREICHBAR if d is None else d

    def abstand_zu_feld(self, x, y):
        d = self._suche([(int(x), int(y))])[0]
        return UNERREICHBAR if d is None else d

    # -------- Richtung und Nachbarfelder

    def _richtung(self, ziele):
        """Wohin `fahre_zu` als Nächstes fahren würde: oben/unten/links/rechts.

        `hier`, wenn der Roboter schon auf dem Ziel steht, `keine`, wenn es kein Ziel
        oder keinen Weg gibt — oder wenn `fahre_zu` gerade nur warten könnte. Die
        Antwort kommt aus derselben Wegsuche wie die Fahrt selbst, samt Ausweichen
        nach einem Standstreit; sie passt also immer zum nächsten Schritt.
        """
        abstand, schritt = self._suche(ziele)
        if abstand is None:
            return "keine"
        if abstand == 0:
            return "hier"
        return schritt if schritt in RICHTUNGEN else "keine"

    def richtung_zu_depot(self):
        return self._richtung([self.depot])

    def richtung_zu_muell(self, sorte=None, nur_in_zone=False, **rest):
        return self._richtung(self._ziel_felder_muell(sorte, nur_in_zone, **rest))

    def richtung_zu_gegner(self):
        """Wie `fahre_zu gegner`, aber ohne dessen zufälliges Innehalten.

        Eine Frage darf den Zufall der Runde nicht verbrauchen — sonst änderte schon
        das Nachsehen, was später passiert.
        """
        if not self.gegner:
            return "keine"
        abstand, schritt = self._suche([(g["x"], g["y"]) for g in self.gegner],
                                       ausweichen=False)
        if abstand is None:
            return "keine"
        return schritt if schritt in RICHTUNGEN else "hier"

    def richtung_zu_zone(self):
        if self.bin_in_zone:
            return "hier"
        return self._richtung(self._zone_felder())

    def richtung_zu_feld(self, x, y):
        return self._richtung([(int(x), int(y))])

    def richtung_weg_von_gegner(self):
        if not self.gegner:
            return "keine"
        schritt = self.weg_von_gegner()
        return schritt if schritt in RICHTUNGEN else "keine"

    def objekt_in_richtung(self, richtung):
        """Was auf dem Nachbarfeld liegt: wand, gegner, eine Müllsorte, depot oder frei.

        Bei mehreren Dingen auf einem Feld gilt diese Reihenfolge. Ohne gültige
        Richtung (`hier`, `keine`) ist die Antwort `frei`.
        """
        name = str(richtung).strip().lower()
        if name not in RICHTUNGEN:
            return "frei"
        dx, dy = RICHTUNGEN[name]
        feld = (self.x + dx, self.y + dy)
        if self.ist_wand(*feld) or feld in self._hindernisse:
            return "wand"
        if feld in self._gegner_felder:
            return "gegner"
        for stueck in self.muell:
            if (stueck["x"], stueck["y"]) == feld:
                return stueck["sorte"]
        if feld == self.depot:
            return "depot"
        return "frei"

    # ------------------------------------------------------------------ Zufall

    def zufall_zahl(self, obergrenze):
        """Deterministischer Zufall: gleiche Runde, gleicher Seed, gleiches Ergebnis."""
        if self._zufall is None:
            self._zufall = Zufall(self._d.get("saat", 0))
        return self._zufall.zahl(obergrenze)

    def zufall_richtung(self):
        return RICHTUNGS_REIHENFOLGE[self.zufall_zahl(len(RICHTUNGS_REIHENFOLGE))]

    # ------------------------------------------------------------------ Regeln

    def regel(self, nummer):
        """Merkt sich, welche Regel gegriffen hat — die Werkstatt zeigt sie an."""
        self.aktive_regel = nummer
        return nummer
