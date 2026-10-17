# SPEC — Maßgebliche Spielregeln

Diese Datei ist die verbindliche Fassung der Spielregeln. Bei Widersprüchen zwischen Code
und SPEC gewinnt die SPEC — oder die SPEC wird bewusst geändert und der Code angepasst.
Alle Zahlenwerte stehen in `config.json`; hier stehen die Regeln, nicht die Zahlen.
Die in Klammern genannten Startwerte sind nur zur Orientierung.

---

## 1. Spielfeld

- Gitter `breite` × `hoehe` (24×24), Koordinaten `(x, y)`, `x` nach rechts, `y` nach unten.
- Der äußerste Ring ist Wand: `x = 0`, `x = breite-1`, `y = 0`, `y = hoehe-1`.
  Bespielbar ist damit das Innere von `(1,1)` bis `(breite-2, hoehe-2)`.
- Dazu kommen **Innenwände** je nach Karte (siehe unten). Sie blockieren Bewegung und
  Schub genau wie der äußere Ring; niemand kann darauf fahren, und es liegt nie Müll
  darauf.

### Symmetrie

Alles, was zufällig platziert wird, wird symmetrisch platziert. Damit kann kein Spieler
per Zufall bevorzugt werden.

- **2 Spieler (Duell):** Punktspiegelung am Mittelpunkt, `(x, y) → (breite-1-x, hoehe-1-y)`.
  Jede Platzierung erzeugt eine Bahn (Orbit) von 2 Feldern.
- **4 Spieler (Gruppe):** Drehung um 90°, `(x, y) → (breite-1-y, x)`.
  Jede Platzierung erzeugt eine Bahn von 4 Feldern.

Fällt eine Bahn auf sich selbst zurück (Feld liegt auf der Symmetrieachse bzw. im Zentrum)
oder ist eines der Felder belegt, wird die ganze Bahn verworfen und eine neue gezogen.

### Depots

Depots liegen `depot_abstand` (2) Felder von der Wand entfernt, also **nicht** im
äußersten Eck. Grund: In der Ecke liefe jeder Rammstoß gegen eine Wand, ein Roboter
auf einem fremden Depot wäre nicht mehr zu verdrängen und könnte die Ablieferung des
Gegners dauerhaft blockieren.

- Duell: `(2,2)` und `(breite-3, hoehe-3)`.
- Gruppe: `(2,2)`, `(breite-3, 2)`, `(breite-3, hoehe-3)`, `(2, hoehe-3)`
  — in dieser Reihenfolge den Robotern 0..3 zugewiesen (Bahn der Drehsymmetrie).
- Jeder Roboter startet auf seinem eigenen Depot.
- Auf einem Depotfeld liegt nie Müll (weder beim Start noch beim Nachschub).

### Innenwände (Karten)

- Die Karten stehen als Liste in `spiel.karten` in der `config.json`; jede Karte hat
  einen Namen und eine Liste von Grundfeldern (`waende`).
- Die Grundfelder liegen im ersten Quadranten; die Welt erzeugt daraus per
  Symmetrie (§1) die tatsächlichen Wände — Punktspiegelung im Duell, 90°-Drehung in
  der Gruppe. Damit ist jede Karte für alle Spieler fair.
- Der **Seed wählt die Karte**: `karten[seed % anzahl]`. Gleicher Seed, gleiche Karte;
  ein Nachspiel mit demselben Seed sieht dieselben Wände.
- Eine Karte ist nur gültig, wenn sie für 2 **und** 4 Spieler aufgeht: keine Wand auf
  einem Depot oder auf einem Feld direkt daneben, und das Feld bleibt in einem Stück
  zusammenhängend. `engine/config.py` prüft das beim Laden.
- Eine Wand auf einem Feld der Bonuszone ist erlaubt; dort kann nur kein Müll liegen.

---

## 2. Ablauf einer Runde

Eine Runde hat `runden_laenge` Ticks (400). Ein Tick läuft in dieser festen Reihenfolge ab:

1. **Bonuszone** aktualisieren (alle `wechsel_alle` Ticks eine neue Position).
2. **Nachschub** einstreuen (alle `nachschub_intervall` Ticks).
3. **Zustand einfrieren** — alle Roboter sehen denselben Stand vom Tickbeginn.
4. **Aktionen einholen** — jeder Bot liefert genau eine Aktion (Reihenfolge: Startreihenfolge).
5. **Aktionen filtern** — Presse, Ladepause und Langsamkeit setzen Aktionen auf `warte`
   (siehe §5a und §6).
6. **Bewegung auflösen** (§7), einschließlich Rammen und Schubsen.
7. **Zwangsaufnahme** für jeden Roboter, der sein Feld gewechselt hat (Startreihenfolge).
8. **Abliefern** für jeden Roboter, der auf seinem eigenen Depot steht (Startreihenfolge).
8a. **Akku leer:** Wer in diesem Tick auf 0 gefallen ist, verliert seine Ladung (§6).
9. **Tick zählen**, Zustand in die Aufzeichnung schreiben.

Nach dem letzten Tick folgt die **Schlussabrechnung** (§9).

---

## 3. Müll

### Sorten

Vier normale Sorten mit aufsteigendem Wert und absteigender Häufigkeit:
`papier` (20), `bio` (36), `metall` (80), `elektro` (160).
Die Häufigkeit beim Nachschub ist ein Gewicht in `config.json` (45 / 30 / 18 / 7).

Dazu **radioaktive Fässer** (`radioaktiv`, Wert −240; den Teams gegenüber heißen sie
immer „radioaktives Fass“, Anzeigename in `radioaktiv.anzeige`):
- `anzahl_pro_spieler` Fässer je Spieler (1) — also 2 im Duell, 4 in der Gruppe.
- Liegen von Beginn an auf festen, symmetrischen Positionen.
- Erscheinen nie nach, auch nicht nachdem sie aufgenommen wurden.
- **Altern nicht.** Ihr Wert ist konstant.
- Bekommen **keinen** Zonenbonus (der Bonus verdoppelt sonst den Schaden).

### Wertverfall

Jedes liegende Müllstück merkt sich den Tick seiner Entstehung. Mit
`alter = jetziger_tick − entsteh_tick`, `T = verfall_ticks` (150) gilt:

```
roh  = basiswert − (basiswert * alter) // T
wert = max(roh, −verfall_strafe_max)
```

- Bei `alter = 0` ist der Wert der Basiswert, bei `alter = T` genau 0.
- Danach sinkt er mit derselben Steigung weiter ins Negative, ist aber bei
  `−verfall_strafe_max` (−40) gedeckelt.
- Ganzzahlige Division; es gibt in der Spiellogik keine Fließkommazahlen.
- Radioaktiver Abfall ist ausgenommen.

### Nachschub

Alle `nachschub_intervall` Ticks (16) werden `nachschub_anzahl` Bahnen (1) eingestreut.
Eine Bahn sind 2 (Duell) bzw. 4 (Gruppe) Felder — es kommen also je Nachschub 2 bzw. 4
Stücke aufs Feld. Die Sorte wird per Gewichtung gezogen und gilt für die ganze Bahn.
Es wird nicht eingestreut, wenn bereits `max_auf_feld` (90) Stücke liegen.
Zum Start liegen `start_anzahl` (20) Stücke auf dem Feld.

Ausgeschlossene Felder: Wände, Depots, Felder mit Müll, Felder mit Robotern.

### Ballen (nur in der Ladung)

- Ein **Ballen** entsteht durch Pressen (§5a). Er ist keine Müllsorte im Sinne des
  Nachschubs: Er liegt nie auf dem Feld, hat keinen Verfall und bekommt keinen
  Zonenbonus.
- Er belegt einen Ladeplatz, kann gestohlen werden und zählt beim Abliefern und am
  Rundenende wie jedes andere Stück mit seinem eingefrorenen Wert.
- Er lässt sich **nicht erneut pressen**.
- Für die Sprache heißt seine Sorte `ballen` (`habe(ballen)`, `anzahl(ballen)`).

### Aufnehmen (Zwangsaufnahme)

- Wer sein Feld wechselt und dort Müll vorfindet, nimmt ihn auf. Kein Ausweichen,
  kein Ablehnen, kein Wegwerfen. Das gilt auch für Roboter, die geschubst wurden.
- Wer stehen bleibt, nimmt nichts auf. Müll erscheint nie unter einem Roboter, deshalb
  kann so kein Stück unaufnehmbar werden.
- **Ladekapazität** `kapazitaet` (6). Jedes Stück belegt einen Platz, unabhängig von der
  Sorte. Ist die Ladung voll, bleibt der Müll liegen; der Roboter fährt normal darüber
  und der Müll altert weiter.
- Der Wert wird **beim Aufnehmen eingefroren** — inklusive Zonenbonus. In der Ladung
  ändert sich nichts mehr.

---

## 4. Bonuszone

- Quadrat der Kantenlänge `groesse` (5), vollständig innerhalb des bespielbaren Bereichs.
- Wechselt alle `wechsel_alle` Ticks (60) die Position, beginnend mit Tick 0.
- Müll, der auf einem Feld **innerhalb** der Zone aufgenommen wird, zählt `faktor`-fach (2).
  Maßgeblich ist die Position des Müllstücks, nicht die des Roboters — beide sind beim
  Aufnehmen dasselbe Feld.
- Der Bonus wird beim Aufnehmen eingefroren. Wandert die Zone weiter, behält bereits
  geladener Müll seinen erhöhten Wert; liegengebliebener Müll hat wieder den normalen.
- Radioaktiver Abfall ist vom Bonus ausgenommen.
- Die Zone ist für alle Roboter jederzeit sichtbar.

---

## 5. Depot und Abliefern

- Punkte zählen erst beim Abliefern im **eigenen** Depot. Fremde Depots sind normale Felder.
- Steht ein Roboter am Ende eines Ticks auf seinem Depot und hat Ladung, wird abgeliefert:
  die eingefrorenen Werte aller Stücke werden aufsummiert (negative voll, positive voll)
  und auf den Punktestand addiert. Die Ladung wird **komplett** geleert.
- **Akku laden:** Wer `k` von `kapazitaet` Plätzen abliefert, erhält
  `gewinn = (k * akku_max) // kapazitaet` Energie, gedeckelt auf `akku_max`.
  Volle Ladung (6 Stück) lädt also vollständig auf.
- **Ladezeit:** `lade_ticks = aufrunden(gewinn / laden_prozent_pro_tick * akku_max / 100)`,
  praktisch: 1 Tick je 10 % Ladung. Während des Ladens ist der Roboter bewegungsunfähig
  (seine Aktionen werden ignoriert) und ganz normal angreifbar — er kann gerammt,
  geschubst und bestohlen werden.
- Wird ein ladender Roboter von seinem Depot geschubst, läuft die Ladung trotzdem weiter
  ab; er ist bis zum Ende der Ladezeit bewegungsunfähig.
- Der Energiegewinn wird **sofort** beim Abliefern gutgeschrieben, nicht erst am Ende
  der Ladezeit.

---

## 5a. Die Presse

- Aktion `presse`. Sie presst `anzahl` (3) gleiche, nicht bereits gepresste Teile aus
  der eigenen Ladung zu **einem** Ballen.
- Voraussetzung: Es gibt eine Sorte, von der mindestens `anzahl` unpresste Teile mit
  **positivem Wert** an Bord sind. Abgewertete oder negative Teile lassen sich nicht
  pressen und zählen nicht mit. Sonst tut die Aktion nichts (der Roboter wartet).
- **Welche Sorte?** Die mit den meisten Teilen; bei Gleichstand die alphabetisch erste.
  Eine feste Regel, damit derselbe Spielstand immer dieselbe Entscheidung ergibt.
- **Welche Teile?** Die `anzahl` Teile mit dem kleinsten eingefrorenen Wert (bei
  Gleichstand die früher geladenen). Der Verlust ist damit so klein wie möglich.
- **Dauer:** `dauer_ticks` (2) Ticks. Im Tick der Aktion und im folgenden Tick ist der
  Roboter bewegungsunfähig (seine Aktionen werden ignoriert) und ganz normal angreifbar.
- **Wert:** Der Ballen ist `abschlag_prozent` (20) % weniger wert als die Summe der
  drei Teile, ganzzahlig abgerundet: `wert = summe * (100 − abschlag) // 100`.
- **Abbruch:** Wird der Roboter während des Pressens bestohlen und fällt die Zahl der
  pressbaren Teile dieser Sorte dadurch unter `anzahl`, bricht die Presse ab — es sind
  keine drei pressbaren Gleichen mehr. Die Teile bleiben ihm; ein Ballen entsteht
  nicht.
- Weggeschubst werden bricht die Presse **nicht** ab; die Zeit läuft ab (dasselbe
  Muster wie die Ladezeit in §5).
- Radioaktiver Abfall lässt sich nicht pressen. Ein Ballen lässt sich nicht erneut
  pressen.
- Am Rundenende zählt ein noch nicht fertig gepresster Satz Teile wie normale Ladung;
  ein fertiger Ballen wie jedes andere positive Stück (§10).

---

## 6. Akku

- Startwert `akku.start` (100), Höchstwert `akku.max` (100), Untergrenze 0.
- Eine **ausgeführte Bewegung** kostet `kosten_bewegung` (1). `warte`, blockierte und
  ignorierte Aktionen kosten nichts. Geschubst werden kostet nichts.
- **Rammen** kostet beide Beteiligten `kosten_rammen` (5) zusätzlich zur Bewegung des
  Angreifers.
- Der Akku sinkt nie unter 0. Bewegungen bleiben auch bei 0 möglich.
- **Langsam:** Ist der Akku beim Filtern (Schritt 5) kleiner als `langsam_ab` (30), wird
  die Aktion in jedem Tick auf `warte` gesetzt, dessen Nummer modulo `langsam_modulo` (2)
  den Rest `langsam_rest` (1) ergibt — mit den Startwerten also in jedem Tick mit
  **ungerader** Ticknummer. Der Roboter gibt weiterhin Aktionen zurück, sie werden nur
  ignoriert.
- **Akku auf 0 heißt Ladung weg** (`akku.leer_verliert_ladung`, true): Fällt der Akku
  in einem Tick von über 0 auf 0 — durch Bewegung, Rammen oder Gerammtwerden —,
  verschwinden nach dem Abliefern (Schritt 8a) alle Teile der Ladung, auch Ballen.
  **Radioaktive Fässer bleiben.** Wer im selben Tick sein Depot erreicht, liefert vorher
  ab und lädt; dann ist der Akku nicht mehr 0. Das Ereignis `akku_leer` nennt die
  verlorenen Teile, `statistik.verloren` zählt sie.
- Die Regel greift **nur beim Fallen auf 0**, nicht in jedem Tick mit leerem Akku.
  Abliefern lädt nach der Zahl der Teile; ein Roboter, der bei 0 nichts behalten
  dürfte, käme nie wieder hoch.
- **Ein leerer Akku bedeutet nie das Aus.** Kein Ausscheiden, keine Todesspirale: Der
  Roboter fährt langsam weiter, sammelt neu und lädt beim nächsten Abliefern.

---

## 7. Bewegungsauflösung

Aktionen sind `oben` (y−1), `unten` (y+1), `links` (x−1), `rechts` (x+1), `warte`.
Alles andere (unbekannte Zeichenkette, Absturz, Zeitüberschreitung) gilt als `warte`.

Die Auflösung ist vollständig deterministisch und läuft in dieser Reihenfolge:

**A — Wunschfelder.** Für jeden Roboter das Zielfeld bestimmen. `warte` und Wand
(außen oder innen) ⇒ Wunsch ist das eigene Feld (bleibt stehen).

**B — Platztausch.** Wollen zwei Roboter A und B genau die Felder des jeweils anderen,
gilt das als **Rammen für beide**: Keiner bewegt sich, beide klauen (§8), beide zahlen
`kosten_rammen`. Kein Schubsen, weil beide gleichzeitig in die Gegenrichtung drücken.

**C — Umstrittene Felder.** Wollen zwei oder mehr Roboter (die nicht schon in B gebunden
sind) auf dasselbe Feld, bleiben **alle** stehen. Das gilt auch, wenn das Feld von einem
Roboter besetzt ist — mehrere Angreifer blockieren sich gegenseitig, es wird nicht
gerammt. Damit kann jeder Roboter höchstens von einem Angreifer gerammt werden.

**D — Nachrücken.** Wiederholt, bis sich nichts mehr ändert: Ein Roboter mit freiem oder
frei werdendem Zielfeld bewegt sich dorthin. Damit gilt: *A fährt auf B, während B
wegfährt ⇒ A rückt nach, kein Rammen.*

**E — Zyklen und Warteschlangen.** Bleiben nach D Roboter übrig, die in einem Ring
aufeinander warten (A→B→C→D→A), bleiben alle stehen. Es wird nicht gerammt. (Der
Zweierring ist der Platztausch aus B und dort schon erledigt; Ringe aus genau drei
Robotern sind auf einem Gitter mit orthogonalen Zügen geometrisch unmöglich.)

Ebenso bleibt stehen, wer **hinter einem rammenden Roboter** wartet: das Rammen wird
nicht weitergereicht. Die Einordnung „rammt" oder „bleibt stehen" wird für alle
verbliebenen Roboter gleichzeitig anhand desselben Zwischenstands getroffen — sonst
würde die Reihenfolge der Prüfung entscheiden, wer rammen darf.

**F — Rammen.** Übrig bleiben Roboter, deren Zielfeld von einem stehenbleibenden Roboter
besetzt ist. In Startreihenfolge:

1. **Schubsen:** Der Getroffene wird ein Feld in Fahrtrichtung des Angreifers verschoben.
   - Ist dieses Feld frei, rückt der Getroffene dorthin und der Angreifer auf dessen
     altes Feld. Landet der Getroffene auf Müll, greift die Zwangsaufnahme.
   - Ist dort eine Wand (außen oder innen) oder ein anderer Roboter, bleiben **beide**
     stehen. **Es gibt keinen Kettenschub** — die Verschiebung endet am ersten
     Hindernis.
2. **Klauen:** Der Angreifer nimmt **genau ein zufällig gezogenes** Stück aus der Ladung
   des Getroffenen, mit dessen eingefrorenem Wert. Ist die Ladung des Angreifers voll
   oder die des Getroffenen leer, entfällt das Klauen.
3. **Energie:** Beide verlieren `kosten_rammen`; der Angreifer zusätzlich
   `kosten_bewegung`, falls er sich bewegt hat.

Punkt 1 und 2 sind unabhängig: **Auch ein blockierter Schub ist ein vollwertiger
Rammangriff** — es wird geklaut und Energie kostet es auch. Sonst wäre Rammen an der
Wand wirkungslos.

---

## 8. Die Falle (muss funktionieren)

Wer rammt, zieht **zufällig** ein Stück aus der gegnerischen Ladung — er kann sich den
Elektroschrott nicht heraussuchen. Zusammen mit §9 (Sicht: nur die *Anzahl* geladener
Teile ist sichtbar, nicht die Sorten) ergibt das die Bluff-Strategie: Ein Bot nimmt
absichtlich ein Fass auf, fährt provozierend nah heran, und der Angreifer erwischt mit
Wahrscheinlichkeit `1/ladung` das Fass.

Diese Strategie ist ausdrücklicher Bestandteil des Spiels. **Bei jeder Regeländerung ist
zu prüfen, ob sie noch trägt** (Test: `tests/test_falle.py`).

---

## 9. Sicht

Was ein Bot **immer** sieht:
- Die eigene Position, den eigenen Akku, die eigene Ladung (mit Sorten und eingefrorenen
  Werten), den eigenen Punktestand, die eigene Ladezeit.
- Das eigene Depot, die Feldgröße, die Wände — außen **und** innen (die ganze Karte).
- **Allen** liegenden Müll mit Position, Sorte und aktuellem Wert.
- Die Bonuszone.
- Ticknummer und Rundenlänge.

Was ein Bot **nur eingeschränkt** sieht:
- Gegner nur, wenn `manhattan_abstand <= sicht_radius` (6).
- Von einem sichtbaren Gegner: Position und **Anzahl** der geladenen Teile.
  **Nicht** die Sorten, nicht die Werte, nicht den Akku, nicht die Punkte.

Fremde Depots sind aus der Feldgröße ableitbar und werden mitgeliefert.

---

## 10. Rundenende und Wertung

- Nach dem letzten Tick wird die verbleibende Ladung jedes Roboters automatisch gebucht.
- **Dabei zählen negative Werte voll, positive nur geteilt durch `positiv_teiler` (2),
  abgerundet.** Formel je Stück: `wert if wert < 0 else wert // positiv_teiler`.
- Die Buchung steht Posten für Posten im Ergebnis (`roboter[].abrechnung` mit
  `punkte_vorher` und `posten`: Sorte, Wert, Punkte), damit die Show sie vorspielen kann.
  Das Ereignis `abliefern` nennt ebenso die abgelieferten `teile` (Sorte, Wert).
- Sieger ist, wer mehr Punkte hat.
- **Gleichstand** wird in dieser Reihenfolge aufgelöst:
  1. höherer Restakku,
  2. mehr abgelieferte Stücke insgesamt,
  3. sonst Unentschieden. Im K.-o.-System wird bei Unentschieden mit dem nächsten Seed
     wiederholt.

---

## 10a. Was die mitgelieferte Wegfindung zusichert

`fahre_zu` und `abstand_zu` sind keine Spielregeln, sondern Hilfen, die das System den
Bots stellt (`engine/zustand.py`). Ihr Verhalten beeinflusst das Spiel aber so stark,
dass es hier festgehalten gehört.

- **Eine Breitensuche je Tick**, gemerkt für alle Abfragen. Hindernisse sind Wände und
  sichtbare Gegner; ein Ziel wird auch dann angenommen, wenn ein Gegner darauf steht.
- **Feste Auflösung bei Gleichstand:** unter gleich weit entfernten Zielen gewinnt das
  mit der kleineren `(y, x)`-Koordinate; unter gleichwertigen Richtungen die Reihenfolge
  `oben, unten, links, rechts`.
- **`naechster_muell` steuert nur Müll an, der noch einen Wert über 0 hat.** Ohne diese
  Zusicherung führte die Regel `fahre_zu naechster_muell` den Roboter zielstrebig auf
  verrotteten Müll, und die Regelsprache hätte kein Mittel dagegen. Ausnahme ist
  `naechster_muell(radioaktiv)`: das Fass will man gerade wegen seines negativen Werts.
  Über den Müll, den man beim Vorbeifahren aufsammelt, sagt das nichts — die
  Zwangsaufnahme greift unverändert. **`muell_in_zone` zählt dieselben Stücke** wie
  `naechster_muell(in_zone)`: nur Müll mit Wert über 0, keine radioaktiven Fässer.
- **`fahre_zu` umfährt keine radioaktiven Fässer.** Liegt eins auf dem kürzesten Weg,
  fährt der Roboter darüber und muss es aufnehmen. Ausweichen ist Sache der Teams:
- **`richtung_zu <ziel>`** liefert den nächsten Schritt, den `fahre_zu <ziel>` gehen
  würde (`oben`/`unten`/`links`/`rechts`) — aus derselben Wegsuche, samt Ausweichen
  nach einem Standstreit —, `hier`, wenn der Roboter schon auf dem Ziel steht, und
  `keine`, wenn es kein Ziel, keinen Weg oder nur ein Warten gibt. Für `gegner` ohne das
  zufällige Innehalten von `ramme gegner`: Eine Frage verbraucht keinen Zufall.
- **`objekt_in_richtung(<richtung>)`** liefert, was auf dem Nachbarfeld liegt, in dieser
  Rangfolge: `wand` (auch Innenwand), `gegner` (sichtbar), die Müllsorte
  (`papier` … `radioaktiv`), `depot` (das eigene), sonst `frei`. Ein fremdes Depot ist
  befahrbar und zählt als `frei`. Ohne gültige Richtung (`hier`, `keine`) ist die Antwort
  `frei`. Beide Fragen lassen sich nur mit `==` und `!=` vergleichen.
- **`ramme gegner` hält bei geradem Abstand gelegentlich inne.** Ziehen beide Roboter in
  jedem Tick, bleibt die Parität ihres Abstands unverändert; aus einem geraden Abstand
  könnte damit nie ein Treffer werden, und zwei aufeinander zufahrende Roboter blockierten
  sich nach §7 C dauerhaft dasselbe Zwischenfeld. Das Innehalten läuft über den
  rundeneigenen Zufall (§12) und ist damit reproduzierbar.
- **Nach einem Standstreit weicht `fahre_zu` deterministisch aus.** Ist der eigene Wunsch
  im letzten Zug an einem umstrittenen Feld oder einem Ring/einer Warteschlange
  gescheitert (§7 C/E), liefert die Sicht `blockiert: True`. Die nächste Wegfindung wählt
  dann statt der angestammten Richtung die erste begehbare Nebenrichtung — feste
  Richtungsreihenfolge, um `saat % 4` gedreht, ohne den Zufallsgenerator zu verbrauchen.
  Ohne das konnten zwei Roboter, die dieselbe Hilfsfunktion nutzen, dauerhaft vor
  demselben freien Zwischenfeld hängen. `ramme gegner` weicht nicht aus: dort ist das
  Zufahren gewollt, es gilt die Paritäts-Pause.
- **`weg_von gegner`** vergrößert den Manhattan-Abstand; bei Gleichstand gewinnt die
  Richtung, die auch in der Luftlinie am weitesten wegführt.

## 11. Bots

- Jeder Bot läuft in einem **eigenen Prozess**. Zeitlimit je Zug `zeitlimit_ms` (100),
  beim Start `start_zeitlimit_ms` (3000).
- Wer überzieht, dessen Aktion für diesen Tick ist `warte`. Verspätete Antworten werden
  verworfen.
- Nach `kill_nach_ueberzogen` (20) aufeinanderfolgenden Überziehungen oder nach einem
  Absturz wird der Prozess beendet und neu gestartet, höchstens `neustarts_max` (3) mal.
  Danach spielt der Roboter den Rest der Runde `warte`.
- **Ein Moduswechsel kostet keinen Zug.** Nach `GOTO` werden sofort die Regeln des
  neuen Modus geprüft, höchstens `sprache.max_wechsel` (8) mal je Tick; danach `warte`.
  **`GOTO` in den Modus, in dem der Roboter schon ist, tut nichts**: Die Regel wird
  übersprungen, und es geht mit der nächsten weiter. Das betrifft vor allem Regeln vor
  dem ersten `STATE` — sie gelten in jedem Modus, also auch in dem, in den sie führen.
- **Folgen.** Innerhalb eines `STATE` darf eine Regel mehrere Aktionen haben, mit Komma
  getrennt (`IF x THEN fahre links, oben, oben, GOTO sammeln`; vor einer Richtung darf
  `fahre` fehlen). Der Parser macht daraus je Schritt einen versteckten Modus
  `folge_z<zeile>_schritt<n>`; jeder Schritt kostet einen Tick, danach geht es im Modus
  hinter dem `GOTO` weiter, ohne `GOTO` im Modus der Regel. `GOTO` nur am Ende, Folgen
  vor dem ersten `STATE` sind ein Fehler. Während einer Folge gilt der Roboter als im
  Modus der Regel: Ein `GOTO` dorthin aus den Regeln vor dem ersten `STATE` tut nichts
  (`_grundmodus` im erzeugten Code), jedes andere `GOTO` bricht die Folge ab.
- **Ein Neustart löscht das Gedächtnis des Bots.** Ein Roboter mit Modi
  (`STATE`/`GOTO`) beginnt danach wieder im Startmodus. Das ist hinnehmbar — die Regeln
  führen ihn in wenigen Ticks zurück —, aber es ist der Grund, warum kein Spielstand
  im Bot gehalten werden darf, der über die Runde entscheidet.
- Ausgaben des Bots auf die Konsole (`print`) stören das Protokoll nicht; sie werden
  eingesammelt und in der Werkstatt angezeigt.
- Abstürze, unsinnige Rückgabewerte und Endlosschleifen beenden weder Runde noch Turnier.

## 12. Determinismus

- Eigener Zufallsgenerator (`engine/rng.py`, xorshift64*), fester Seed. **Nicht** `random`.
- Der Seed steht in jeder Aufzeichnung.
- Feste Reihenfolge überall: Bots in Startreihenfolge, Mengen vor dem Iterieren sortiert.
- Nur Ganzzahlen in der Spiellogik.
- Ein Zufallsgenerator je Runde, in dieser festen Verbrauchsreihenfolge: Startbelegung,
  dann je Tick Zone → Nachschub → Klauen.
- Gleicher Seed + gleiche Bots ⇒ identischer Spielverlauf. Abgesichert durch
  `tests/golden/`.
