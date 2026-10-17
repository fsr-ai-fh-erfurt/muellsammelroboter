"""Die config.json: unsinnige Werte müssen beim Laden auffallen, nicht im Spiel.

Der FSR-Editor reicht jede Änderung durch `aus_dict` — was hier durchkommt, landet
im laufenden Turnier. Eine 0 im Nachschub-Intervall wäre dort ein ZeroDivisionError
mitten in der ersten Runde.
"""

import os
import subprocess
import sys
import unittest

from engine import config as config_modul


class TestConfigPruefung(unittest.TestCase):
    def daten(self):
        return config_modul.lade().als_dict()

    def setze(self, pfad, wert):
        daten = self.daten()
        teile = pfad.split(".")
        ziel = daten
        for teil in teile[:-1]:
            ziel = ziel[teil]
        ziel[teile[-1]] = wert
        return daten

    def erwarte_fehler(self, daten, stichwort):
        with self.assertRaises(ValueError) as gefangen:
            config_modul.pruefe(daten)
        self.assertIn(stichwort, str(gefangen.exception))

    def test_geladene_config_ist_gueltig(self):
        config_modul.pruefe(self.daten())

    def test_null_im_wechselintervall_der_zone(self):
        self.erwarte_fehler(self.setze("zone.wechsel_alle", 0), "zone.wechsel_alle")

    def test_null_im_nachschub_intervall(self):
        self.erwarte_fehler(self.setze("muell.nachschub_intervall", 0),
                            "nachschub_intervall")

    def test_startmuell_muss_positiv_und_durch_vier_teilbar_sein(self):
        self.erwarte_fehler(self.setze("muell.start_anzahl", 0), "start_anzahl")
        self.erwarte_fehler(self.setze("muell.start_anzahl", 1), "durch 4 teilbar")
        self.erwarte_fehler(self.setze("muell.start_anzahl", 6), "durch 4 teilbar")
        config_modul.pruefe(self.setze("muell.start_anzahl", 20))

    def test_kill_nach_ueberzogen_muss_positiv_sein(self):
        self.erwarte_fehler(self.setze("bots.kill_nach_ueberzogen", 0),
                            "kill_nach_ueberzogen")
        config_modul.pruefe(self.setze("bots.kill_nach_ueberzogen", 1))

    def test_leere_runde(self):
        self.erwarte_fehler(self.setze("spiel.runden_laenge", 0), "runden_laenge")

    def test_start_akku_ueber_max(self):
        self.erwarte_fehler(self.setze("akku.start", 101), "akku.start")

    def test_null_seeds(self):
        self.erwarte_fehler(self.setze("balance.seeds", 0), "balance.seeds")

    def test_balance_fehlt_ganz(self):
        daten = self.daten()
        del daten["balance"]
        self.erwarte_fehler(daten, "balance")

    def test_abschnitt_ist_null(self):
        self.erwarte_fehler(self.setze("presse", None), "presse")

    def test_abschnitt_ist_eine_zahl(self):
        self.erwarte_fehler(self.setze("server", 5), "server")

    def test_abschnitt_ist_ein_text(self):
        self.erwarte_fehler(self.setze("turnier", "kein Objekt"), "turnier")

    def test_muell_sorten_sind_kein_objekt(self):
        self.erwarte_fehler(self.setze("muell.sorten", "papier"), "muell.sorten")

    def test_muell_sorte_ist_kein_objekt(self):
        self.erwarte_fehler(self.setze("muell.sorten", {"papier": 5}),
                            "muell.sorten.papier")

    def test_sortenname_mit_punkt(self):
        daten = self.daten()
        daten["muell"]["sorten"]["a.b"] = {"wert": 1, "gewicht": 1, "anzeige": "X"}
        self.erwarte_fehler(daten, "Punkt")

    def test_fehlende_anzeige_der_sorte(self):
        daten = self.daten()
        del daten["muell"]["sorten"]["papier"]["anzeige"]
        self.erwarte_fehler(daten, "muell.sorten.papier.anzeige")

    def test_fehlende_anzeige_von_radioaktiv(self):
        daten = self.daten()
        del daten["radioaktiv"]["anzeige"]
        self.erwarte_fehler(daten, "radioaktiv.anzeige")

    def test_feld_ueberschreitet_die_obergrenze(self):
        daten = self.setze("spiel.breite", 65)
        daten["spiel"]["hoehe"] = 65
        self.erwarte_fehler(daten, "höchstens 64")

    def test_runden_laenge_ueberschreitet_die_obergrenze(self):
        self.erwarte_fehler(self.setze("spiel.runden_laenge", 10001), "höchstens 10000")

    def test_gleichstand_wiederholungen_ueberschreiten_die_obergrenze(self):
        self.erwarte_fehler(self.setze("turnier.gleichstand_wiederholungen", 101),
                            "höchstens 100")

    def test_gruppen_groesse_ueberschreitet_die_obergrenze(self):
        self.erwarte_fehler(self.setze("turnier.gruppen_groesse", 5), "höchstens 4")

    def test_gruppen_groesse_vier_ist_erlaubt(self):
        config_modul.pruefe(self.setze("turnier.gruppen_groesse", 4))

    def test_nachschub_intervall_ueberschreitet_die_obergrenze(self):
        self.erwarte_fehler(self.setze("muell.nachschub_intervall", 10001),
                            "höchstens 10000")

    def test_balance_seeds_ueberschreiten_die_obergrenze(self):
        self.erwarte_fehler(self.setze("balance.seeds", 1001), "höchstens 1000")

    def test_punkte_je_platz_darf_nur_zahlen_enthalten(self):
        self.erwarte_fehler(self.setze("turnier.punkte_je_platz", [3, "zwei", 1, 0]),
                            "punkte_je_platz")

    def test_null_im_zeitlimit(self):
        self.erwarte_fehler(self.setze("bots.zeitlimit_ms", 0), "bots.zeitlimit_ms")

    def test_presse_braucht_mindestens_zwei_teile(self):
        self.erwarte_fehler(self.setze("presse.anzahl", 1), "presse.anzahl")

    def test_presse_abschlag_unter_hundert(self):
        self.erwarte_fehler(self.setze("presse.abschlag_prozent", 100),
                            "presse.abschlag_prozent")

    def test_fehlende_datei_wird_deutsch_gemeldet(self):
        with self.assertRaises(ValueError) as gefangen:
            config_modul.lade("/gibt/es/ganz/sicher/nicht/config.json")
        self.assertIn("Datei nicht gefunden", str(gefangen.exception))

    def test_kein_gueltiges_json(self):
        with self.assertRaises(ValueError) as gefangen:
            config_modul.lade("/dev/null")
        self.assertIn("kein gültiges JSON", str(gefangen.exception))

    def test_zeitlimit_als_text(self):
        self.erwarte_fehler(self.setze("bots.zeitlimit_ms", "100"), "ganze Zahl")

    def test_breite_als_kommazahl(self):
        self.erwarte_fehler(self.setze("spiel.breite", 24.0), "spiel.breite")

    def test_max_wechsel_als_kommazahl(self):
        self.erwarte_fehler(self.setze("sprache.max_wechsel", 8.5), "sprache.max_wechsel")

    def test_port_als_text(self):
        self.erwarte_fehler(self.setze("server.port", "acht"), "server.port")

    def test_port_null_ist_ungueltig(self):
        self.erwarte_fehler(self.setze("server.port", 0), "server.port")

    def test_port_ueber_der_obergrenze(self):
        self.erwarte_fehler(self.setze("server.port", 70000), "server.port")

    def test_port_negativ_ist_ungueltig(self):
        self.erwarte_fehler(self.setze("server.port", -1), "server.port")

    def test_port_8080_ist_erlaubt(self):
        config_modul.pruefe(self.setze("server.port", 8080))

    def test_bool_ist_keine_ganzzahl(self):
        self.erwarte_fehler(self.setze("spiel.kapazitaet", True), "spiel.kapazitaet")

    def test_match_meldet_config_fehler_ohne_traceback(self):
        wurzel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ergebnis = subprocess.run(
            [sys.executable, "-m", "engine.match", "bots/hausmeister.py",
             "--config", "/dev/null"],
            cwd=wurzel, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        ausgabe = ergebnis.stdout + ergebnis.stderr
        self.assertNotEqual(ergebnis.returncode, 0)
        self.assertNotIn("Traceback", ausgabe)
        self.assertIn("kein gültiges JSON", ausgabe)


if __name__ == "__main__":
    unittest.main()
