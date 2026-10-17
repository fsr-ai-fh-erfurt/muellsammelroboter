"""Eigener deterministischer Zufallsgenerator.

Bewusst NICHT `random` aus der Standardbibliothek: dessen Ausgabe ist zwischen
Python-Versionen nicht garantiert, und das Turnier muss auf jedem Rechner denselben
Spielverlauf erzeugen. Hier: xorshift64* — kurz, ganzzahlig, überall gleich.
"""

MASKE64 = (1 << 64) - 1
_MULTIPLIKATOR = 0x2545F4914F6CDD1D
_STREUER = 0x9E3779B97F4A7C15


class Zufall:
    """Ganzzahliger Zufallsgenerator mit festem Startwert."""

    def __init__(self, seed):
        zustand = (int(seed) ^ _STREUER) & MASKE64
        if zustand == 0:
            zustand = _STREUER
        self._zustand = zustand

    def _naechster(self):
        x = self._zustand
        x ^= x >> 12
        x &= MASKE64
        x ^= (x << 25) & MASKE64
        x ^= x >> 27
        self._zustand = x & MASKE64
        return (self._zustand * _MULTIPLIKATOR) & MASKE64

    def zahl(self, obergrenze):
        """Ganzzahl aus 0 .. obergrenze-1."""
        if obergrenze <= 0:
            raise ValueError("obergrenze muss positiv sein")
        return self._naechster() % obergrenze

    def bereich(self, von, bis):
        """Ganzzahl aus von .. bis (beide einschließlich)."""
        return von + self.zahl(bis - von + 1)

    def gewichtet(self, paare):
        """paare: Liste aus (element, gewicht). Gewichte sind Ganzzahlen > 0."""
        gesamt = 0
        for _, gewicht in paare:
            gesamt += gewicht
        rest = self.zahl(gesamt)
        for element, gewicht in paare:
            if rest < gewicht:
                return element
            rest -= gewicht
        return paare[-1][0]
