# Mitgelieferter Gegner: Sabotage als eigenständige Strategie.
#
# Zwei Dinge muss man über das Rammen wissen:
#   1. Hinterherfahren bringt nichts. Fährt der Verfolgte weg, rückt der Verfolger nur
#      nach — das ist ausdrücklich kein Rammen (SPEC §7 D). Getroffen wird nur, wer
#      stehen bleibt, blockiert wird oder frontal entgegenkommt.
#   2. `fahre_zu_gegner` hält deshalb gelegentlich inne. Sonst bliebe der Abstand
#      immer gerade und man käme nie heran.
#
# Der Lauerer sammelt wie ein normaler Sammler — bis ein gut beladener Gegner in
# Sicht kommt. Der wird bald heimfahren, und der Heimweg führt über sein Depot.
# Wenn der Lauerer den Posten vor ihm erreichen kann, lässt er alles stehen und
# liegen und hält dort Wache (im Duell WACHE Ticks, in der Vierergruppe geteilt
# durch die Gegnerzahl — an einem von drei Depots lohnt kein langes Warten. Wer
# heimkommen will, muss auf das Depot steigen, und weil ein Platztausch für beide
# als Rammen zählt und dabei KEINER sein Feld wechselt, wird die Ablieferung
# gleich mit verhindert. Nach der Wache sammelt
# er weiter; der nächste Heimkehrer kommt bestimmt. Was ohne Umweg auf dem Weg zum
# Posten liegt, nimmt er mit — die Wache kostet so keine Sammelzeit.
#
# Er hat vier Modi — an ihm sieht man am besten, wofür Modi gut sind. „sammeln",
# „lauern", „angriff" und „heimweg" sind vier verschiedene Absichten, und jede hat
# ihre eigene kleine Regelliste. In der Regelsprache sähe sein Gerüst so aus
# (`kann_abfangen` prüft, ob er vor dem Heimkehrer am Depot ist):
#
#   STATE sammeln
#     IF ladung >= 5 THEN GOTO heimweg
#     IF gegner_sichtbar AND gegner_ladung >= 2 AND kann_abfangen THEN GOTO lauern
#     ELSE fahre_zu BEST muell BY wert - 3 * abstand
#
#   STATE lauern
#     IF ladung >= 5 THEN GOTO heimweg
#     ELSE fahre_zu feld(...)          # das fremde Depot, dann warten
#
#   STATE angriff
#     IF abstand_zu gegner == 1 THEN ramme gegner
#     ELSE warte                        # auf dem Posten bleiben
#
#   STATE heimweg
#     IF ladung < 5 THEN GOTO sammeln
#     ELSE fahre_zu depot
#
# Der Posten selbst lässt sich in Regeln nicht ausdrücken — `fremde_depots` steht
# nur dem Python-Teil offen; die Wache am Posten ist Python-Gedächtnis. Alles andere
# steht so auch den Teams zur Verfügung.
#
# Der Ausstieg aus `heimweg` hängt am Grund und nicht am leeren Laderaum — wer ihm
# unterwegs die Beute klaut, schickt ihn zurück an die Arbeit.

BESCHREIBUNG = "Besetzt das gegnerische Depot und rammt, wer heimkommt."
NAME = "Der Lauerer"

LOHNENDE_BEUTE = 2     # ab so vielen Teilen lohnt der Stoß, wenn er daneben steht
HINTERHALT = 2         # ab so vielen Teilen lohnt sich der Hinterhalt
VORSPRUNG = 4          # so viel näher am Posten muss er sein, um abzufangen
SCHATZ = 5             # ab so viel eigener Ladung lohnt der Heimweg
WEGKOSTEN = 3
WACHE = 120            # so lange hält er den Posten höchstens (Duell; sonst geteilt)
PATROUILLE = 12        # so oft tritt er sich am Posten die Beine aus
PRESSE_WEG = 6
PRESSE_PLATZ = 2


class Roboter:
    NAME = NAME
    START_MODUS = "sammeln"

    def __init__(self):
        self.modus = self.START_MODUS
        self.posten_ticks = 0

    def entscheide(self, zustand):
        for _ in range(zustand.max_wechsel):
            aktion = self._modus_schritt(zustand)
            if aktion is not None:
                return aktion
        return "warte"

    def _modus_schritt(self, zustand):
        """Die Aktion für diesen Tick — oder None, wenn nur der Modus wechselte."""
        if self.modus == "angriff":
            return self._modus_angriff(zustand)
        if self.modus == "heimweg":
            return self._modus_heimweg(zustand)
        if self.modus == "lauern":
            return self._modus_lauern(zustand)
        return self._modus_sammeln(zustand)

    # ---------------------------------------------------------------- Modi

    def _modus_sammeln(self, zustand):
        if self._muss_heim(zustand):
            zustand.regel(1)
            return self._wechsel("heimweg")

        # Ein gut beladener Gegner wird bald heimfahren. Wenn der Lauerer den
        # Posten vor ihm erreichen kann, lässt er alles stehen und liegen.
        if self._abfangen_lohnt(zustand):
            self.posten_ticks = 0
            zustand.regel(2)
            return self._wechsel("lauern")

        # Nur was direkt neben ihm steht, reizt ihn zum Angriff — sonst würde
        # er dem Gegner quer über die Karte folgen.
        if (zustand.gegner_sichtbar and zustand.gegner_ladung >= LOHNENDE_BEUTE
                and zustand.abstand_zu_gegner() == 1):
            zustand.regel(3)
            return self._wechsel("angriff")

        # Enge Ladung unterwegs pressen, solange der Heimweg weit ist.
        if (zustand.kann_pressen and zustand.freie_plaetze <= PRESSE_PLATZ
                and zustand.abstand_zu_depot() > PRESSE_WEG):
            zustand.regel(4)
            return "presse"

        nahes = self._bestes_stueck(zustand)
        if nahes is not None and not zustand.ladung_ist_voll:
            zustand.regel(5)
            return zustand.fahre_zu_feld(nahes["x"], nahes["y"])

        # Nichts lohnt sich gerade: Ladung heimbringen, sonst in der Zone auf
        # Nachschub warten.
        if not zustand.ladung_ist_leer:
            zustand.regel(6)
            return zustand.fahre_zu_depot()
        zustand.regel(7)
        return zustand.fahre_zu_zone()

    def _modus_lauern(self, zustand):
        if self._muss_heim(zustand):
            zustand.regel(8)
            return self._wechsel("heimweg")

        self.posten_ticks += 1
        posten = self._posten(zustand)
        if (zustand.x, zustand.y) != posten:
            # Den Posten erreichen — wenn möglich vor dem Heimkehrer. Was direkt
            # am Weg liegt, wird mitgenommen; der Umweg zum Posten bleibt so keine
            # verlorene Zeit.
            if zustand.ladung < SCHATZ - 2:
                am_weg = self._stueck_auf_dem_weg(zustand, posten)
                if am_weg is not None:
                    zustand.regel(9)
                    return zustand.fahre_zu_feld(am_weg["x"], am_weg["y"])
            zustand.regel(10)
            return zustand.fahre_zu_feld(posten[0], posten[1])

        if self.posten_ticks > self._wache(zustand):
            zustand.regel(11)
            return self._wechsel("sammeln")

        # Ein beladener Gegner direkt neben ihm wird gerammt. Wer auf seinen
        # Posten will, will auf sein Feld — das ist der Platztausch.
        if (zustand.gegner_sichtbar and zustand.gegner_ladung >= LOHNENDE_BEUTE
                and zustand.abstand_zu_gegner() == 1):
            zustand.regel(12)
            return self._wechsel("angriff")

        # Nicht festwachsen: Alle paar Ticks ein Schritt zur Seite und gleich
        # wieder zurück. In Depothitternähe bleibt er dabei.
        if self.posten_ticks % PATROUILLE == 0:
            schritt = self._seitenschritt(zustand)
            if schritt != "warte":
                zustand.regel(13)
                return schritt

        zustand.regel(14)
        return "warte"

    def _modus_angriff(self, zustand):
        # Eigene Beute zuerst sichern: beim Rammen könnte sie selbst geklaut werden.
        if self._muss_heim(zustand):
            zustand.regel(15)
            return self._wechsel("heimweg")

        # Der Gegner ist weg oder trägt nichts mehr, was den Stoß lohnt.
        if not zustand.gegner_sichtbar or zustand.gegner_ladung < LOHNENDE_BEUTE:
            zustand.regel(16)
            return self._wechsel("sammeln")

        if zustand.abstand_zu_gegner() == 1:
            # Direkt daneben: zustoßen. Will er auf mein Feld — und auf sein Depot
            # will er immer —, ist das ein Platztausch: Rammen für beide, und
            # keiner bewegt sich. Solange er es weiter versucht, klaue ich jeden
            # Tick ein weiteres Teil.
            zustand.regel(17)
            return zustand.fahre_zu_gegner()

        if self._auf_posten(zustand):
            # Den Posten nicht aufgeben. Wer heim will, muss ohnehin hierher.
            self.posten_ticks += 1
            if self.posten_ticks % PATROUILLE == 0:
                schritt = self._seitenschritt(zustand)
                if schritt != "warte":
                    zustand.regel(18)
                    return schritt
            zustand.regel(19)
            return "warte"

        # Nicht hinterherfahren: Das bringt nach §7 D nichts und kostet nur
        # Sammelzeit. Der Heimkehrer kommt zum Posten.
        zustand.regel(20)
        return zustand.fahre_zu_feld(self._posten(zustand)[0], self._posten(zustand)[1])

    def _modus_heimweg(self, zustand):
        # Der Heimweg gilt genau so lange, wie sein Grund gilt: abgeliefert, oder
        # die Beute unter der Schwelle, weil ihm selbst etwas geklaut wurde.
        if not self._muss_heim(zustand):
            zustand.regel(21)
            return self._wechsel("sammeln")

        zustand.regel(22)
        return zustand.fahre_zu_depot()

    # ---------------------------------------------------------------- Hilfen

    def _wechsel(self, modus):
        """Moduswechsel ohne Zugverlust: `None` heißt „weiter im neuen Modus"."""
        self.modus = modus
        return None

    def _wache(self, zustand):
        """Wachdauer am Posten: im Duell unverändert WACHE, in der Vierergruppe
        kürzer — ein Posten von dreien lohnt kein langes Festsitzen."""
        return max(1, WACHE // max(1, len(zustand.fremde_depots)))

    def _muss_heim(self, zustand):
        """Die drei Gründe, die jeden Hinterhalt abbrechen."""
        if zustand.ladung >= SCHATZ:
            return True
        if zustand.ladung_ist_leer:
            return False
        return (zustand.restliche_ticks <= self._heimweg(zustand) + 4
                or zustand.akku < 30)

    def _heimweg(self, zustand):
        weg = zustand.abstand_zu_depot()
        return weg * 2 if zustand.akku < 30 else weg

    def _posten(self, zustand):
        """Das gegnerische Depot selbst — fremde Depots sind normale Felder."""
        return zustand.fremde_depots[0] if zustand.fremde_depots else zustand.depot

    def _auf_posten(self, zustand):
        return (zustand.x, zustand.y) == self._posten(zustand)

    def _seitenschritt(self, zustand):
        """Ein freies Nachbarfeld — damit er am Posten nicht festwächst."""
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            if zustand.begehbar(zustand.x + dx, zustand.y + dy):
                return zustand.fahre_zu_feld(zustand.x + dx, zustand.y + dy)
        return "warte"

    def _abfangen_lohnt(self, zustand):
        """Kann der Lauerer den vollen Heimkehrer am Depot abfangen?"""
        gegner = zustand.naechster_gegner()
        if gegner is None or gegner["ladung"] < HINTERHALT:
            return False
        posten = self._posten(zustand)
        mein_weg = zustand.abstand_zu_feld(posten[0], posten[1])
        if mein_weg >= zustand.unerriechbar:
            return False
        seins = zustand.entfernung(gegner["x"], gegner["y"], posten[0], posten[1])
        return mein_weg <= seins + VORSPRUNG

    def _bestes_stueck(self, zustand):
        """Wert gegen Weg — zwischen zwei Hinterhalten sammelt er ganz normal."""
        bestes = None
        beste_marke = 0
        for stueck in zustand.muell_auswahl(nur_positiv=True):
            weg = zustand.abstand_zu_feld(stueck["x"], stueck["y"])
            if weg >= zustand.unerriechbar:
                continue
            wert = stueck["wert"] * (2 if zustand.ist_in_zone(stueck["x"], stueck["y"]) else 1)
            marke = wert - weg * WEGKOSTEN
            if marke > beste_marke:
                beste_marke, bestes = marke, stueck
        return bestes

    def _stueck_auf_dem_weg(self, zustand, ziel):
        """Das wertvollste Stück, das ohne Umweg auf dem Weg zum Ziel liegt."""
        gesamt = zustand.abstand_zu_feld(ziel[0], ziel[1])
        if gesamt >= zustand.unerriechbar:
            return None
        bestes = None
        beste_marke = 0
        for stueck in zustand.muell_auswahl(nur_positiv=True):
            weg = zustand.abstand_zu_feld(stueck["x"], stueck["y"])
            if weg >= zustand.unerriechbar:
                continue
            rest = zustand.entfernung(stueck["x"], stueck["y"], ziel[0], ziel[1])
            if weg + rest != gesamt:
                continue
            marke = stueck["wert"] - weg * WEGKOSTEN
            if marke > beste_marke:
                beste_marke, bestes = marke, stueck
        return bestes
