"""Was eine Regel kostet — in Zügen und Akku.

Die Angabe steht als Kommentar in der Abgabedatei und in der Werkstatt unter dem
Spielfeld. Sie ist eine Lernhilfe: Wer sieht, dass `fahre_zu depot` nicht einen Zug
kostet, sondern einen je Schritt, versteht von selbst, warum sich ein weiter Umweg
für Papier nicht lohnt.

Ehrlich bleiben ist wichtiger als knapp sein: Wo die Kosten vom Spielstand abhängen,
sagt der Text das dazu und nennt den Wert, mit dem man sie ausrechnen kann.
"""


def _akku(kosten, feld, ersatz):
    """Der Zahlenwert aus der config.json — oder ein Text ohne Zahl."""
    if not kosten or feld not in kosten:
        return ersatz
    return "%d Akku" % kosten[feld]


def ziel_text(ziel):
    """Wie man den Weg zu diesem Ziel selbst nachrechnet — ein halber Satz."""
    if ziel is None:
        return None
    if ziel.was == "depot":
        return "hängt vom Weg ab — abstand_zu depot sagt es dir"
    if ziel.was == "gegner":
        return "hängt vom Weg ab — abstand_zu gegner sagt es dir"
    if ziel.was == "zone":
        return "hängt vom Weg ab — abstand_zu zone sagt es dir"
    if ziel.was == "feld":
        return ("hängt vom Weg ab — abstand_zu feld(%d, %d) sagt es dir"
                % (ziel.x, ziel.y))
    if ziel.was == "weg_von_gegner":
        return "hängt vom Abstand zum Gegner ab — abstand_zu gegner sagt es dir"
    if ziel.was == "muell":
        if getattr(ziel, "formel", None) is not None:
            return None          # das Ziel steht erst nach der Rechnung fest
        teile = []
        if getattr(ziel, "sorte", None):
            teile.append(ziel.sorte)
        if getattr(ziel, "nur_in_zone", False):
            teile.append("in_zone")
        muell = "naechster_muell%s" % ("(%s)" % ", ".join(teile) if teile else "")
        return "hängt vom Weg ab — abstand_zu %s sagt es dir" % muell
    return "hängt vom Weg ab"


def aktion_kosten(aktion, kosten=None):
    """Ein Satz: was diese Aktion an Zügen und Akku kostet."""
    bewegung = _akku(kosten, "bewegung", "etwas Akku")
    rammen = _akku(kosten, "rammen", "noch mehr Akku")

    if aktion.art == "warte":
        return "1 Zug, kein Akku."
    if aktion.art == "goto" and getattr(aktion, "folge", False):
        return ("%d Züge — einer je Schritt der Folge, jeder kostet so viel wie die Aktion "
                "allein. Danach weiter in Modus `%s`." % (aktion.anzahl, aktion.danach))
    if aktion.art == "goto":
        return ("0 Züge — ein Moduswechsel kostet nichts. Der Roboter prüft sofort "
                "die Regeln von Modus `%s`. Ist er schon darin, tut die Regel nichts "
                "und die nächste kommt dran." % aktion.modus)
    if aktion.art == "fahre":
        return ("1 Zug, %s je wirklich ausgeführten Schritt. Gegen eine Wand (auch "
                "Innenwand) kostet er nichts. Steht ein Gegner im Weg, ist es ein "
                "Rammen: der Stoß kostet den Gegner und dich je %s — auch dann, wenn "
                "der Schub blockiert ist." % (bewegung, rammen))
    if aktion.art == "presse":
        zahlen = kosten or {}
        if {"presse_anzahl", "presse_dauer", "presse_abschlag"} <= set(zahlen):
            return ("%d Züge, kein Akku. Aus %d gleichen Teilen wird ein Ballen; er "
                    "belegt einen Platz und ist %d %% weniger wert als die Teile "
                    "zusammen." % (zahlen["presse_dauer"], zahlen["presse_anzahl"],
                                   zahlen["presse_abschlag"]))
        return ("Ein paar Züge, kein Akku. Aus gleichen Teilen wird ein Ballen; er "
                "belegt einen Platz und ist etwas weniger wert als die Teile zusammen.")
    if aktion.art == "fahre_zu" and getattr(aktion, "rammen", False):
        return ("1 Zug, %s für den Schritt und %s für den Stoß — den zahlen beide. "
                "Bis zum Treffer sind es so viele Züge, wie der Gegner weit weg ist "
                "(abstand_zu gegner), und der bewegt sich auch."
                % (bewegung, rammen))
    if aktion.art == "fahre_zu":
        ziel = aktion.ziel
        weg = ziel_text(ziel)
        satz = "1 Zug und %s je Schritt." % bewegung
        if weg:
            return "%s Wie viele Schritte es werden, %s." % (satz, weg)
        if getattr(ziel, "was", None) == "muell" and \
                getattr(ziel, "formel", None) is not None:
            return ("%s Wie viele Schritte es werden, hängt davon ab, welches Stück die "
                    "Rechnung gewinnt und wie weit das liegt." % satz)
        return "%s Wie viele Schritte es werden, hängt vom Weg ab." % satz
    return "1 Zug."
