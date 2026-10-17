# Mitgelieferter Gegner: sammelt stur den nächsten Müll und liefert ab, wenn voll.
# Kennt keine Gegner, kennt keine Zone, kennt keinen Wertverfall.

BESCHREIBUNG = "Sammelt stur den nächsten Müll und liefert ab, wenn voll."
NAME = "Fleißig"


class Roboter:
    NAME = "Fleißig"

    def entscheide(self, zustand):
        if zustand.ladung_ist_voll:
            return zustand.fahre_zu_depot()
        return zustand.fahre_zu_muell()
