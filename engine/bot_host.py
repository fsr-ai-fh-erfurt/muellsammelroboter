"""Kindprozess: lädt eine Bot-Datei und beantwortet Anfragen als JSON-Zeilen.

Wird nie direkt benutzt, sondern von engine/runner.py gestartet:
    python3 -m engine.bot_host <pfad-zur-bot-datei>

Zwei Dinge sind hier wichtig:
1. `print()` aus Studierenden-Code darf das Protokoll nicht zerstören. Deshalb wird
   Dateideskriptor 1 auf stderr umgebogen und das Protokoll auf eine beiseitegelegte
   Kopie geschrieben.
2. Nichts, was der Bot tut, darf diesen Prozess umbringen — jeder Fehler wird gemeldet
   und der Zug als `warte` beantwortet.
"""

import importlib.util
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.zustand import Zustand  # noqa: E402


def _protokoll_kanal():
    """Gibt einen Schreibkanal auf das echte stdout zurück und biegt fd 1 auf stderr um."""
    try:
        sys.stdout.flush()
    except Exception:
        pass
    kopie = os.dup(1)
    os.dup2(2, 1)
    return os.fdopen(kopie, "w", encoding="utf-8", buffering=1)


def _modul_laden(pfad):
    name = "studi_bot_" + os.path.splitext(os.path.basename(pfad))[0]
    spezifikation = importlib.util.spec_from_file_location(name, pfad)
    if spezifikation is None or spezifikation.loader is None:
        raise ImportError("Die Datei %s lässt sich nicht als Python-Modul laden." % pfad)
    modul = importlib.util.module_from_spec(spezifikation)
    sys.modules[name] = modul
    spezifikation.loader.exec_module(modul)
    return modul


def _bot_finden(modul):
    kandidat = getattr(modul, "Roboter", None)
    if isinstance(kandidat, type):
        return kandidat()
    for name in sorted(dir(modul)):
        if name.startswith("_"):
            continue
        obj = getattr(modul, name)
        if isinstance(obj, type) and hasattr(obj, "entscheide") \
                and getattr(obj, "__module__", None) == modul.__name__:
            return obj()
    funktion = getattr(modul, "entscheide", None)
    if callable(funktion):
        class AusFunktion:
            def entscheide(self, zustand):
                return funktion(zustand)
        return AusFunktion()
    raise AttributeError(
        "In der Datei steht keine Klasse `Roboter` mit einer Methode `entscheide`."
    )


def _name_von(bot, modul, pfad):
    for quelle in (bot, modul):
        wert = getattr(quelle, "NAME", None)
        if isinstance(wert, str) and wert.strip():
            return wert.strip()[:60]
    return os.path.splitext(os.path.basename(pfad))[0]


def main():
    if len(sys.argv) < 2:
        print("Aufruf: python3 -m engine.bot_host <bot.py>", file=sys.stderr)
        return 2
    pfad = sys.argv[1]
    protokoll = _protokoll_kanal()

    bot = None
    name = os.path.splitext(os.path.basename(pfad))[0]
    startfehler = None
    try:
        modul = _modul_laden(pfad)
        bot = _bot_finden(modul)
        name = _name_von(bot, modul, pfad)
    except BaseException:
        startfehler = traceback.format_exc(limit=6)

    protokoll.write(json.dumps({
        "nr": 0, "bereit": bot is not None, "name": name, "fehler": startfehler,
    }, ensure_ascii=False) + "\n")

    for zeile in sys.stdin:
        zeile = zeile.strip()
        if not zeile:
            continue
        try:
            anfrage = json.loads(zeile)
        except ValueError:
            continue
        if anfrage.get("ende"):
            break
        nr = anfrage.get("nr", 0)
        aktion, regel, fehler = "warte", None, None
        if bot is not None:
            try:
                zustand = Zustand(anfrage["sicht"])
                antwort = bot.entscheide(zustand)
                regel = zustand.aktive_regel
                if isinstance(antwort, str):
                    aktion = antwort.strip().lower()
                elif isinstance(antwort, (list, tuple)) and antwort:
                    aktion = str(antwort[0]).strip().lower()
                    if len(antwort) > 1 and type(antwort[1]) is int:
                        regel = antwort[1]
            except BaseException:
                fehler = traceback.format_exc(limit=6)
        antwort = {"nr": nr, "aktion": aktion, "regel": regel}
        if fehler:
            antwort["fehler"] = fehler
        try:
            protokoll.write(json.dumps(antwort, ensure_ascii=False) + "\n")
        except BaseException:
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
