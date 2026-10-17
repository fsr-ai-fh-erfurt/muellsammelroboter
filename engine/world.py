"""Spielzustand: Gitter, Müll, Bonuszone, Roboter.

Enthält den Aufbau einer Runde und alle Abfragen auf den Zustand. Die Tick-Schleife
und die Bewegungsauflösung stehen in game.py.
"""

from .rng import Zufall

RICHTUNGEN = {
    "oben": (0, -1),
    "unten": (0, 1),
    "links": (-1, 0),
    "rechts": (1, 0),
}
# Feste Reihenfolge überall dort, wo über Richtungen iteriert wird (Determinismus).
RICHTUNGS_REIHENFOLGE = ("oben", "unten", "links", "rechts")

SORTE_RADIOAKTIV = "radioaktiv"


def symmetrie_felder(breite, hoehe, x, y, ordnung):
    """Alle Felder, die unter der Symmetrie zu (x, y) gehören.

    Wird auch von der config-Prüfung benutzt, damit eine Karte schon beim Laden
    auffällt, wenn ihre Wände nicht symmetrisch aufgehen.
    """
    if ordnung == 1:
        return [(x, y)]
    if ordnung == 2:
        return [(x, y), (breite - 1 - x, hoehe - 1 - y)]
    felder = []
    p = (x, y)
    for _ in range(4):
        felder.append(p)
        p = (breite - 1 - p[1], p[0])
    return felder


class Muell:
    __slots__ = ("x", "y", "sorte", "basiswert", "entsteh_tick", "radioaktiv")

    def __init__(self, x, y, sorte, basiswert, entsteh_tick, radioaktiv=False):
        self.x = x
        self.y = y
        self.sorte = sorte
        self.basiswert = basiswert
        self.entsteh_tick = entsteh_tick
        self.radioaktiv = radioaktiv


class Roboter:
    __slots__ = ("index", "name", "x", "y", "akku", "punkte", "ladung", "lade_ticks",
                 "presse_ticks", "presse_sorte", "depot", "statistik", "blockiert")

    def __init__(self, index, name, x, y, akku, depot):
        self.index = index
        self.name = name
        self.x = x
        self.y = y
        self.akku = akku
        self.punkte = 0
        self.ladung = []            # Liste aus {"sorte": str, "wert": int}
        self.lade_ticks = 0
        self.presse_ticks = 0       # läuft eine Presse? dann bewegt er sich nicht
        self.presse_sorte = None    # welche Sorte gerade gepresst wird
        self.depot = depot          # (x, y)
        # Ob der eigene Wunsch im letzten Tick an einem Standstreit scheiterte
        # (SPEC §7 C/E). Die Wegfindung weicht darauf im nächsten Tick aus.
        self.blockiert = False
        self.statistik = {
            "abgeliefert_stueck": 0,
            "abgeliefert_punkte": 0,
            "aufgenommen": 0,
            "rammangriffe": 0,
            "gerammt_worden": 0,
            "geklaut": 0,
            "bestohlen": 0,
            "bewegungen": 0,
            "gepresst": 0,
            "verloren": 0,
        }

    @property
    def position(self):
        return (self.x, self.y)


class Welt:
    """Der vollständige Spielzustand einer Runde."""

    def __init__(self, config, namen, seed, spieler=None):
        self.config = config
        self.seed = int(seed)
        self.zufall = Zufall(seed)
        self.breite = config.spiel.breite
        self.hoehe = config.spiel.hoehe
        self.runden_laenge = config.spiel.runden_laenge
        self.kapazitaet = config.spiel.kapazitaet
        self.spieler = spieler if spieler is not None else len(namen)
        if not 1 <= self.spieler <= 4:
            raise ValueError("Es sind 1 bis 4 Roboter vorgesehen, nicht %d." % self.spieler)
        self.tick = 0
        self.muell = {}             # (x, y) -> Muell
        self.zone = (1, 1)

        self._sorten_gewichte = [
            (name, config.muell.sorten[name].gewicht)
            for name in sorted(config.muell.sorten.keys())
        ]
        self._sorten_werte = {
            name: config.muell.sorten[name].wert
            for name in config.muell.sorten.keys()
        }

        depots = self.depot_positionen()
        self.roboter = [
            Roboter(i, namen[i], depots[i][0], depots[i][1], config.akku.start, depots[i])
            for i in range(self.spieler)
        ]
        self._depot_felder = set(depots)
        self.hindernisse = set()        # Innenwände der gewählten Karte
        self.karte_name = ""
        self._karte_lesen(config)

        self._zone_neu()
        self._faesser_setzen()
        self._startmuell_setzen()

    # ------------------------------------------------------------------ Geometrie

    @property
    def symmetrie_ordnung(self):
        if self.spieler <= 1:
            return 1
        if self.spieler == 2:
            return 2
        return 4

    def bahn(self, x, y):
        """Alle Felder, die unter der Symmetrie zu (x, y) gehören."""
        return symmetrie_felder(self.breite, self.hoehe, x, y, self.symmetrie_ordnung)

    def _karte_lesen(self, config):
        """Wählt die Karte dieses Spiels und baut ihre Innenwände auf.

        Die Karte kommt über den Seed: gleicher Seed, gleiches Feld. In der
        `config.json` stehen nur die Grundfelder; die Symmetrie erzeugt daraus die
        passenden Wände für 2 oder 4 Spieler.
        """
        karten = config.spiel.karten
        karte = karten[self.seed % len(karten)]
        self.karte_name = karte.get("name", "")
        felder = set()
        for punkt in karte["waende"]:
            bahn = self.bahn(punkt[0], punkt[1])
            if len(set(bahn)) != self.symmetrie_ordnung:
                raise ValueError(
                    "Die Karte %r hat eine Wand, die mit %d Spielern nicht sauber "
                    "aufgeht: %s" % (self.karte_name, self.spieler, punkt))
            for fx, fy in bahn:
                if self.ist_wand(fx, fy) or (fx, fy) in self._depot_felder:
                    raise ValueError(
                        "Die Karte %r legt eine Wand auf Rand oder Depot: %s"
                        % (self.karte_name, punkt))
                felder.add((fx, fy))
        self.hindernisse = felder

    def depot_positionen(self):
        """Depots liegen `depot_abstand` Felder von der Wand entfernt.

        Nicht direkt in der Ecke: dort liefe jeder Schub gegen eine Wand und ein
        Roboter, der ein fremdes Depot besetzt, wäre nicht mehr zu vertreiben.
        """
        b, h = self.breite, self.hoehe
        a = self.config.spiel.depot_abstand
        if self.spieler <= 1:
            return [(a, a)]
        if self.spieler == 2:
            return [(a, a), (b - 1 - a, h - 1 - a)]
        return self.bahn(a, a)[: self.spieler]

    def ist_wand(self, x, y):
        return x <= 0 or y <= 0 or x >= self.breite - 1 or y >= self.hoehe - 1

    def ist_hindernis(self, x, y):
        return (x, y) in self.hindernisse

    def ist_blockiert(self, x, y):
        """Wand oder Innenwand — alles, worauf niemand fahren kann."""
        return self.ist_wand(x, y) or self.ist_hindernis(x, y)

    def ist_depot(self, x, y):
        return (x, y) in self._depot_felder

    def roboter_auf(self, x, y):
        for r in self.roboter:
            if r.x == x and r.y == y:
                return r
        return None

    def in_zone(self, x, y):
        zx, zy = self.zone
        g = self.config.zone.groesse
        return zx <= x < zx + g and zy <= y < zy + g

    # ------------------------------------------------------------------ Aufbau

    def _zone_neu(self):
        g = self.config.zone.groesse
        obergrenze = self.breite - 1 - g
        x = self.zufall.bereich(1, obergrenze)
        y = self.zufall.bereich(1, self.hoehe - 1 - g)
        self.zone = (x, y)

    def _feld_frei(self, x, y):
        if self.ist_blockiert(x, y):
            return False
        if (x, y) in self.muell:
            return False
        if self.ist_depot(x, y):
            return False
        return self.roboter_auf(x, y) is None

    def _faesser_setzen(self):
        """Radioaktive Fässer: feste, symmetrische Positionen, kein Nachschub."""
        b, h = self.breite, self.hoehe
        basen = [(b // 4, h // 2), (b // 2, h // 4), (b // 4, h // 4)]
        gewuenscht = self.config.radioaktiv.anzahl_pro_spieler
        gesetzt = 0
        for basis in basen:
            if gesetzt >= gewuenscht:
                break
            felder = self.bahn(*basis)
            if len(set(felder)) != self.symmetrie_ordnung:
                continue
            if not all(self._feld_frei(x, y) for x, y in felder):
                continue
            for x, y in felder:
                self.muell[(x, y)] = Muell(
                    x, y, SORTE_RADIOAKTIV, self.config.radioaktiv.wert, 0, radioaktiv=True
                )
            gesetzt += 1

    def _startmuell_setzen(self):
        # start_anzahl ist durch 4 teilbar (config-Prüfung), die Symmetrieordnung
        # ist 1, 2 oder 4 — die Division geht also glatt auf.
        bahnen = self.config.muell.start_anzahl // self.symmetrie_ordnung
        self._muell_streuen(bahnen)

    def _muell_streuen(self, bahnen):
        """Streut `bahnen` vollständige Symmetriebahnen ein. Gibt die neuen Stücke zurück."""
        neu = []
        ordnung = self.symmetrie_ordnung
        versuche = 0
        gesetzt = 0
        # Mehr Innenfelder als (breite - 2) * (hoehe - 2) gibt es nicht — eine
        # feste Zahl hier wäre ein Spielwert im Code und hat auf vollen Feldern
        # still zu wenige Bahnen eingestreut.
        grenze = (self.breite - 2) * (self.hoehe - 2)
        while gesetzt < bahnen and versuche < grenze:
            versuche += 1
            if len(self.muell) >= self.config.muell.max_auf_feld:
                break
            x = self.zufall.bereich(1, self.breite - 2)
            y = self.zufall.bereich(1, self.hoehe - 2)
            felder = self.bahn(x, y)
            if len(set(felder)) != ordnung:
                continue
            # Die ganze Bahn muss noch hineinpassen — sonst sprengt die Symmetrie
            # die Obergrenze um bis zu ordnung - 1 Stücke.
            if len(self.muell) + len(felder) > self.config.muell.max_auf_feld:
                break
            if not all(self._feld_frei(fx, fy) for fx, fy in felder):
                continue
            sorte = self.zufall.gewichtet(self._sorten_gewichte)
            wert = self._sorten_werte[sorte]
            for fx, fy in felder:
                stueck = Muell(fx, fy, sorte, wert, self.tick)
                self.muell[(fx, fy)] = stueck
                neu.append(stueck)
            gesetzt += 1
        return neu

    # ------------------------------------------------------------------ Werte

    def wert_von(self, stueck):
        """Aktueller Wert eines liegenden Müllstücks (§3 SPEC)."""
        if stueck.radioaktiv:
            return stueck.basiswert
        t = self.config.muell.verfall_ticks
        alter = self.tick - stueck.entsteh_tick
        roh = stueck.basiswert - (stueck.basiswert * alter) // t
        return max(roh, -self.config.muell.verfall_strafe_max)

    def aufnahme_wert(self, stueck):
        """Wert beim Aufnehmen, inklusive eingefrorenem Zonenbonus."""
        wert = self.wert_von(stueck)
        if not stueck.radioaktiv and self.in_zone(stueck.x, stueck.y):
            wert *= self.config.zone.faktor
        return wert

    # ------------------------------------------------------------------ Sicht

    def sicht(self, index):
        """Der Zustand, den Roboter `index` zu sehen bekommt (§9 SPEC)."""
        ich = self.roboter[index]
        radius = self.config.spiel.sicht_radius

        muell = []
        for (x, y) in sorted(self.muell):
            stueck = self.muell[(x, y)]
            muell.append({
                "x": x, "y": y,
                "sorte": stueck.sorte,
                "wert": self.wert_von(stueck),
                "radioaktiv": stueck.radioaktiv,
            })

        gegner = []
        for r in self.roboter:
            if r.index == index:
                continue
            if abs(r.x - ich.x) + abs(r.y - ich.y) <= radius:
                gegner.append({"x": r.x, "y": r.y, "ladung": len(r.ladung)})

        return {
            "tick": self.tick,
            "runden_laenge": self.runden_laenge,
            # Deterministische Saat je Bot und Tick: erlaubt Zufallsbots ohne `random`.
            "saat": (self.seed * 1000003 + index * 7919 + self.tick * 31) & ((1 << 62) - 1),
            "breite": self.breite,
            "hoehe": self.hoehe,
            "sicht_radius": radius,
            "ich": {
                "x": ich.x, "y": ich.y,
                "akku": ich.akku,
                "akku_max": self.config.akku.max,
                "punkte": ich.punkte,
                "laedt": ich.lade_ticks,
                "langsam": ich.akku < self.config.akku.langsam_ab,
                "kapazitaet": self.kapazitaet,
                "ladung": [dict(teil) for teil in ich.ladung],
                "blockiert": ich.blockiert,
            },
            "depot": {"x": ich.depot[0], "y": ich.depot[1]},
            "fremde_depots": [
                {"x": r.depot[0], "y": r.depot[1]}
                for r in self.roboter if r.index != index
            ],
            "muell": muell,
            "gegner": gegner,
            "zone": {"x": self.zone[0], "y": self.zone[1], "groesse": self.config.zone.groesse,
                     "faktor": self.config.zone.faktor},
            "max_wechsel": self.config.sprache.max_wechsel,
            "presse_anzahl": self.config.presse.anzahl,
            "hindernisse": [{"x": x, "y": y} for (x, y) in sorted(self.hindernisse)],
        }

    # ------------------------------------------------------------------ Abbild

    def abbild(self):
        """Vollständiger Zustand für die Aufzeichnung (der Browser zeigt ihn nur an)."""
        return {
            "tick": self.tick,
            "karte": self.karte_name,
            "hindernisse": [[x, y] for (x, y) in sorted(self.hindernisse)],
            "zone": [self.zone[0], self.zone[1]],
            "roboter": [
                {
                    "x": r.x, "y": r.y,
                    "akku": r.akku,
                    "punkte": r.punkte,
                    "laedt": r.lade_ticks,
                    "ladung": [dict(teil) for teil in r.ladung],
                }
                for r in self.roboter
            ],
            "muell": [
                [x, y, self.muell[(x, y)].sorte, self.wert_von(self.muell[(x, y)])]
                for (x, y) in sorted(self.muell)
            ],
        }
