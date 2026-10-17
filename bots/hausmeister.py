# Mitgelieferter Gegner: die Qualifikationshürde.
#
# Der Hausmeister rechnet, statt nur zum nächsten Stück zu fahren. Für jedes
# Müllstück wiegt er den Wert gegen den Weg ab — für Elektroschrott fährt er weit,
# für Papier nur um die Ecke. Dazu meidet er verrottetes Zeug, nimmt den Zonenbonus
# mit und fährt rechtzeitig heim.
#
# Er ist ein Zustandsautomat mit zwei Modi und damit genauso gebaut wie das, was
# die Werkstatt aus Regeln erzeugt: `self.modus` sagt, wo er gerade ist, je Modus
# gibt es eine Methode, und ein Wechsel kostet keinen Zug — die Methode gibt `None`
# zurück, und `entscheide` prüft sofort die Regeln des neuen Modus. In der
# Regelsprache steht derselbe Roboter so da:
#
#   LET wegkosten = 3
#   LET heimkehr  = 25
#
#   STATE sammeln
#     IF restliche_ticks < heimkehr AND NOT ladung_ist_leer THEN GOTO heimweg
#     IF ladung_ist_voll THEN GOTO heimweg
#     IF akku < 30 AND NOT ladung_ist_leer THEN GOTO heimweg
#     IF kann_pressen AND freie_plaetze <= 2 AND abstand_zu depot > 6 THEN presse
#     ELSE fahre_zu BEST muell BY wert * bonus - wegkosten * abstand
#
#   STATE heimweg
#     IF ladung_ist_leer THEN GOTO sammeln
#     ELSE fahre_zu depot
#
# Die Modi ordnen hier seine Regeln, sie ändern seine Strategie nicht: Er trifft
# Zug für Zug dieselbe Entscheidung wie die flache Regelliste von früher — das ist
# über je 6 Seeds gegen einen sammelnden und einen rammenden Gegner nachgemessen,
# Zug für Zug identisch. Wer die Datei liest, sieht die Bauform; wer gegen ihn
# spielt, merkt keinen Unterschied.
#
# Ausprobiert und wieder verworfen: ihn stur bis zum Depot durchfahren zu lassen,
# sobald er einmal im Modus `heimweg` ist. Das klingt entschlossener, kostet aber
# Punkte — er verpasst dabei Müll, der auf dem Heimweg erst lohnend wird. Im
# direkten Vergleich über 40 Seeds hat die durchfahrende Fassung 38.8 % der Spiele
# gewonnen, diese hier 61.2 %. Deshalb prüft `_muss_heim` in jedem Zug neu, ob der
# Grund für den Heimweg überhaupt noch gilt.
#
# Gegner ignoriert er vollständig — genau da ist er zu schlagen. Wer ihn abpasst,
# wenn er voll beladen heimfährt, nimmt ihm eine ganze Ladung ab.

BESCHREIBUNG = "Wiegt Wert gegen Weg, meidet altes Zeug, fährt rechtzeitig heim. Die Hürde."
NAME = "Der Hausmeister"

WEGKOSTEN = 3          # so viele Punkte ist ihm ein Schritt Umweg wert
MINDESTWERT = 5        # darunter lässt er liegen
HEIMKEHR_PUFFER = 25   # so früh vor Schluss fährt er heim
AKKU_GRENZE = 30
PRESSE_WEG = 6         # erst ab so vielen Schritten zum Depot lohnt das Pressen
PRESSE_PLATZ = 2       # und nur, wenn höchstens so viele Plätze frei sind


class Roboter:
    NAME = NAME
    START_MODUS = "sammeln"

    def __init__(self):
        self.modus = self.START_MODUS

    def entscheide(self, zustand):
        for _ in range(zustand.max_wechsel):
            aktion = self._modus_schritt(zustand)
            if aktion is not None:
                return aktion
        return "warte"

    def _modus_schritt(self, zustand):
        """Die Aktion für diesen Tick — oder None, wenn nur der Modus wechselte."""
        if self.modus == "heimweg":
            return self._modus_heimweg(zustand)
        return self._modus_sammeln(zustand)

    # ---------------------------------------------------------------- Modi

    def _modus_sammeln(self, zustand):
        if self._muss_heim(zustand):
            zustand.regel(1)
            return self._wechsel("heimweg")

        # Die Presse: Drei gleiche Teile werden zu einem Ballen und machen Platz.
        # Er presst nur, wenn der Heimweg weit und der Laderaum eng ist — sonst
        # kostet der Wertverlust mehr, als der gewonnene Platz einbringt.
        if (zustand.kann_pressen and zustand.freie_plaetze <= PRESSE_PLATZ
                and zustand.abstand_zu_depot() > PRESSE_WEG):
            zustand.regel(3)
            return "presse"

        ziel = self._bestes_ziel(zustand)
        if ziel is not None:
            zustand.regel(4)
            return zustand.fahre_zu_feld(ziel["x"], ziel["y"])

        # Nichts lohnt sich gerade: Ladung heimbringen, sonst in der Zone auf
        # Nachschub warten. Hier wird der Modus bewusst NICHT gewechselt — der
        # Grund kann schon im nächsten Zug weg sein, weil neuer Müll fällt oder
        # ein Stück durch den kürzeren Weg plötzlich lohnt. Er fährt also Richtung
        # Depot und prüft trotzdem jeden Zug neu.
        if not zustand.ladung_ist_leer:
            zustand.regel(5)
            return zustand.fahre_zu_depot()
        zustand.regel(6)
        return zustand.fahre_zu_zone()

    def _modus_heimweg(self, zustand):
        # Der Heimweg gilt genau so lange, wie sein Grund gilt. Sobald keiner mehr
        # zutrifft — abgeliefert, Akku wieder voll —, geht es zurück an die Arbeit.
        if not self._muss_heim(zustand):
            zustand.regel(7)
            return self._wechsel("sammeln")

        zustand.regel(8)
        return zustand.fahre_zu_depot()

    # ---------------------------------------------------------------- Hilfen

    def _wechsel(self, modus):
        """Moduswechsel ohne Zugverlust: `None` heißt „weiter im neuen Modus"."""
        self.modus = modus
        return None

    def _muss_heim(self, zustand):
        """Die drei Gründe für den Heimweg — sie entscheiden über beide Modi."""
        # Voll ist voll: mehr geht nicht drauf.
        if zustand.ladung_ist_voll:
            return True
        if zustand.ladung_ist_leer:
            return False
        # Vor Schluss heim, die Restladung zählt sonst nur zur Hälfte. Und mit
        # leerem Akku wird man langsam; Abliefern lädt wieder auf.
        return (zustand.restliche_ticks <= HEIMKEHR_PUFFER
                or zustand.akku < AKKU_GRENZE)

    def _bestes_ziel(self, zustand):
        """Wert minus Weg, Zonenbonus eingerechnet, verrottetes Zeug ausgelassen."""
        bestes = None
        beste_marke = 0
        for stueck in zustand.muell_auswahl(mindestwert=MINDESTWERT):
            weg = zustand.abstand_zu_feld(stueck["x"], stueck["y"])
            if weg >= zustand.unerriechbar:
                continue
            wert = stueck["wert"]
            if zustand.ist_in_zone(stueck["x"], stueck["y"]):
                wert *= zustand.zone_faktor
            marke = wert - weg * WEGKOSTEN
            if marke > beste_marke:
                beste_marke, bestes = marke, stueck
        return bestes
