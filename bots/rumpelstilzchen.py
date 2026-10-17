# Mitgelieferter Gegner: fährt einfach zufällig herum.
# Zum Ausprobieren gedacht — wer den nicht schlägt, hat noch keine Strategie.

BESCHREIBUNG = "Fährt zufällig herum. Zum Ausprobieren."
NAME = "Rumpelstilzchen"
# Absichtlich trivial: zählt in balance.py nicht als Maßstab für die Zahlen.
BALANCE_MASSSTAB = "nein"


class Roboter:
    NAME = "Rumpelstilzchen"

    def entscheide(self, zustand):
        return zustand.zufall_richtung()
