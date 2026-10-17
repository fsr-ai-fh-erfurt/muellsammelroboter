# Mitgelieferter Gegner: der Beweis, dass die Falle funktioniert.
#
# Von außen sieht man nur, WIE VIELE Teile ein Roboter trägt, nicht welche. Der
# Fassbluffer nutzt das aus: Er holt sich ein radioaktives Fass, füllt daneben ganz
# normal auf und sucht die Nähe des Gegners. Wer ihn rammt, zieht ein zufälliges
# Teil — und hat mit etwas Glück das Fass am Hals.
#
# Ein Fass ist aber nur dann kein reines Verlustgeschäft, wenn der Bluff Aussicht
# hat: Der Gegner muss in der Nähe und schwer beladen sein — sonst bleibt das Fass
# liegen und er sammelt normal (bzw. wartet in der Zone auf Nachschub). Gegen einen
# passiven Sammler, der nie rammt, wird so gar nicht erst ein Fass aufgenommen.
# Ein einmal getragenes Fass bringt er auch nicht extra heim: Das wäre ein sicherer
# Selbstschaden; es geht erst mit der vollen Ladung oder am Rundenende mit heim.
#
# Er hat vier Modi, und an ihm sieht man den Unterschied zwischen Modus und
# Gedächtnis: `self.modus` sagt, WAS er gerade vorhat — `bluff_ticks` und
# `aufgegeben` sind darüber hinaus richtiges Gedächtnis und zählen mit, ob der
# Bluff überhaupt jemanden reizt. Beides zusammen macht ihn zu dem einzigen
# mitgelieferten Gegner, der sich im Lauf einer Runde umstellt.
#
#   sammeln  → besorgen   Gegner sichtbar und beladen, Fass in Reichweite
#   besorgen → sammeln    sobald das Fass an Bord ist (erst noch auffüllen)
#   sammeln  → bluffen    Fass + positives Teil an Bord, Gegner in Sicht
#   bluffen  → sammeln    wenn niemand mehr da ist — oder der Bluff zu lange reizlos blieb
#   alle     → heimweg    wenn voll, wenn der Akku knapp wird, vor Rundenschluss
#
# Wichtig dabei: `_bluff_verfolgen` wird genau einmal je Tick aufgerufen, oben in
# `entscheide` — nicht in den Modi. Die Modusschleife kann mehrmals laufen, und
# dann würde der Zähler mehrfach hochlaufen.

BESCHREIBUNG = "Trägt ein Fass spazieren und provoziert — gibt aber auf, wenn niemand rammt."
NAME = "Fassbluffer"

WEGKOSTEN = 3
GEDULD = 70            # so lange wird auf einen Rammangriff gewartet
FASS_REICHWEITE = 6    # weiter fährt er für ein Fass nicht
BLUFF_LADUNG = 3       # erst ab so vielen Teilen lohnt sich ein Bluff
BLUFF_ABSTAND = 6      # und der Gegner muss dafür in Reichweite sein
BLUFF_START_LADUNG = 2 # Fass + mindestens ein positives Teil, sonst rammt niemand


class Roboter:
    NAME = NAME
    START_MODUS = "sammeln"

    def __init__(self):
        self.modus = self.START_MODUS
        self.bluff_ticks = 0
        self.hatte_fass = False
        self.aufgegeben = False

    def entscheide(self, zustand):
        # Genau einmal je Tick — die Modusschleife darunter läuft womöglich öfter.
        self._bluff_verfolgen(zustand, self._hat_fass(zustand))

        for _ in range(zustand.max_wechsel):
            aktion = self._modus_schritt(zustand)
            if aktion is not None:
                return aktion
        return "warte"

    def _modus_schritt(self, zustand):
        """Die Aktion für diesen Tick — oder None, wenn nur der Modus wechselte."""
        if self.modus == "besorgen":
            return self._modus_besorgen(zustand)
        if self.modus == "bluffen":
            return self._modus_bluffen(zustand)
        if self.modus == "heimweg":
            return self._modus_heimweg(zustand)
        return self._modus_sammeln(zustand)

    # ---------------------------------------------------------------- Modi

    def _modus_sammeln(self, zustand):
        if self._muss_heim(zustand):
            zustand.regel(1)
            return self._wechsel("heimweg")

        # Ohne Fass ist der Bluff wirkungslos — erst eins besorgen. Aber nur,
        # wenn der Bluff Aussicht hat: gegen einen reinen Sammler ist das Fass
        # totes Gewicht, und dann sammelt er lieber selbst.
        if self._fass_lohnt(zustand):
            zustand.regel(2)
            return self._wechsel("besorgen")

        # Ein Fass allein lohnt den Angriff nicht: Der Gegner rammt erst bei
        # genug Beute, also erst noch ein positives Teil einsammeln.
        if (self._hat_fass(zustand) and zustand.ladung >= BLUFF_START_LADUNG
                and zustand.gegner_sichtbar and not self.aufgegeben):
            zustand.regel(3)
            return self._wechsel("bluffen")

        ziel = self._bestes_ziel(zustand)
        if ziel is not None:
            zustand.regel(4)
            return zustand.fahre_zu_feld(ziel["x"], ziel["y"])

        # Nichts lohnt sich gerade: Ladung heimbringen, sonst in der Zone auf
        # Nachschub warten. Ein einsames Fass bringt er nicht extra heim — es
        # wäre ein sicherer Selbstschaden. Kein Moduswechsel — der Grund kann im
        # nächsten Zug weg sein, weil neuer Müll fällt oder ein Gegner in Sicht
        # kommt.
        if not zustand.ladung_ist_leer and not self._nur_fass(zustand):
            zustand.regel(5)
            return zustand.fahre_zu_depot()
        zustand.regel(6)
        return zustand.fahre_zu_zone()

    def _modus_besorgen(self, zustand):
        if self._muss_heim(zustand):
            zustand.regel(7)
            return self._wechsel("heimweg")

        # Fass an Bord: erst noch ein positives Teil sammeln, dann damit vor die
        # Nase des Gegners — mit nur dem Fass würde der Angriff nicht lohnen.
        if self._hat_fass(zustand):
            zustand.regel(8)
            if zustand.ladung >= BLUFF_START_LADUNG:
                return self._wechsel("bluffen")
            return self._wechsel("sammeln")

        # Niemand mehr da, den es zu reizen lohnt, oder kein Fass in Reichweite.
        if not self._fass_lohnt(zustand):
            zustand.regel(9)
            return self._wechsel("sammeln")

        zustand.regel(10)
        return zustand.fahre_zu_muell(sorte="radioaktiv")

    def _modus_bluffen(self, zustand):
        if self._muss_heim(zustand):
            zustand.regel(11)
            return self._wechsel("heimweg")

        # Fass weg — entweder abgeliefert oder erfolgreich untergejubelt.
        if not self._hat_fass(zustand):
            zustand.regel(12)
            return self._wechsel("sammeln")

        # Ohne Publikum kein Bluff — und nach zu langer Warterei auch nicht mehr:
        # Das Fass bleibt an Bord, aber er läuft keinem Gegner mehr nach.
        if not zustand.gegner_sichtbar or self.aufgegeben:
            zustand.regel(13)
            return self._wechsel("sammeln")

        abstand = zustand.abstand_zu_gegner()
        if abstand > 2:
            zustand.regel(14)
            return zustand.fahre_zu_gegner()
        if abstand == 2:
            zustand.regel(15)
            return zustand.fahre_zu_gegner()   # frontal: klaut auch selbst
        zustand.regel(16)
        return "warte"                         # direkt daneben stehen bleiben

    def _modus_heimweg(self, zustand):
        # Der Heimweg gilt genau so lange, wie sein Grund gilt — sonst zurück
        # an die Arbeit, samt Fass.
        if not self._muss_heim(zustand):
            zustand.regel(17)
            return self._wechsel("sammeln")

        zustand.regel(18)
        return zustand.fahre_zu_depot()

    # ---------------------------------------------------------------- Hilfen

    def _wechsel(self, modus):
        """Moduswechsel ohne Zugverlust: `None` heißt „weiter im neuen Modus"."""
        self.modus = modus
        return None

    def _hat_fass(self, zustand):
        return zustand.habe("radioaktiv")

    def _nur_fass(self, zustand):
        return self._hat_fass(zustand) and zustand.ladung == 1

    def _muss_heim(self, zustand):
        """Die Gründe, die jeden Bluff abbrechen — in jedem Modus dieselben."""
        if zustand.ladung_ist_voll:
            return True
        if zustand.ladung_ist_leer:
            return False
        # Zum Rundenende alles heimbringen: die Restladung zählt sonst nur halb,
        # das Fass aber voll negativ.
        return (zustand.restliche_ticks <= self._heimweg(zustand) + 4
                or zustand.akku < 30)

    def _fass_lohnt(self, zustand):
        """Nur ein Bluff mit Aussicht lohnt: Der Gegner muss in der Nähe und
        schwer beladen sein — sonst ist das Fass nur totes Gewicht. Gegen einen
        passiven Sammler, der nie rammt, bleibt es liegen.
        """
        return (not self._hat_fass(zustand)
                and not self.aufgegeben
                and zustand.gegner_sichtbar
                and zustand.gegner_ladung >= BLUFF_LADUNG
                and zustand.abstand_zu_gegner() <= BLUFF_ABSTAND
                and zustand.abstand_zu_muell(sorte="radioaktiv") < FASS_REICHWEITE)

    def _bluff_verfolgen(self, zustand, hat_fass):
        """Zählt, wie lange das Fass schon spazieren getragen wird."""
        if hat_fass:
            self.bluff_ticks += 1
            # Die Geduld gilt auch beim Tragen: Wird das Fass nicht bald zum
            # Angriff, gibt er den Bluff auf und sammelt wieder normal.
            if self.bluff_ticks > GEDULD:
                self.aufgegeben = True
        else:
            if self.hatte_fass and self.bluff_ticks <= GEDULD:
                # Das Fass ist weg, obwohl er es nicht abgeliefert hat: der Bluff hat
                # gesessen. Also gleich das nächste holen.
                self.aufgegeben = False
            elif self.bluff_ticks > GEDULD:
                self.aufgegeben = True
            self.bluff_ticks = 0
        self.hatte_fass = hat_fass

    def _heimweg(self, zustand):
        weg = zustand.abstand_zu_depot()
        return weg * 2 if zustand.akku < 30 else weg

    def _bestes_ziel(self, zustand):
        bestes = None
        beste_marke = 0
        for stueck in zustand.muell_auswahl(mindestwert=5):
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
