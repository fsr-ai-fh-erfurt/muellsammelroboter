"""Die beiden harten Randbedingungen des Projekts, als Test.

1. Es läuft auf Python 3.10 — dort steht es am Turniertag, hier nicht unbedingt.
2. Es braucht nichts außer der Standardbibliothek.

Beides lässt sich prüfen, ohne eine Zeile auszuführen: der Quelltext wird mit
`ast.parse(..., feature_version=(3, 10))` gelesen, und die Importe werden gegen
`sys.stdlib_module_names` gehalten. Ein Test ist hier mehr wert als ein einmaliger
Blick, weil neuere Schreibweisen sich unbemerkt einschleichen.
"""

import ast
import os
import sys
import unittest

PROJEKT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MINDESTVERSION = (3, 10)

# Ordner, die nicht zum ausgelieferten Programm gehören.
AUSGENOMMEN = {"__pycache__", ".git", ".idea", ".vscode", "abgaben",
               ".venv", "venv", ".tox", "node_modules", "build", "dist"}
# Diese Datei ist absichtlich kaputt — sie prüft die Fehlerbehandlung im Runner.
ABSICHTLICH_KAPUTT = {os.path.join("tests", "kaputte_bots", "syntaxfehler.py")}
# Pakete des Projekts selbst.
EIGEN = {"engine", "language", "web", "tests", "balance", "start"}


def ausgenommene_ordner(ordner):
    """Der Abstieg in venv, Build-Ausgaben und Versionsverwaltung ist nicht nötig."""
    return sorted(o for o in ordner if o not in AUSGENOMMEN)


def python_dateien():
    for wurzel, ordner, dateien in os.walk(PROJEKT):
        ordner[:] = ausgenommene_ordner(ordner)
        for name in sorted(dateien):
            if not name.endswith(".py"):
                continue
            pfad = os.path.join(wurzel, name)
            kurz = os.path.relpath(pfad, PROJEKT)
            if kurz.replace("/", os.sep) in ABSICHTLICH_KAPUTT:
                continue
            yield kurz, pfad


def oberste_module(baum):
    """Alle Modulnamen, die eine Datei importiert — nur der erste Namensteil."""
    namen = set()
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Import):
            for teil in knoten.names:
                namen.add(teil.name.split(".")[0])
        elif isinstance(knoten, ast.ImportFrom):
            if knoten.level:                     # relativer Import, bleibt im Projekt
                continue
            if knoten.module:
                namen.add(knoten.module.split(".")[0])
    return namen


class TestUmgebungAusnahmen(unittest.TestCase):
    """Ein lokales venv darf den Testlauf nicht in site-packages führen.

    Statt eines echten venv — langsam und ohne Erkenntnis — wird die Sperrliste
    selbst geprüft und dazu die Filterfunktion, die `os.walk` damit steuert.
    """

    def test_unerwuenschte_ordner_sind_ausgenommen(self):
        for name in (".venv", "venv", ".tox", "node_modules", "build", "dist",
                     "__pycache__", ".git", ".idea", ".vscode", "abgaben"):
            self.assertIn(name, AUSGENOMMEN)

    def test_filter_laesst_nur_projektordner_uebrig(self):
        gemischt = ["engine", ".venv", "__pycache__", "tests", "node_modules",
                    "venv", "build", "dist", ".tox"]
        self.assertEqual(ausgenommene_ordner(gemischt), ["engine", "tests"])


class TestPythonVersion(unittest.TestCase):
    def test_alles_ist_unter_python_310_lesbar(self):
        fehler = []
        gepruefte = 0
        for kurz, pfad in python_dateien():
            with open(pfad, "r", encoding="utf-8") as datei:
                quelle = datei.read()
            gepruefte += 1
            try:
                ast.parse(quelle, filename=kurz, feature_version=MINDESTVERSION)
            except SyntaxError as problem:
                fehler.append("%s, Zeile %s: %s" % (kurz, problem.lineno, problem.msg))
        self.assertGreater(gepruefte, 20, "Es wurden kaum Dateien gefunden.")
        self.assertEqual(fehler, [], "Neuer als Python %d.%d:\n  %s"
                         % (MINDESTVERSION + ("\n  ".join(fehler),)))

    def test_die_erzeugte_abgabedatei_ebenfalls(self):
        from language.compiler import uebersetzen
        ergebnis = uebersetzen(
            "IF ladung_ist_voll THEN fahre_zu depot\n"
            "ELSE fahre_zu naechster_muell\n", "Team Test", "")
        self.assertTrue(ergebnis["gueltig"], ergebnis["fehler"])
        ast.parse(ergebnis["quelle"], filename="abgabe.py",
                  feature_version=MINDESTVERSION)

    def test_start_py_nennt_dieselbe_mindestversion(self):
        from start import MINDESTVERSION as aus_start
        self.assertEqual(aus_start, MINDESTVERSION)


class TestNurStandardbibliothek(unittest.TestCase):
    def test_kein_import_von_ausserhalb(self):
        erlaubt = set(sys.stdlib_module_names) | EIGEN
        fremd = {}
        for kurz, pfad in python_dateien():
            with open(pfad, "r", encoding="utf-8") as datei:
                baum = ast.parse(datei.read(), filename=kurz)
            for modul in sorted(oberste_module(baum) - erlaubt):
                fremd.setdefault(modul, []).append(kurz)
        self.assertEqual(fremd, {},
                         "Nur die Standardbibliothek ist erlaubt, gefunden: %s" % fremd)


class TestEigenerZufall(unittest.TestCase):
    """Regel 4: der Zufall kommt aus engine/rng.py, nie aus `random`."""

    def test_niemand_importiert_random(self):
        treffer = []
        for kurz, pfad in python_dateien():
            with open(pfad, "r", encoding="utf-8") as datei:
                baum = ast.parse(datei.read(), filename=kurz)
            if "random" in oberste_module(baum):
                treffer.append(kurz)
        self.assertEqual(treffer, [],
                         "Bitte engine/rng.py benutzen statt random: %s" % treffer)


class TestKeineExternenDateienImBrowser(unittest.TestCase):
    """Keine Schrift, kein CDN, keine Bibliothek von außen — auch nicht im HTML."""

    def test_kein_verweis_nach_draussen(self):
        ordner = os.path.join(PROJEKT, "web", "static")
        treffer = []
        for name in sorted(os.listdir(ordner)):
            with open(os.path.join(ordner, name), "r", encoding="utf-8") as datei:
                for nummer, zeile in enumerate(datei, 1):
                    for muster in ("http://", "https://", "//cdn", "@import url("):
                        if muster in zeile and "127.0.0.1" not in zeile:
                            treffer.append("%s:%d %s" % (name, nummer, zeile.strip()[:70]))
        self.assertEqual(treffer, [], "Verweise nach außen:\n  %s" % "\n  ".join(treffer))


if __name__ == "__main__":
    unittest.main()
