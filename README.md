# Müllsammel-Roboter Turnier

Bot-Programmierspiel für die Ersti-Woche Informatik: Erstsemester schreiben in 2–3
Stunden Regeln in einer deutschen Pseudocode-Sprache, danach läuft ein K.-o.-Turnier
mit etwa 16 Teams. Alles läuft offline mit der Python-Standardbibliothek (3.10+,
Linux); es wird nichts installiert und keine Internetverbindung gebraucht.

Entstanden für die Ersti-Woche 2026 des Fachschaftsrats Angewandte Informatik.
Zwei (im Turnier auch vier) Roboter fahren über ein Gitter, sammeln Müll ein und
liefern ihn im eigenen Depot ab — wer nach 400 Zügen mehr Punkte hat, gewinnt. Wer
nach der Ersti-Woche weiterbasteln will: Die Spielregeln stehen in `SPEC.md`, die
Regelsprache in `ANLEITUNG.md`, und die fünf mitgelieferten Gegner in `bots/`
sind gute Beispiele, wie ein Roboter in Python aussieht.

## Schnellstart

```bash
python3 start.py                 # Werkstatt starten, Browser öffnet sich
python3 start.py --kein-browser  # ohne Browserfenster, Adresse wird gedruckt
python3 start.py --port 8080     # anderer Startport (belegte Ports werden übersprungen)
./start.sh                       # dasselbe unter Linux/macOS
```

Der Server legt `abgaben/`, `aufzeichnungen/` und `turnier/` beim Start selbst an.
Beenden mit `Strg+C`.

## Die Werkstatt (für die Teams)

1. Regeln in den Editor schreiben. Die Vorlage ist ein kleiner Zustandsautomat und
   läuft sofort; der Knopf **Vorlage** setzt sie zurück.
2. **Strg+Enter** startet einen Testlauf. Als Gegner ist „Keiner" vorgewählt — der
   eigene Roboter fährt allein; darunter lassen sich die mitgelieferten Gegner wählen.
3. Die Wiedergabe zeigt das Feld, die gerade greifende Regel (die Editorzeile leuchtet
   mit) und die Kosten je Regel. Play/Pause, Einzelschritt, Tempo und Zeitleiste
   stehen unter dem Feld.
4. **Speichern** legt einen Zwischenstand im Browser ab (`localStorage`),
   **Öffnen …** liest eine zuvor abgegebene Datei zurück, **Abgeben** lädt die fertige
   Bot-Datei herunter.

Die Abgabedatei definiert nur `class Roboter` mit `entscheide(zustand)` und importiert
nichts aus dem Projekt. Die Sprache steht vollständig in `ANLEITUNG.md` und in der
aufklappbaren Befehlsreferenz im Editor; Fehler erscheinen direkt unter dem Code.

## Der FSR-Modus (für die Turnierleitung)

Oben rechts **FSR-Modus** anklicken und anmelden — das Passwort steht in `config.json`
(`fsr_passwort`). Da dieses Repo öffentlich ist, kennt jede*r das voreingestellte
Passwort: Vor einem echten Turnier in `config.json` ein eigenes eintragen. Die Reiter:

| Reiter | Zweck |
|---|---|
| **Roboter** | Alle Abgaben aus `abgaben/` samt Logos und Beschreibung |
| **Einzelmatch** | 2–4 Roboter gegeneinander, mit Wiedergabe und Beamer-Knopf |
| **Gruppenphase** | Vierergruppen über mehrere Runden, rotierende Startecken, Tabelle |
| **K.-o.-Runden** | Ausgeloster Baum mit Spiel um Platz 3; die Show zeigt Baum, dann jede Partie einzeln (VS-Bild, Spiel mit Ladung und Depot an den Seiten, Abrechnung der Ladung, Sieger), am Ende die Siegertreppe — weiter nur auf Klick, wächst mit dem Beamer mit |
| **Turnierarchiv** | Gespeicherte Turniere, wieder anzeigbar und auf der Bühne nachspielbar |
| **Massenauswertung** | Siegquoten-Matrix über viele Seeds (Hintergrundaufgabe) |
| **Einstellungen** | `config.json` prüfen, ändern und dauerhaft speichern |

Die Beamer-Ansicht blendet alles außer dem Spiel aus; im Vollbild passt sich das Feld
an Breite und Höhe an. Teams erscheinen in der Liste, sobald ihre Datei in `abgaben/`
liegt — ein Logo daneben gehört dazu: `abgaben/die_profis.py` und
`abgaben/die_profis.png`.

## Auf der Konsole

```bash
python3 -m engine.match bots/hausmeister.py bots/fleissig.py --seed 1
python3 -m engine.match bots/*.py --seed 4 --zeigen --alle 20
python3 -m engine.match a.py b.py --ticks 80 --aufzeichnung aufzeichnungen/lauf.json
```

`--zeigen` malt das Feld als Text: Ziffern sind Roboter, `p b M E X` die Müllsorten,
`#` Wand, `▓` Innenwand, `_` Depot, `·` Bonuszone. `--alle N` zeichnet nur jeden
N-ten Tick.

```bash
python3 balance.py                          # mitgelieferte Gegner, Seeds aus config.json
python3 balance.py --seeds 30 --json bericht.json
python3 balance.py --ordner abgaben --nur hausmeister
```

`balance.py` gibt am Ende ein Urteil aus („kein Bot dominiert …"). Es ist das
Prüfwerkzeug für die `config.json`: nach jeder Regel- oder Zahlenänderung neu laufen
lassen.

## Tests

```bash
python3 -m tests.run                            # alles, rund 20 s
python3 -m tests.run -v
python3 -m tests.run --golden-neu               # Golden neu aufnehmen (nur bewusst!)
python3 -m tests.run --golden-neu --nur <name>  # nur ein Szenario neu aufnehmen
```

Die Golden Tests in `tests/golden/` halten Endstand **und** Prüfsumme des Verlaufs
fester Szenarien fest. Ändert sich eine Prüfsumme ohne bewusste Regeländerung, ist das
ein Fehler — nicht neu aufnehmen.

## Ordner

| Ordner | Inhalt |
|---|---|
| `abgaben/` | Bot-Dateien der Teams (und deren Logos) |
| `aufzeichnungen/` | gespeicherte Spielverläufe (`--aufzeichnung`) |
| `turnier/` | gespeicherte Turnierergebnisse (FSR-Modus) |
| `bots/` | die fünf mitgelieferten Gegner |
| `tests/golden/` | die eingefrorenen Golden-Szenarien |

## Wenn etwas klemmt

- **Ein laufender Server kennt neuen Python-Code nicht.** Statische Dateien liest er
  bei jeder Anfrage neu, die Python-Module aber nur beim Start. Nach jeder Änderung an
  einer `.py`-Datei `start.py` neu starten.
- **Port belegt:** `start.py` probiert die nächsten 20 Ports durch und druckt die
  gefundene Adresse.
- **Bot fährt nicht los:** Im Testlauf stehen Fehlermeldung und Regelnummer unter dem
  Feld; häufige Ursache ist ein Tippfehler, den die Prüfung beim Tippen schon meldet.
- **Kein Browser öffnet sich:** mit `--kein-browser` starten und die gedruckte Adresse
  von Hand aufrufen. Geprüft ist Chromium; Firefox und Safari nutzen dieselben
  Standardfunktionen.

## Dokumente

- `ANLEITUNG.md` — Kurzanleitung für die Teams
- `SPEC.md` — die Spielregeln, maßgeblich

## Lizenz

MIT-Lizenz, siehe `LICENSE`. Du darfst den Code frei verwenden, verändern und
weitergeben, solange der Copyright-Hinweis erhalten bleibt.
