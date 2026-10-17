# Golden-Szenario: ein Bot, der die Presse ausreizt.
#
# Hausmeister und Lauerer pressen nur selten — nur wenn sie eng beladen und weit
# vom Depot weg sind. Dieser Testbot presst dagegen in jedem Zug, in dem es geht,
# und friert damit die ganze Kette ein: sammeln, drei gleiche Teile pressen,
# Ballen abliefern. Er läuft ausschließlich in den Golden Tests, nicht im Turnier.

NAME = "Presse-Testbot"


class Roboter:
    def entscheide(self, zustand):
        if zustand.kann_pressen:
            return "presse"
        if zustand.ladung_ist_voll:
            return zustand.fahre_zu_depot()
        aktion = zustand.fahre_zu_muell("papier")
        if aktion == "warte":
            aktion = zustand.fahre_zu_muell()
        return aktion
