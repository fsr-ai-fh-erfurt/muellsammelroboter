# Müllsammel-Roboter — Anleitung für die Teams

Ihr baut einen Roboter, der Müll einsammelt. Ihr schreibt keinen Python-Code, sondern
**Regeln**. Am Ende kämpft euer Roboter im Turnier gegen die der anderen Teams.

---

## 1. Loslegen

```
python3 start.py
```

Der Browser geht von selbst auf. Falls nicht: `http://127.0.0.1:8000/` eintippen.

1. Oben im Kasten euren **Teamnamen** eintragen.
2. Links steht schon ein Beispiel. Drückt **▶ Testlauf** und schaut zu.
3. Ändert eine Regel und drückt wieder Testlauf.
4. Wenn ihr zufrieden seid: **Abgeben**. Die heruntergeladene `.py`-Datei ist eure Abgabe.

Wer beim Turnier ein **Logo** zeigen will, gibt eine quadratische Bilddatei mit
demselben Namen wie die Abgabedatei mit ab — aus `die_muell_profis.py` wird
`die_muell_profis.png` (auch `.jpg`, `.jpeg`, `.webp` oder `.gif`). Ohne Logo
erscheint beim Turnier ein Kästchen mit dem Anfangsbuchstaben eures Teamnamens.

Tastenkürzel: `Strg`+`Enter` startet den Testlauf.

---

## 2. Wie euer Roboter denkt

In jedem Zug wird euer Roboter genau einmal gefragt: **Was tust du jetzt?**

Eure Regeln werden dabei **von oben nach unten** geprüft. Die **erste** Regel, die
zutrifft, bestimmt die Aktion. Alle weiteren werden nicht mehr angeschaut.

```
IF ladung_ist_voll THEN fahre_zu depot
IF akku < 30 THEN fahre_zu depot
ELSE fahre_zu naechster_muell
```

Das heißt: *Wenn ich voll bin, fahre ich heim. Sonst, wenn mein Akku fast leer ist,
fahre ich auch heim. Sonst hole ich den nächsten Müll.*

Die Reihenfolge ist also entscheidend. Steht `ELSE fahre_zu naechster_muell` ganz oben,
kommt euer Roboter nie mehr nach Hause.

Statt lauter einzelner `IF`-Zeilen dürft ihr auch `ELSE IF` schreiben — das ist
dasselbe, liest sich aber wie eine Kette:

```
IF ladung_ist_voll THEN fahre_zu depot
ELSE IF akku < 30 THEN fahre_zu depot
ELSE fahre_zu naechster_muell
```

Groß- und Kleinschreibung ist egal, Leerzeichen sind egal, Umlaute sind egal, und
`THEN` dürft ihr weglassen. Alles hinter `#` ist ein Kommentar.

Die Schlüsselwörter sind englisch (`IF`, `THEN`, `ELSE`, `AND`, `STATE`), die Begriffe
aus dem Spiel deutsch (`ladung`, `akku`, `naechster_muell`). Genauso sieht der Code aus,
den ihr im Studium schreiben werdet.

---

## 3. Der Spickzettel

**Aktionen — was der Roboter tut**

| | |
|---|---|
| `fahre_zu <ziel>` | Ein Schritt Richtung Ziel. Den Weg sucht das Spiel für euch. |
| `fahre <richtung>` | Ein Schritt nach `oben`, `unten`, `links` oder `rechts`. |
| `ramme gegner` | Auf den nächsten sichtbaren Gegner zu. Beim Auftreffen wird geschubst und ein **zufälliges** Teil geklaut. |
| `warte` | Diesen Zug nichts tun. Spart Energie. |
| `presse` | Gleiche Teile zu einem **Ballen** pressen: dauert 2 Züge, in denen ihr euch nicht bewegen könnt. Der Ballen ist 20 % weniger wert als die Teile zusammen, belegt aber nur einen Platz. Nur, wenn ihr genug gleiche Teile habt (`kann_pressen`); abgewertete Teile (Wert 0 oder darunter) zählen nicht mit. |
| `GOTO <modus>` | Wechselt den Modus — ohne einen Zug zu verbrauchen (siehe §5). |

**Ziele — wohin**

| | |
|---|---|
| `depot` | Euer eigenes Depot. Nur dort zählen Punkte. |
| `naechster_muell` | Das nächstgelegene Stück, das noch etwas wert ist. |
| `naechster_muell(metall)` | Nur diese Sorte: `papier`, `bio`, `metall`, `elektro`, `radioaktiv`. |
| `naechster_muell(in_zone)` | Nur Müll in der Bonuszone. Zusammen geht auch: `naechster_muell(metall, in_zone)`. |
| `BEST muell BY <rechnung>` | Rechnet für **jedes** Stück und fährt zum besten (siehe §4). |
| `gegner` | Der nächste sichtbare Gegner. |
| `weg_von gegner` | Einen Schritt vom Gegner weg. |
| `zone` | In die Bonuszone hinein. |
| `feld(12, 8)` | Ein bestimmtes Feld. |

**Bedingungen — wann**

| | |
|---|---|
| `ladung` | Wie viele Teile geladen sind (0 bis 6). |
| `ladung_ist_voll` / `ladung_ist_leer` | Alle Plätze belegt bzw. alle frei. |
| `freie_plaetze` | Wie viele Plätze noch frei sind. |
| `ladung_wert` | Was eure Ladung zusammen wert ist. |
| `anzahl(metall)` | Wie viele Teile dieser Sorte ihr geladen habt. |
| `habe(elektro)` | Habt ihr ein Teil dieser Sorte geladen? |
| `anzahl(ballen)` / `habe(ballen)` | Ballen zählen wie eine Sorte — sie entstehen beim Pressen und liegen nie auf dem Feld. |
| `akku` | Der Akkustand (0 bis 100). |
| `gegner_sichtbar` | Ist ein Gegner in Sichtweite? |
| `gegner_ladung` | Wie viele Teile der nächste sichtbare Gegner trägt. **Welche Sorten, seht ihr nicht.** |
| `abstand_zu <ziel>` | Weglänge zum Ziel, z.B. `abstand_zu depot < 5`. |
| `tick` | Der wievielte Zug gerade läuft (Standard: 400, die Turnierleitung kann es einstellen). |
| `restliche_ticks` | Wie viele Züge die Runde noch hat. |
| `punkte` | Euer Punktestand. |
| `bin_in_zone` | Steht ihr in der Bonuszone? |
| `muell_in_zone` | Liegt Müll in der Bonuszone, der noch etwas wert ist? |
| `kann_pressen` | Habt ihr genug gleiche Teile mit positivem Wert für einen Ballen? |
| `RANDOM(30)` | Trifft in 30 % der Züge zu — für Roboter, die nicht ausrechenbar sein sollen. |

Verknüpfen mit `AND`, `OR`, `NOT` und Klammern.
Vergleichen mit `<`, `>`, `==`, `!=`, `>=`, `<=`.

> Ein einzelnes `=` ist **kein** Vergleich. Vergleichen heißt `==`, mit zwei
> Gleichheitszeichen. Ein `=` gibt es nur bei `LET`. Diesen Unterschied gibt es in fast
> jeder Programmiersprache, und er kostet jeden einmal eine Viertelstunde.

---

## 4. Rechnen

Auf **beiden** Seiten eines Vergleichs darf gerechnet werden, mit `+ - * / %` und
Klammern. Geteilt wird ganzzahlig (`7 / 2` ist `3`).

```
IF akku < abstand_zu depot * 2 + 10 THEN fahre_zu depot
```

*Wenn mein Akku knapper ist, als ich für den doppelten Heimweg brauche, fahre ich heim.*

**`LET` gibt einer Zahl einen Namen.** Dann dreht ihr an *einer* Stelle statt an fünf:

```
LET heimkehr = 25

IF restliche_ticks < heimkehr THEN fahre_zu depot
```

`RANDOM(...)` und `feld(...)` brauchen aber **feste Zahlen** — eine `LET`-Konstante
wird dort nicht angenommen. `LET` gilt nur für Vergleiche und Rechnungen.

**Das beste Stück auswählen.** `BEST muell BY` rechnet eure Formel für jedes Müllstück
aus und fährt zu dem mit dem höchsten Ergebnis. In der Formel dürft ihr benutzen:

- `wert` — was das Stück gerade wert ist
- `abstand` — die Weglänge dorthin
- `bonus` — 2 in der Bonuszone, sonst 1

```
ELSE fahre_zu BEST muell BY wert * bonus - 3 * abstand
```

Die `3` sagt, was euch ein Schritt Umweg wert ist. Für Elektroschrott (160) fahrt ihr
damit weit, für Papier (20) nur um die Ecke. **Dreht an dieser Zahl** — das ist eine der
wichtigsten Stellschrauben, die ihr habt.

---

## 5. Modi: ein Roboter mit Zuständen

Eine Regelliste kann nichts *zu Ende* tun. Sie entscheidet in jedem Zug neu und hat kein
Gedächtnis. Mit `STATE` gebt ihr eurem Roboter **Zustände**, mit `GOTO` wechselt er
zwischen ihnen.

```
STATE sammeln
  IF ladung_ist_voll THEN GOTO heimweg
  ELSE fahre_zu BEST muell BY wert * bonus - 3 * abstand

STATE heimweg
  IF ladung_ist_leer THEN GOTO sammeln
  IF gegner_sichtbar THEN fahre_zu weg_von gegner
  ELSE fahre_zu depot
```

- Der **erste** `STATE` ist der Startmodus.
- `GOTO` kostet **keinen Zug**. Der Roboter prüft sofort die Regeln des neuen Modus und
  handelt noch im selben Zug.
- Unter dem Spielfeld steht bei jedem Zug, in welchem Modus euer Roboter gerade ist.
- Regeln **vor** dem ersten `STATE` gelten in *jedem* Modus. Gut für Notfälle:
  `IF akku < 5 THEN GOTO notfall`.
- `GOTO` in den Modus, in dem ihr **schon seid**, tut nichts — die Regel wird
  übersprungen, es geht mit der nächsten weiter. Ihr könnt eine Notfallregel also
  oben stehen lassen, ohne dass sie euch im Notfallmodus den Zug wegnimmt.
- **Vorsicht:** Wenn zwei Modi sich gegenseitig aufrufen, dreht sich euer Roboter im
  Kreis. Er merkt das und wartet — aber der Zug ist verloren.

Das ist ein *endlicher Automat*, und ihr baut damit genau das, was in einem echten
Roboter steckt. Fangt mit zwei Modi an. Drei sind schon anspruchsvoll: Womit fängt der
Modus an, und was bringt euch wieder heraus?

### Folgen: mehrere Züge in einer Regel

Innerhalb eines `STATE` darf eine Regel mehrere Aktionen hintereinander haben, mit
Komma getrennt. Jede Aktion ist ein eigener Zug. Alles, was geht, in einer Zeile:

```
LET umweg = 3

STATE start
  IF abstand_zu depot == 0 THEN fahre rechts, rechts, warte, fahre_zu BEST muell BY wert * bonus - umweg * abstand, GOTO sammeln

STATE sammeln
  IF ladung_ist_voll THEN fahre_zu depot
  ELSE fahre_zu BEST muell BY wert * bonus - umweg * abstand
```

- Vor einer Richtung darf `fahre` fehlen: `fahre rechts, rechts` ist dasselbe wie
  zweimal `fahre rechts`.
- Jede Aktion geht als Schritt — `warte`, `presse`, `ramme gegner`, `fahre_zu …`.
  `fahre_zu` ist auch in einer Folge nur **ein** Schritt Richtung Ziel.
- `GOTO` steht, wenn überhaupt, **ganz am Ende**. Ohne `GOTO` ist der Roboter danach
  wieder im Modus der Regel; stimmt die Bedingung dann noch, beginnt die Folge von vorn.
- Mit `BEST muell BY …` gehört die **ganze Formel** in den Schritt — ein „das beste
  Stück von vorhin“ gibt es nicht. Braucht ihr dieselbe Formel öfter, haltet die Zahlen
  mit `LET` an einer Stelle (oben `umweg`).
- **Eine Folge schaut nicht hin.** Solange sie läuft, prüft der Roboter die Regeln seines
  Modus nicht. Ist ein Weg versperrt, bleibt er stehen und macht trotzdem mit dem
  nächsten Schritt weiter. Die Regeln **vor** dem ersten `STATE` werden aber in jedem Zug
  zuerst geprüft; springt eine davon in einen anderen Modus, ist die Folge abgebrochen.
- Vor dem ersten `STATE` gibt es keine Folgen. Was eine Folge genau tut, steht in der
  Werkstatt unter dem Editor, sobald ihr sie schreibt.

---

## 6. Was eine Regel kostet

Unter dem Spielfeld steht bei jedem Zug, was die gerade greifende Regel kostet — und in
eurer Abgabedatei steht es als Kommentar über jeder Regel:

```python
# Regel 3: ELSE fahre_zu depot
# Kosten:   1 Zug und 1 Akku je Schritt. Wie viele Schritte es werden, hängt vom Weg
#           ab — abstand_zu depot sagt es dir.
```

Wichtig ist der zweite Satz: **`fahre_zu` kostet nicht einen Zug, sondern einen je
Schritt.** Ein Ziel am anderen Ende des Feldes kostet 30 Züge und 30 Akku. Deshalb lohnt
sich ein weiter Umweg nur für teuren Müll — und deshalb gibt es `BEST muell BY`.

---

## 7. Die Spielregeln in Kürze

- **Zwangsaufnahme.** Wer auf ein Feld mit Müll fährt, nimmt ihn auf. Immer.
  Wegwerfen geht nicht. Ladeplätze: 6.
- **Wertverfall.** Liegender Müll verliert langsam an Wert und wird irgendwann negativ.
  In eurer Ladung altert nichts mehr — der Wert wird beim Aufnehmen eingefroren.
- **Bonuszone.** Müll, den ihr **in** der Zone aufnehmt, zählt doppelt, und zwar für
  immer. Die Zone wandert alle 60 Züge weiter.
- **Presse.** Drei gleiche Teile werden zu einem **Ballen**: zwei Züge Arbeit, 20 %
  Wertverlust — dafür belegt er nur einen Platz. Radioaktive Fässer und abgewertete Teile (Wert 0
  oder darunter) lassen sich nicht pressen. Werdet ihr beim Pressen bestohlen und sind
  es keine drei Gleichen mehr, bricht sie ab.
- **Karte.** Jede Runde hat **Innenwände**. Sie sind symmetrisch und stehen fest; der
  Seed entscheidet, welchen Plan ihr bekommt. Gleicher Seed, gleiche Karte.
- **Depot.** Punkte zählen erst beim Abliefern. Dabei lädt der Akku — das dauert
  aber mehrere Züge, in denen ihr euch nicht bewegen könnt und angreifbar seid.
- **Akku.** Jede Bewegung kostet, Rammen kostet mehr. Unter 30 fahrt ihr nur noch
  jeden zweiten Zug. **Fällt der Akku auf 0, ist eure ganze Ladung weg** — nur ein
  radioaktives Fass bleibt euch (doppelt Pech). Danach könnt ihr weitersammeln und
  im Depot wieder aufladen. Vorsicht: Auch Gerammtwerden kostet Akku.
- **Rammen.** Schubst den Gegner und klaut ihm ein **zufälliges** Teil. Kostet beiden
  Energie. Ihr könnt euch nicht aussuchen, was ihr erwischt.
- **Radioaktive Fässer.** Sehr viele Punkte wert — negativ. Sie altern nicht; jedes
  Team bekommt ein radioaktives Fass aufs Feld (zwei im Duell, vier in der
  Vierergruppe). `fahre_zu` fährt einfach drüber, wenn eins im Weg liegt.
- **Rundenende.** Was ihr am Ende noch tragt, zählt nur zur Hälfte. Minuspunkte
  dagegen voll. Fahrt also rechtzeitig heim.
- **Sicht.** Müll, Wände, Zone und euer Depot seht ihr immer. Gegner nur im Umkreis
  von 6 Feldern — und von denen nur, **wie viele** Teile sie tragen, nicht welche.

---

## 8. Drei Ratschläge

1. **Fahrt rechtzeitig heim.** Der häufigste Fehler ist ein Roboter, der fleißig
   sammelt und nie abliefert. Der bekommt am Ende fast nichts. Eine Endspurt-Regel
   im Modus `sammeln`, vor der `ELSE`-Zeile, bringt messbar etwas: Gegen den
   Hausmeister ergab sie in je 60 Spielen 1066 statt 1040 Punkte (mit der
   `BEST`-Zeile aus §4) — rund 27 mehr und eine Partie mehr gewonnen; ohne `BEST`
   sind es 920 statt 889 Punkte.

   ```
   IF restliche_ticks < 50 AND NOT ladung_ist_leer AND abstand_zu depot < restliche_ticks THEN GOTO heimweg
   ```

   Die Regel schickt den Roboter nur heim, wenn der Weg in der Restzeit noch zu
   schaffen ist. Das lohnt sich, weil am Rundenende die Restladung nur halb zählt
   und nach Tick 350 in 15–17 % der Partien noch die Rohpunkte-Führung wechselt
   (in 0–3 % kippt der Sieger erst durch die Schlussbuchung).
2. **Ändert eine Sache und testet.** Der Seed bleibt gleich, also läuft das Spiel
   gleich ab. Nur so seht ihr, ob eure Änderung wirklich besser war. Probiert danach
   ruhig mehrere Seeds — ein Sieg bei Seed 1 ist noch keine Strategie.
3. **Schaut euch an, welche Regel greift.** Unter dem Spielfeld steht bei jedem Zug,
   welche eurer Regeln gerade zieht, in welchem Modus ihr seid und was das kostet; die
   Zeile wird im Editor gelb. Wenn euer Roboter Unsinn macht, seht ihr dort sofort,
   warum. Auf dem Feld steht auf jedem Müllstück, was es gerade wert ist, und ein
   kleiner Pfeil zeigt, wohin euer Roboter im nächsten Zug fährt. Darunter seht ihr
   eure Ladung mit Werten und alles, was schon im Depot liegt.

---

## 9. Die Falle

Ihr seht von einem Gegner nur, **wie viele** Teile er trägt — nicht welche. Und wer
rammt, zieht ein **zufälliges** Teil.

Daraus wird eine Strategie: Nehmt absichtlich ein radioaktives Fass auf und fahrt
provozierend dicht am Gegner entlang. Sieht für ihn aus wie eine fette Beute. Rammt er,
erwischt er vielleicht das radioaktive Fass — und hat den Ärger.

Umgekehrt heißt das: Überlegt euch gut, wen ihr rammt. Ein Roboter, der auffällig
gemütlich vor euch herfährt, will vielleicht genau das.

Mit Modi lässt sich das sauber bauen: ein `STATE koeder`, in den ihr wechselt, sobald
ihr ein radioaktives Fass geladen habt, und der wieder herausführt, wenn niemand anbeißt.

---

## 10. Für Fortgeschrittene

### Richtung und Nachbarfelder

Zwei Fragen liefern statt einer Zahl ein **Wort**. Verglichen wird nur mit `==` und `!=`.

| | |
|---|---|
| `richtung_zu <ziel>` | Wohin `fahre_zu <ziel>` als Nächstes fahren würde: `oben`, `unten`, `links`, `rechts` — oder `hier` (schon da) bzw. `keine` (kein Ziel, kein Weg). |
| `objekt_in_richtung(<richtung>)` | Was auf dem Nachbarfeld liegt: `frei`, `wand`, `gegner`, `depot` oder eine Müllsorte (`papier`, …, `radioaktiv`). Statt einer Richtung geht auch `richtung_zu …`. |

```
IF objekt_in_richtung(richtung_zu depot) == radioaktiv THEN GOTO ausweichen
```

Wie ihr damit einem radioaktiven Fass ausweicht, findet ihr selbst heraus.

### Echtes Python

Zwischen `PYTHON` und `END` dürft ihr echtes Python schreiben. Es landet an genau
dieser Stelle in eurer Abgabedatei. Das Objekt heißt `zustand`, und ihr gebt mit
`return` eine Aktion zurück.

```
IF ladung_ist_voll THEN fahre_zu depot

PYTHON
bestes = None
for stueck in zustand.muell_auswahl(nur_positiv=True):
    weg = zustand.abstand_zu_feld(stueck["x"], stueck["y"])
    if bestes is None or stueck["wert"] - weg * 3 > bestes[0]:
        bestes = (stueck["wert"] - weg * 3, stueck)
if bestes:
    return zustand.fahre_zu_feld(bestes[1]["x"], bestes[1]["y"])
END

ELSE fahre_zu naechster_muell
```

Öffnet ruhig mal eure Abgabedatei in einem Editor — da steht euer Pseudocode als
Kommentar über jeder `if`-Zeile, und darunter, was sie kostet. So sieht der Code aus,
den ihr gerade geschrieben habt. Wenn ihr Modi benutzt, findet ihr für jeden Modus eine
eigene Methode `_modus_<name>`; ein `PYTHON`-Block landet in dem Modus, in dem er steht.

---

## 11. Wenn etwas klemmt

- **Rote Meldung im Editor:** Klickt sie an, dann springt der Cursor in die Zeile.
  Bei Tippfehlern schlägt das Programm meist den richtigen Befehl vor.
- **„`WENN` heißt jetzt `IF`":** Ihr habt eine ältere Anleitung erwischt. Die
  Schlüsselwörter sind jetzt englisch. Die alten Wörter `WENN`, `DANN`, `SONST`,
  `UND`, `ODER`, `NICHT` und `ENDE` erkennt der Editor noch und sagt euch, wie es
  jetzt heißt.
- **„Dein Roboter hat Züge über dem Zeitlimit gebraucht":** In eurem `PYTHON`-Block
  läuft vermutlich eine Endlosschleife. Der Roboter setzt dann Züge aus, das Spiel
  läuft aber weiter.
- **Der Roboter fährt im Kreis:** Wahrscheinlich greift immer dieselbe Regel. Schaut
  auf die Regelanzeige unter dem Spielfeld.
- **Der Roboter hängt in einem Modus fest:** Schaut, welche Regel den Modus wieder
  verlässt — und ob ihre Bedingung überhaupt jemals zutrifft.
- **Nichts geht mehr:** Fenster schließen, `python3 start.py` neu starten. Euer Stand
  bleibt im Browser gespeichert.
