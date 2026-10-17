"""Fehlermeldungen auf Deutsch — mit Zeilennummer und Vorschlag.

Zielgruppe sind Menschen, die zum ersten Mal programmieren. Eine Meldung muss sagen,
WAS in WELCHER Zeile fehlt und WIE es richtig aussieht. „SyntaxError at line 4" ist
hier ein Fehler im Programm, nicht im Pseudocode.
"""


class RegelFehler(Exception):
    """Ein Problem in einer Zeile des Pseudocodes."""

    def __init__(self, zeile, text, vorschlag=None, spalte=None, beispiel=None):
        self.zeile = zeile
        self.text = text
        self.vorschlag = vorschlag
        self.spalte = spalte
        self.beispiel = beispiel
        super().__init__(self.vollstaendig())

    def vollstaendig(self):
        teile = ["Zeile %d: %s" % (self.zeile, self.text)]
        if self.vorschlag:
            teile.append("Meintest du `%s`?" % self.vorschlag)
        if self.beispiel:
            teile.append("So geht es: `%s`" % self.beispiel)
        return " ".join(teile)

    def als_dict(self):
        return {
            "zeile": self.zeile,
            "spalte": self.spalte,
            "text": self.text,
            "vorschlag": self.vorschlag,
            "beispiel": self.beispiel,
            "meldung": self.vollstaendig(),
        }


class Hinweis:
    """Kein Fehler, aber vermutlich nicht gewollt."""

    def __init__(self, zeile, text):
        self.zeile = zeile
        self.text = text

    def als_dict(self):
        return {"zeile": self.zeile, "text": self.text, "meldung":
                "Zeile %d: %s" % (self.zeile, self.text) if self.zeile else self.text}


def abstand(a, b):
    """Levenshtein-Abstand — für „Meintest du ...?"."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    vorherige = list(range(len(b) + 1))
    for i, zeichen_a in enumerate(a, 1):
        aktuelle = [i]
        for j, zeichen_b in enumerate(b, 1):
            aktuelle.append(min(
                vorherige[j] + 1,
                aktuelle[j - 1] + 1,
                vorherige[j - 1] + (zeichen_a != zeichen_b),
            ))
        vorherige = aktuelle
    return vorherige[-1]


def vorschlag(wort, bekannte):
    """Das ähnlichste bekannte Wort — oder None, wenn nichts nahe genug liegt."""
    if not wort:
        return None
    bester = None
    beste = None
    for kandidat in sorted(bekannte):
        d = abstand(wort, kandidat)
        if beste is None or d < beste:
            beste, bester = d, kandidat
    if bester is None:
        return None
    grenze = max(1, min(3, len(wort) // 2 + 1))
    return bester if beste <= grenze else None
