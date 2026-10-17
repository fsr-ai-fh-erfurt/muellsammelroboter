/* Aufbau der Seite: Werkstatt starten, Referenz füllen, FSR-Modus freischalten. */

const REFERENZ = `
<h3>So funktioniert es</h3>
<p>Dein Roboter bekommt in jedem Zug genau eine Frage: <b>Was tust du jetzt?</b>
Deine Regeln werden dabei von oben nach unten geprüft. Die <b>erste</b> Regel, die
zutrifft, bestimmt die Aktion. Alle weiteren werden nicht mehr angeschaut.</p>
<div class="beispiel">IF ladung_ist_voll THEN fahre_zu depot
IF akku &lt; 30 THEN fahre_zu depot
ELSE fahre_zu naechster_muell</div>
<p>Mehrere Bedingungen hintereinander darfst du auch als Kette schreiben —
<code>ELSE IF</code> bedeutet dasselbe wie ein weiteres <code>IF</code>:</p>
<div class="beispiel">IF ladung_ist_voll THEN fahre_zu depot
ELSE IF akku &lt; 30 THEN fahre_zu depot
ELSE fahre_zu naechster_muell</div>
<p class="klein">Groß- und Kleinschreibung ist egal, Leerzeichen sind egal, Umlaute
sind egal, und <code>THEN</code> darfst du weglassen. Alles hinter <code>#</code> ist
ein Kommentar.</p>

<h3>Aktionen — was der Roboter tut</h3>
<table>
<tr><td><code>fahre_zu &lt;ziel&gt;</code></td><td>Fährt einen Schritt Richtung Ziel. Der Weg
wird für dich gesucht, um Wände und Roboter herum.</td></tr>
<tr><td><code>fahre &lt;richtung&gt;</code></td><td>Ein Schritt nach <code>oben</code>,
<code>unten</code>, <code>links</code> oder <code>rechts</code>.</td></tr>
<tr><td><code>ramme gegner</code></td><td>Fährt auf den nächsten sichtbaren Gegner zu.
Beim Auftreffen wird geschubst und ein <b>zufälliges</b> Teil geklaut.</td></tr>
<tr><td><code>warte</code></td><td>Diesen Zug nichts tun. Spart Energie.</td></tr>
<tr><td><code>presse</code></td><td>Presst gleiche Teile zu einem Ballen: dauert zwei
Züge, in denen du dich nicht bewegen kannst. Siehe unten.</td></tr>
<tr><td><code>GOTO &lt;modus&gt;</code></td><td>Wechselt den Modus — ohne einen Zug zu
verbrauchen. Siehe unten.</td></tr>
</table>
<p class="klein">Was eine Regel kostet, steht unter dem Spielfeld, sobald sie greift —
und als Kommentar in deiner Abgabedatei.</p>

<h3>Ziele — wohin</h3>
<table>
<tr><td><code>depot</code></td><td>Dein eigenes Depot. Nur dort zählen Punkte.</td></tr>
<tr><td><code>naechster_muell</code></td><td>Das nächstgelegene Müllstück, das noch etwas
wert ist. Radioaktive Fässer werden dabei ausgelassen.</td></tr>
<tr><td><code>naechster_muell(metall)</code></td><td>Nur diese Sorte: <code>papier</code>,
<code>bio</code>, <code>metall</code>, <code>elektro</code>, <code>radioaktiv</code>.</td></tr>
<tr><td><code>naechster_muell(in_zone)</code></td><td>Nur Müll in der Bonuszone. Beides geht
auch zusammen: <code>naechster_muell(metall, in_zone)</code>.</td></tr>
<tr><td><code>BEST muell BY &lt;rechnung&gt;</code></td><td>Rechnet für <b>jedes</b> Stück und
fährt zum besten. Siehe unten.</td></tr>
<tr><td><code>gegner</code></td><td>Der nächste sichtbare Gegner.</td></tr>
<tr><td><code>weg_von gegner</code></td><td>Einen Schritt vom Gegner weg.</td></tr>
<tr><td><code>zone</code></td><td>In die Bonuszone hinein.</td></tr>
<tr><td><code>feld(12, 8)</code></td><td>Ein bestimmtes Feld.</td></tr>
</table>

<h3>Bedingungen — wann</h3>
<table>
<tr><td><code>ladung</code></td><td>Wie viele Teile geladen sind (0 bis 6).</td></tr>
<tr><td><code>ladung_ist_voll</code> / <code>ladung_ist_leer</code></td><td>Trifft zu, wenn
alle Plätze belegt bzw. alle frei sind.</td></tr>
<tr><td><code>freie_plaetze</code></td><td>Wie viele Plätze noch frei sind.</td></tr>
<tr><td><code>ladung_wert</code></td><td>Was deine Ladung zusammen wert ist.</td></tr>
<tr><td><code>anzahl(metall)</code></td><td>Wie viele Teile dieser Sorte du geladen hast.</td></tr>
<tr><td><code>habe(elektro)</code></td><td>Hast du ein Teil dieser Sorte geladen?</td></tr>
<tr><td><code>anzahl(ballen)</code> / <code>habe(ballen)</code></td><td>Ballen zählen wie eine
Sorte — sie entstehen beim Pressen und liegen nie auf dem Feld.</td></tr>
<tr><td><code>akku</code></td><td>Der Akkustand (0 bis 100).</td></tr>
<tr><td><code>gegner_sichtbar</code></td><td>Trifft zu, wenn ein Gegner in Sichtweite ist.</td></tr>
<tr><td><code>gegner_ladung</code></td><td>Wie viele Teile der nächste sichtbare Gegner
trägt. Welche Sorten — das siehst du nicht.</td></tr>
<tr><td><code>abstand_zu &lt;ziel&gt;</code></td><td>Weglänge zum Ziel, z.B.
<code>abstand_zu depot &lt; 5</code>.</td></tr>
<tr><td><code>tick</code></td><td>Der wievielte Zug gerade läuft.</td></tr>
<tr><td><code>restliche_ticks</code></td><td>Wie viele Züge die Runde noch hat.</td></tr>
<tr><td><code>punkte</code></td><td>Dein Punktestand.</td></tr>
<tr><td><code>bin_in_zone</code></td><td>Stehst du in der Bonuszone?</td></tr>
<tr><td><code>muell_in_zone</code></td><td>Liegt Müll in der Bonuszone, der noch etwas
wert ist? Radioaktive Fässer zählen nicht.</td></tr>
<tr><td><code>kann_pressen</code></td><td>Trifft zu, wenn du genug gleiche Teile
mit positivem Wert für einen Ballen beisammen hast.</td></tr>
<tr><td><code>RANDOM(30)</code></td><td>Trifft in 30 % der Züge zu — für Roboter, die
nicht ausrechenbar sein wollen.</td></tr>
</table>
<p class="klein">Verknüpfen mit <code>AND</code>, <code>OR</code>, <code>NOT</code> und
Klammern. Vergleichen mit <code>&lt;</code>, <code>&gt;</code>, <code>==</code>,
<code>!=</code>, <code>&gt;=</code>, <code>&lt;=</code>. Ein einzelnes <code>=</code> ist
kein Vergleich — das gibt es nur bei <code>LET</code>.</p>

<h3>Rechnen</h3>
<p>Auf beiden Seiten eines Vergleichs darf gerechnet werden, mit
<code>+ - * / %</code> und Klammern. Geteilt wird ganzzahlig.</p>
<div class="beispiel">IF akku &lt; abstand_zu depot * 2 + 10 THEN fahre_zu depot</div>
<p><code>LET</code> gibt einer Zahl einen Namen. Dann drehst du an <b>einer</b> Stelle,
statt an fünf:</p>
<div class="beispiel">LET heimkehr = 25

IF restliche_ticks &lt; heimkehr THEN fahre_zu depot</div>
<p class="klein"><code>RANDOM(...)</code> und <code>feld(...)</code> brauchen aber
<b>feste Zahlen</b> — eine <code>LET</code>-Konstante wird dort nicht angenommen.
<code>LET</code> gilt nur für Vergleiche und Rechnungen.</p>

<h3>Das beste Stück auswählen</h3>
<p><code>BEST muell BY</code> rechnet deine Formel für jedes Müllstück aus und fährt zu
dem mit dem höchsten Ergebnis. In der Formel darfst du <code>wert</code> (was das Stück
gerade wert ist), <code>abstand</code> (die Weglänge dorthin) und <code>bonus</code>
(2 in der Bonuszone, sonst 1) benutzen.</p>
<div class="beispiel">ELSE fahre_zu BEST muell BY wert * bonus - 3 * abstand</div>
<p class="klein">Die <code>3</code> sagt, was dir ein Schritt Umweg wert ist. Für
Elektroschrott fährst du damit weit, für Papier nur um die Ecke. Dreh an dieser Zahl.</p>

<h3>Die Presse</h3>
<p>Drei gleiche Teile werden zu einem <b>Ballen</b>: Das kostet zwei Züge, in denen
du dich nicht bewegen kannst, und der Ballen ist etwas weniger wert als die drei
Teile zusammen — dafür belegt er nur <b>einen</b> Platz. Das lohnt sich, wenn du
weit vom Depot weg bist und noch weitersammeln willst.</p>
<div class="beispiel">IF kann_pressen AND abstand_zu depot &gt; 6 THEN presse</div>
<p class="klein">Radioaktive Fässer und abgewertete Teile (Wert 0 oder darunter) lassen sich
nicht pressen. Wirst du beim Pressen bestohlen und sind es keine drei Gleichen
mehr, bricht die Presse ab. Wer einen Ballen trägt, ist eine lohnende Beute — er
sieht für den Gegner aus wie ein Teil.</p>

<h3>Modi — ein Roboter mit Zuständen</h3>
<p>Ein Roboter, der immer dieselbe Liste durchgeht, kann nichts <i>zu Ende</i> tun. Mit
<code>STATE</code> gibst du ihm Zustände, mit <code>GOTO</code> wechselt er zwischen
ihnen. Der Wechsel kostet keinen Zug: der Roboter prüft sofort die Regeln des neuen
Modus.</p>
<div class="beispiel">STATE sammeln
  IF ladung_ist_voll THEN GOTO heimweg
  ELSE fahre_zu BEST muell BY wert * bonus - 3 * abstand

STATE heimweg
  IF ladung_ist_leer THEN GOTO sammeln
  IF gegner_sichtbar THEN fahre_zu weg_von gegner
  ELSE fahre_zu depot</div>
<p class="klein">Der erste <code>STATE</code> ist der Startmodus. Unter dem Spielfeld
steht bei jedem Zug, in welchem Modus dein Roboter gerade ist. Regeln <b>vor</b> dem
ersten <code>STATE</code> gelten in jedem Modus — gut für Notfälle; ein
<code>GOTO</code> in den Modus, in dem du schon bist, tut nichts und lässt die nächste
Regel dran. Vorsicht: Wenn zwei <i>verschiedene</i> Modi sich gegenseitig aufrufen,
dreht sich dein Roboter im Kreis und wartet.</p>

<h3>Folgen — mehrere Züge in einer Regel</h3>
<p>Innerhalb eines <code>STATE</code> darf eine Regel mehrere Aktionen hintereinander
haben, mit Komma getrennt. Jede Aktion ist ein eigener Zug. Hier alles, was geht, in
einer Zeile:</p>
<div class="beispiel">LET umweg = 3

STATE start
  IF abstand_zu depot == 0 THEN fahre rechts, rechts, warte, fahre_zu BEST muell BY wert * bonus - umweg * abstand, GOTO sammeln

STATE sammeln
  IF ladung_ist_voll THEN fahre_zu depot
  ELSE fahre_zu BEST muell BY wert * bonus - umweg * abstand</div>
<table>
<tr><td><code>fahre rechts</code> oder <code>rechts</code></td><td>Vor einer Richtung darf
<code>fahre</code> in einer Folge fehlen.</td></tr>
<tr><td><code>warte</code>, <code>presse</code>, <code>ramme gegner</code>,
<code>fahre_zu …</code></td><td>Jede Aktion geht als Schritt. <code>fahre_zu</code> ist
auch hier nur <b>ein</b> Schritt Richtung Ziel, nicht der ganze Weg.</td></tr>
<tr><td><code>GOTO sammeln</code></td><td>Nur ganz am Ende: Nach dem letzten Schritt geht
es in diesem Modus weiter. Ohne <code>GOTO</code> ist er danach wieder im Modus der
Regel — stimmt die Bedingung dann noch, beginnt die Folge von vorn.</td></tr>
<tr><td><code>BEST muell BY …</code></td><td>Die <b>ganze Formel</b> gehört in den Schritt
— ein „das beste Stück von vorhin“ gibt es nicht. Brauchst du dieselbe Formel öfter, halte
die Zahlen mit <code>LET</code> an einer Stelle, wie oben <code>umweg</code>.</td></tr>
</table>
<p class="klein"><b>Eine Folge schaut nicht hin.</b> Solange sie läuft, prüft dein Roboter
die Regeln seines Modus nicht. Ist ein Weg versperrt, bleibt er stehen und macht trotzdem
mit dem nächsten Schritt weiter. Die Regeln <b>vor</b> dem ersten <code>STATE</code>
werden aber in jedem Zug zuerst geprüft; springt eine davon mit <code>GOTO</code> in einen
anderen Modus, ist die Folge abgebrochen. Vor dem ersten <code>STATE</code> selbst gibt es
keine Folgen. Was eine Folge genau tut, steht unter dem Editor, sobald du sie
schreibst.</p>

<h3>Die Spielregeln in Kürze</h3>
<table>
<tr><td>Zwangsaufnahme</td><td>Wer auf ein Feld mit Müll fährt, nimmt ihn auf. Immer.
Wegwerfen geht nicht.</td></tr>
<tr><td>Wertverfall</td><td>Liegender Müll verliert langsam an Wert und wird irgendwann
negativ. In der Ladung altert nichts mehr.</td></tr>
<tr><td>Bonuszone</td><td>Müll, den du <b>in</b> der Zone aufnimmst, zählt doppelt — für
immer. Die Zone wandert.</td></tr>
<tr><td>Rammen</td><td>Schubst den Gegner und klaut ihm ein <b>zufälliges</b> Teil.
Kostet beiden Energie.</td></tr>
<tr><td>Radioaktives Fass</td><td>Ein radioaktives Fass ist viele Punkte wert — negativ.
Es altert nicht. Wer eins trägt, ist gefährlich zu rammen.</td></tr>
<tr><td>Akku leer</td><td>Unter 30 fährt der Roboter nur noch jeden zweiten Zug. Fällt der
Akku auf 0, ist die <b>ganze Ladung weg</b> — nur ein radioaktives Fass bleibt dir.</td></tr>
<tr><td>Depot</td><td>Punkte zählen erst beim Abliefern. Solange der Roboter ablädt,
kann er sich nicht bewegen — dabei lädt der Akku wieder auf.</td></tr>
<tr><td>Rundenende</td><td>Was du am Ende noch trägst, zählt nur halb — Minuspunkte
dagegen voll.</td></tr>
</table>

<h3>Für Fortgeschrittene: Richtung und Nachbarfelder</h3>
<table>
<tr><td><code>richtung_zu &lt;ziel&gt;</code></td><td>Wohin <code>fahre_zu</code> als Nächstes
fahren würde: <code>oben</code>, <code>unten</code>, <code>links</code>,
<code>rechts</code> — oder <code>hier</code> (schon da) bzw. <code>keine</code>
(kein Weg).</td></tr>
<tr><td><code>objekt_in_richtung(&lt;richtung&gt;)</code></td><td>Was auf dem Nachbarfeld
liegt: <code>frei</code>, <code>wand</code>, <code>gegner</code>, <code>depot</code> oder
eine Müllsorte wie <code>radioaktiv</code>. Statt einer Richtung geht auch
<code>richtung_zu …</code>.</td></tr>
</table>
<div class="beispiel">IF objekt_in_richtung(richtung_zu depot) == radioaktiv THEN GOTO ausweichen</div>
<p class="klein">Beide liefern ein Wort, keine Zahl — verglichen wird nur mit
<code>==</code> und <code>!=</code>. Wie man damit einem radioaktiven Fass ausweicht,
findet ihr selbst heraus.</p>

<h3>Für Fortgeschrittene: echtes Python</h3>
<p>Zwischen <code>PYTHON</code> und <code>END</code> darfst du richtiges Python schreiben.
Es wird an dieser Stelle in die Abgabedatei übernommen. Das Objekt heißt
<code>zustand</code>, und du gibst mit <code>return</code> eine Aktion zurück.</p>
<div class="beispiel">PYTHON
bestes = None
for stueck in zustand.muell_auswahl(nur_positiv=True):
    weg = zustand.abstand_zu_feld(stueck["x"], stueck["y"])
    if bestes is None or stueck["wert"] - weg * 3 &gt; bestes[0]:
        bestes = (stueck["wert"] - weg * 3, stueck)
if bestes:
    return zustand.fahre_zu_feld(bestes[1]["x"], bestes[1]["y"])
END</div>
`;

const ANLEITUNG = `
<h2>In fünf Minuten zum ersten Roboter</h2>
<ol>
<li>Trag oben im Kasten euren <b>Teamnamen</b> ein.</li>
<li>Links steht schon ein Beispiel. Drück <b>▶ Testlauf</b> und sieh zu.</li>
<li>Unter dem Spielfeld siehst du bei jedem Tick, <b>welche Regel gerade greift</b> —
die Zeile wird im Editor gelb hinterlegt. Auf jedem Müllstück steht sein Wert, ein
Pfeil zeigt, wohin dein Roboter als Nächstes fährt.</li>
<li>Ändere eine Regel, drück wieder Testlauf. Gleicher Seed heißt gleiches Spiel:
so siehst du, ob deine Änderung wirklich besser war.</li>
<li>Wenn du zufrieden bist: <b>Abgeben</b>. Die heruntergeladene <code>.py</code>-Datei
ist eure Abgabe.</li>
</ol>
<p class="klein">Optional: ein <b>Logo</b> — quadratische Bilddatei mit demselben Namen
wie die Abgabedatei, z.&nbsp;B. <code>die_muell_profis.png</code> (auch
<code>.jpg</code>, <code>.jpeg</code>, <code>.webp</code>, <code>.gif</code>). Ohne
Logo zeigt das Turnier ein Kästchen mit dem Anfangsbuchstaben.</p>
<h2>Drei Ratschläge</h2>
<ul>
<li><b>Fahr rechtzeitig heim.</b> Punkte gibt es nur im Depot, und am Rundenende zählt
die Ladung nur halb.</li>
<li><b>Schau auf den Akku.</b> Unter dem Schwellwert fährt der Roboter nur noch jeden
zweiten Tick. Fällt er auf 0, ist die Ladung weg. Abliefern lädt auf.</li>
<li><b>Rammen ist ein Glücksspiel.</b> Du klaust ein zufälliges Teil — vielleicht ein
radioaktives Fass. Genau das kann man auch ausnutzen.</li>
</ul>
<h2>Wenn die Liste nicht mehr reicht</h2>
<p>Gib deinem Roboter <b>Modi</b>: einen zum Sammeln, einen für den Heimweg, einen für
den Hinterhalt. <code>STATE</code> legt einen an, <code>GOTO</code> wechselt hinüber —
das kostet keinen Zug. Alles dazu steht in der Befehlsreferenz.</p>
<p class="klein">Tastenkürzel: <code>Strg</code>+<code>Enter</code> startet den Testlauf.</p>
`;

document.addEventListener('DOMContentLoaded', async () => {
  document.getElementById('referenz-inhalt').innerHTML = REFERENZ;
  document.getElementById('anleitung-inhalt').innerHTML = ANLEITUNG;

  const werkstatt = new Werkstatt();
  window.werkstatt = werkstatt;
  try {
    await werkstatt.starten();
  } catch (fehler) {
    document.getElementById('meldungen').innerHTML =
      `<div class="meldung fehler">${schuetze(fehler.message)}</div>`;
  }

  document.getElementById('knopf-anleitung').addEventListener('click',
    () => document.getElementById('dialog-anleitung').showModal());

  const fsrDialog = document.getElementById('dialog-fsr');
  document.getElementById('knopf-fsr').addEventListener('click', () => {
    if (window.fsr && window.fsr.angemeldet) { window.fsr.umschalten(); return; }
    document.getElementById('fsr-fehler').textContent = '';
    fsrDialog.showModal();
  });
  document.getElementById('fsr-abbrechen').addEventListener('click', () => {
    fsrDialog.close();
  });
  document.getElementById('fsr-anmelden').addEventListener('click', async (e) => {
    e.preventDefault();
    const passwort = document.getElementById('fsr-passwort').value;
    try {
      const antwort = await hole('/api/fsr/anmelden', { passwort });
      fsrDialog.close();
      document.getElementById('fsr-passwort').value = '';
      await window.fsr.anmelden(antwort.marke);
    } catch (fehler) {
      document.getElementById('fsr-fehler').textContent = fehler.message;
    }
  });
});
