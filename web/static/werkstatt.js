/* Die Werkstatt: Editor, Prüfung, Testlauf, Abgabe.
   Der Browser prüft nichts selbst — jede Meldung kommt aus dem Python-Parser.
   Die Einfärbung im Editor ist reine Darstellung. */

const SCHLUESSELWOERTER = new Set(['if', 'then', 'else', 'and', 'or', 'not',
  'state', 'goto', 'let', 'best', 'by', 'random']);
const AKTIONSWOERTER = new Set(['fahre_zu', 'fahre', 'ramme', 'warte', 'presse']);
const ZIELWOERTER = new Set(['depot', 'gegner', 'zone', 'naechster_muell', 'nächster_müll',
  'naechster_müll', 'nächster_muell', 'muell', 'müll', 'weg_von', 'feld', 'in_zone',
  'papier', 'bio', 'metall', 'elektro', 'radioaktiv', 'fass', 'oben', 'unten', 'links',
  'rechts', 'ladung', 'akku', 'gegner_sichtbar', 'gegner_ladung', 'abstand_zu', 'tick',
  'punkte', 'bin_in_zone', 'muell_in_zone', 'ladung_ist_voll', 'ladung_ist_leer',
  'freie_plaetze', 'ladung_wert', 'restliche_ticks', 'anzahl', 'habe',
  'kann_pressen', 'ballen', 'wert', 'abstand', 'bonus', 'richtung_zu',
  'objekt_in_richtung', 'hier', 'keine', 'frei', 'wand']);
const BLOCKWOERTER = new Set(['python', 'end']);

const VORLAGE = `# Dein Roboter ist ein Zustandsautomat: STATE ist ein Modus, GOTO schaltet um.
# Ein Wechsel kostet keinen Zug — der Roboter handelt sofort weiter.
# In jedem Modus gilt: Regeln von oben nach unten, die erste passende gewinnt.
# Drück ▶ Testlauf. Unter dem Spielfeld steht, in welchem Modus er gerade ist.

LET akku_reserve = 30

# Regeln vor dem ersten STATE gelten in JEDEM Modus — gut für Notfälle.
IF akku < akku_reserve AND NOT ladung_ist_leer THEN fahre_zu depot

STATE sammeln
  IF ladung_ist_voll THEN GOTO heimweg
  ELSE fahre_zu naechster_muell

STATE heimweg
  IF ladung_ist_leer THEN GOTO sammeln
  ELSE fahre_zu depot

# Damit gewinnt er noch nichts. Vier Schritte weiter — Kommentarzeichen
# wegnehmen, Testlauf drücken, nachsehen was sich ändert.

# 1. Klüger zielen: nicht zum nächsten Stück, sondern zum lohnendsten.
#    Von allem hier bringt das am meisten.
#    Schreib oben dazu:  LET wegkosten = 3
#    und ersetze die ELSE-Zeile in STATE sammeln durch:
#      ELSE fahre_zu BEST muell BY wert * bonus - wegkosten * abstand
#    Die 3 sagt, was dir ein Schritt Umweg wert ist. Dreh an dieser Zahl.
#    bonus rechnet die Bonuszone schon mit ein — dafür brauchst du keinen
#    eigenen Modus.

# 2. Ausweichen: Jeder Modus hat seine eigene Regelliste, und darin liegt ihr
#    Sinn: beladen geht er dem Gegner aus dem Weg, leer ist der ihm egal. Diese
#    Zeile gehört nach STATE heimweg, vor die ELSE-Zeile:
#      IF gegner_sichtbar AND abstand_zu gegner < 3 THEN fahre_zu weg_von gegner
#    Gemessen gegen den Lauerer, je 60 Spiele mit Schritt 1: 37 zu 30 Siege und
#    rund 86 Punkte weniger, dazu etwas mehr langsame Ticks. Sie kostet Wege und
#    bringt keinen Sieg — ausprobieren, aber keine Wunder erwarten.

# 3. Ein dritter Modus — dem beladenen Gegner die Ladung abnehmen. Der Weg
#    hinein gehört nach STATE sammeln, vor die ELSE-Zeile:
#      IF gegner_sichtbar AND gegner_ladung >= 4 THEN GOTO jagd
#    Vorsicht: Rammen kostet Akku und Züge, in denen du nicht sammelst. So wie
#    der Modus hier steht, verliert er mehr, als er einbringt — nachgemessen.
#    Findest du eine Fassung, bei der die Rechnung aufgeht?
# STATE jagd
#   IF NOT gegner_sichtbar THEN GOTO sammeln
#   IF gegner_ladung < 2 THEN GOTO sammeln
#   ELSE ramme gegner

# 4. Endspurt: Am Rundenende zählt die Restladung nur halb, Minuspunkte voll.
#    Diese Regel schickt ihn rechtzeitig heim, solange sich der Weg noch lohnt.
#    Sie gehört in STATE sammeln, vor die ELSE-Zeile:
#      IF restliche_ticks < 50 AND NOT ladung_ist_leer AND abstand_zu depot < restliche_ticks THEN GOTO heimweg
#    Gemessen gegen den Hausmeister, je 60 Spiele mit Schritt 1: 1040:942
#    Punkte ohne die Regel, 1066:940 mit ihr — eine Partie mehr gewonnen und
#    rund 27 Punkte mehr. Nach Tick 350 wechselt noch in 15–17 % der Partien die
#    Rohpunkte-Führung, in 0–3 % kippt der Sieger erst durch die Schlussbuchung,
#    weil die Restladung nur halb zählt. Nach Schritt 1 ist das der Schritt, der
#    sich noch lohnt.
`;

/* Frühere Fassungen der Vorlage. Wer eine davon unverändert im Zwischenspeicher
   liegen hat, hat nie etwas Eigenes geschrieben — der bekommt beim nächsten Öffnen
   die aktuelle Vorlage statt eines Beispiels, das die Anleitung nicht mehr kennt.
   Verglichen wird auf's Zeichen genau, damit kein selbst geschriebener Entwurf
   verloren geht. */
const ALTE_VORLAGEN = [`# Dein Roboter ist ein Zustandsautomat: STATE ist ein Modus, GOTO schaltet um.
# Ein Wechsel kostet keinen Zug — der Roboter handelt sofort weiter.
# In jedem Modus gilt: Regeln von oben nach unten, die erste passende gewinnt.
# Drück ▶ Testlauf. Unter dem Spielfeld steht, in welchem Modus er gerade ist.

LET akku_reserve = 30

# Regeln vor dem ersten STATE gelten in JEDEM Modus — gut für Notfälle.
IF akku < akku_reserve AND NOT ladung_ist_leer THEN fahre_zu depot

STATE sammeln
  IF ladung_ist_voll THEN GOTO heimweg
  ELSE fahre_zu naechster_muell

STATE heimweg
  IF ladung_ist_leer THEN GOTO sammeln
  ELSE fahre_zu depot

# Damit gewinnt er noch nichts. Drei Schritte weiter — Kommentarzeichen
# wegnehmen, Testlauf drücken, nachsehen was sich ändert.

# 1. Klüger zielen: nicht zum nächsten Stück, sondern zum lohnendsten.
#    Von allem hier bringt das am meisten.
#    Schreib oben dazu:  LET wegkosten = 3
#    und ersetze die ELSE-Zeile in STATE sammeln durch:
#      ELSE fahre_zu BEST muell BY wert * bonus - wegkosten * abstand
#    Die 3 sagt, was dir ein Schritt Umweg wert ist. Dreh an dieser Zahl.
#    bonus rechnet die Bonuszone schon mit ein — dafür brauchst du keinen
#    eigenen Modus.

# 2. Jeder Modus hat seine eigene Regelliste, und darin liegt ihr Sinn: beladen
#    geht er dem Gegner aus dem Weg, leer ist der ihm egal. Diese Zeile gehört
#    nach STATE heimweg, vor die ELSE-Zeile:
#      IF gegner_sichtbar AND abstand_zu gegner < 3 THEN fahre_zu weg_von gegner

# 3. Ein dritter Modus — dem beladenen Gegner die Ladung abnehmen. Der Weg
#    hinein gehört nach STATE sammeln, vor die ELSE-Zeile:
#      IF gegner_sichtbar AND gegner_ladung >= 4 THEN GOTO jagd
#    Vorsicht: Rammen kostet Akku und Züge, in denen du nicht sammelst. So wie
#    der Modus hier steht, verliert er mehr, als er einbringt — nachgemessen.
#    Findest du eine Fassung, bei der die Rechnung aufgeht?
# STATE jagd
#   IF NOT gegner_sichtbar THEN GOTO sammeln
#   IF gegner_ladung < 2 THEN GOTO sammeln
#   ELSE ramme gegner
`,
`# Regeln werden von oben nach unten geprüft.
# Die erste Regel, die zutrifft, wird ausgeführt.

IF ladung_ist_voll THEN fahre_zu depot
IF akku < 30 THEN fahre_zu depot
IF gegner_sichtbar AND gegner_ladung >= 4 THEN ramme gegner
IF muell_in_zone THEN fahre_zu naechster_muell(in_zone)
ELSE fahre_zu naechster_muell

# Wenn das nicht mehr reicht: gib deinem Roboter Modi.
# STATE sammeln
#   IF ladung_ist_voll THEN GOTO heimweg
#   ELSE fahre_zu BEST muell BY wert * bonus - 3 * abstand
# STATE heimweg
#   IF ladung_ist_leer THEN GOTO sammeln
#   ELSE fahre_zu depot
`];

function schuetze(text) {
  return String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

/* Zugriffe auf den Zwischenspeicher dürfen nie die ganze Seite lahmlegen — im
   privaten Modus wirft schon `getItem`. */
function lesenLokal(schluessel) {
  try { return localStorage.getItem(schluessel); } catch (fehler) { return null; }
}

function speichernLokal(schluessel, wert) {
  try { localStorage.setItem(schluessel, wert); } catch (fehler) { /* dann eben nicht */ }
}

function entfernenLokal(schluessel) {
  try { localStorage.removeItem(schluessel); } catch (fehler) { /* egal */ }
}

async function antwortLesen(antwort) {
  let inhalt;
  try {
    inhalt = await antwort.json();
  } catch (fehler) {
    throw new Error(antwort.ok
      ? 'Die Antwort des Servers war unlesbar.'
      : `Der Server meldet einen Fehler (${antwort.status}).`);
  }
  if (!antwort.ok) {
    throw new Error(inhalt.fehler || `Der Server meldet einen Fehler (${antwort.status}).`);
  }
  return inhalt;
}

async function hole(pfad, daten) {
  let antwort;
  try {
    antwort = await fetch(pfad, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(daten || {}),
    });
  } catch (fehler) {
    throw new Error('Der Server antwortet nicht.');
  }
  return antwortLesen(antwort);
}

async function holeGet(pfad) {
  let antwort;
  try {
    antwort = await fetch(pfad);
  } catch (fehler) {
    throw new Error('Der Server antwortet nicht.');
  }
  return antwortLesen(antwort);
}

class Werkstatt {
  constructor() {
    this.editor = document.getElementById('editor');
    this.hervorhebung = document.getElementById('hervorhebung');
    this.zeilennummern = document.getElementById('zeilennummern');
    this.meldungen = document.getElementById('meldungen');
    this.teamname = document.getElementById('teamname');
    this.gegnerAuswahl = document.getElementById('gegner');
    this.seedFeld = document.getElementById('seed');

    this.spielfeld = new Spielfeld(document.getElementById('spielfeld'));
    this.spielfeld.werteZeigen = true;
    this.spielfeld.pfeileZeigen = true;
    this.wiedergabe = new Wiedergabe(this.spielfeld, (i) => this.rahmenGezeichnet(i));
    this.wiedergabe.aufEnde = () => this.startKnopfAktualisieren();

    this.fehlerZeilen = new Set();
    this.aktiveZeile = null;
    this.aufzeichnung = null;
    this.regelnDerAufzeichnung = null;
    this.pruefUhr = null;
    this.pruefNr = 0;
    this.status = null;
  }

  async starten() {
    this.status = await holeGet('/api/status');
    this.gegnerFuellen();
    this.wiederherstellen();
    this.verdrahten();
    this.zeichneEditor();
    this.pruefen();
  }

  gegnerFuellen() {
    this.gegnerAuswahl.innerHTML = '';
    /* „Keiner" steht oben und ist die Vorgabe: Beim ersten Testlauf will man sehen,
       was der eigene Roboter tut. Ein zweiter, der gleichzeitig einsammelt, verdeckt
       das nur — und ob man gewinnt, ist erst interessant, wenn er überhaupt fährt.
       Der leere Wert bedeutet für /api/testlauf „allein fahren". */
    const allein = document.createElement('option');
    allein.value = '';
    allein.textContent = 'Keiner';
    allein.title = 'Allein über das Feld — gut, um den eigenen Roboter zu beobachten.';
    this.gegnerAuswahl.appendChild(allein);
    this.status.gegner.forEach((g) => {
      const eintrag = document.createElement('option');
      eintrag.value = g.datei;
      eintrag.textContent = g.name;
      eintrag.title = g.beschreibung || '';
      this.gegnerAuswahl.appendChild(eintrag);
    });
    this.gegnerAuswahl.value = '';
  }

  wiederherstellen() {
    const gespeichert = lesenLokal('werkstatt.quelltext');
    const unberuehrt = gespeichert === null
      || ALTE_VORLAGEN.some((alt) => alt.trim() === gespeichert.trim());
    this.editor.value = unberuehrt ? VORLAGE : gespeichert;
    const name = lesenLokal('werkstatt.teamname');
    if (name) this.teamname.value = name;
    /* Der leere Wert („Keiner") ist eine gültige Wahl — deshalb auf null prüfen
       und nicht auf Wahrheitswert. */
    const gegner = lesenLokal('werkstatt.gegner');
    if (gegner !== null
        && [...this.gegnerAuswahl.options].some((o) => o.value === gegner)) {
      this.gegnerAuswahl.value = gegner;
    }
    const seed = lesenLokal('werkstatt.seed');
    if (seed !== null) this.seedFeld.value = seed;
  }

  teilerVerdrahten() {
    /* Der Balken zwischen Editor und Spielfeld. Gezogen wird die Breite der linken
       Spalte; die rechte bekommt den Rest. Beides bleibt über den Mindestbreiten,
       sonst ist entweder der Code oder das Feld nicht mehr zu gebrauchen.

       Gerechnet wird relativ zur Breite beim Aufsetzen, nicht zur Zeigerposition:
       Sonst springt die Spalte schon beim bloßen Anklicken um die halbe Balkenbreite. */
    const teiler = document.getElementById('teiler');
    const raster = document.getElementById('werkstatt');
    const links = document.querySelector('.spalte-links');
    const MIN_LINKS = 380;
    const MIN_RECHTS = 340;

    const gespeichert = lesenLokal('werkstatt.spaltenbreite');
    if (gespeichert) raster.style.setProperty('--spalte-links', gespeichert);

    const hoechstens = () => {
      const stil = getComputedStyle(raster);
      const innen = raster.clientWidth
        - parseFloat(stil.paddingLeft) - parseFloat(stil.paddingRight);
      return innen - teiler.offsetWidth - 2 * (parseFloat(stil.columnGap) || 0) - MIN_RECHTS;
    };

    const setzen = (breite) => {
      const grenze = hoechstens();
      if (grenze < MIN_LINKS) return;          // Fenster zu schmal zum Verteilen
      const wert = Math.round(Math.min(Math.max(breite, MIN_LINKS), grenze));
      raster.style.setProperty('--spalte-links', `${wert}px`);
    };

    const merken = () => {
      const wert = raster.style.getPropertyValue('--spalte-links').trim();
      if (wert) speichernLokal('werkstatt.spaltenbreite', wert);
    };

    let zieht = false;
    let startX = 0;
    let startBreite = 0;
    teiler.addEventListener('pointerdown', (e) => {
      zieht = true;
      startX = e.clientX;
      startBreite = links.offsetWidth;
      teiler.setPointerCapture(e.pointerId);
      teiler.classList.add('zieht');
      /* Kein preventDefault: Das unterdrückt die Maus-Folgeereignisse, und damit
         käme der Doppelklick unten nie an. Gegen das Markieren von Text hilft
         `user-select` — am Balken immer, am Rest der Seite nur während des Zugs. */
      document.body.style.userSelect = 'none';
    });
    teiler.addEventListener('pointermove', (e) => {
      if (zieht) setzen(startBreite + (e.clientX - startX));
    });
    const loslassen = () => {
      if (!zieht) return;
      zieht = false;
      teiler.classList.remove('zieht');
      document.body.style.userSelect = '';
      merken();
    };
    teiler.addEventListener('pointerup', loslassen);
    teiler.addEventListener('pointercancel', loslassen);

    /* Mit der Maus gezogen, mit den Pfeiltasten feinjustiert — und ein Doppelklick
       stellt die Ausgangsaufteilung wieder her. */
    teiler.addEventListener('keydown', (e) => {
      const richtung = e.key === 'ArrowLeft' ? -1 : (e.key === 'ArrowRight' ? 1 : 0);
      if (!richtung) return;
      e.preventDefault();
      setzen(links.offsetWidth + richtung * (e.shiftKey ? 48 : 16));
      merken();
    });
    teiler.addEventListener('dblclick', () => {
      raster.style.removeProperty('--spalte-links');
      entfernenLokal('werkstatt.spaltenbreite');
    });

    /* Wird das Fenster schmaler, kann eine gemerkte Breite nicht mehr passen —
       dann nachziehen, sonst steht das Spielfeld über den Rand hinaus. */
    window.addEventListener('resize', () => {
      if (raster.style.getPropertyValue('--spalte-links')) setzen(links.offsetWidth);
    });
  }

  vorlageEinsetzen() {
    /* Zurück auf Anfang — für alle, die sich verrannt haben, und für jeden Entwurf,
       der noch aus einer früheren Fassung stammt. Eigene Arbeit wird nur nach
       Rückfrage überschrieben. */
    const eigenes = this.editor.value.trim()
      && this.editor.value.trim() !== VORLAGE.trim()
      && !ALTE_VORLAGEN.some((alt) => alt.trim() === this.editor.value.trim());
    if (eigenes && !window.confirm('Deine Regeln durch die Beispiel-Vorlage ersetzen?')) {
      return;
    }
    this.editor.value = VORLAGE;
    this.zeichneEditor();
    this.sichern();
    this.pruefen();
    this.editor.focus();
  }

  sichern() {
    speichernLokal('werkstatt.quelltext', this.editor.value);
    speichernLokal('werkstatt.teamname', this.teamname.value);
    speichernLokal('werkstatt.gegner', this.gegnerAuswahl.value);
    /* Auch der Seed gehört dazu: „Gleicher Seed, gleiches Spiel" ist nur
       nachvollziehbar, wenn er ein Neuladen übersteht. */
    speichernLokal('werkstatt.seed', this.seedFeld.value);
  }

  verdrahten() {
    this.editor.addEventListener('input', () => {
      this.zeichneEditor();
      this.sichern();
      clearTimeout(this.pruefUhr);
      this.pruefUhr = setTimeout(() => this.pruefen(), 400);
    });
    this.editor.addEventListener('scroll', () => {
      this.hervorhebung.scrollTop = this.editor.scrollTop;
      this.zeilennummern.scrollTop = this.editor.scrollTop;
    });
    this.editor.addEventListener('keydown', (e) => {
      if (e.key === 'Tab') {
        e.preventDefault();
        const s = this.editor.selectionStart;
        this.editor.setRangeText('    ', s, this.editor.selectionEnd, 'end');
        this.editor.dispatchEvent(new Event('input'));
      }
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        this.testlauf();
      }
    });
    /* Zieht jemand den Editor größer oder ändert sich die Fensterbreite, brechen die
       Zeilen anders um — dann müssen die Nummern neu ausgemessen werden. */
    if (window.ResizeObserver) {
      new ResizeObserver(() => this.nummernAusrichten()).observe(this.editor);
    } else {
      window.addEventListener('resize', () => this.nummernAusrichten());
    }
    this.teilerVerdrahten();
    this.teamname.addEventListener('input', () => this.sichern());
    this.seedFeld.addEventListener('input', () => this.sichern());
    this.gegnerAuswahl.addEventListener('change', () => this.sichern());

    document.getElementById('knopf-vorlage').addEventListener('click', () => this.vorlageEinsetzen());
    document.getElementById('knopf-testlauf').addEventListener('click', () => this.testlauf());
    document.getElementById('knopf-speichern').addEventListener('click', () => this.speichern());
    document.getElementById('knopf-abgabe').addEventListener('click', () => this.abgeben());
    document.getElementById('knopf-laden').addEventListener('click',
      () => document.getElementById('datei-eingabe').click());
    document.getElementById('datei-eingabe').addEventListener('change',
      (e) => this.dateiOeffnen(e));

    document.getElementById('knopf-start').addEventListener('click', () => {
      this.wiedergabe.umschalten();
      this.startKnopfAktualisieren();
    });
    document.getElementById('knopf-vor').addEventListener('click', () => {
      this.wiedergabe.schritt(1); this.startKnopfAktualisieren();
    });
    document.getElementById('knopf-zurueck').addEventListener('click', () => {
      this.wiedergabe.schritt(-1); this.startKnopfAktualisieren();
    });
    document.getElementById('schieber').addEventListener('input', (e) => {
      this.wiedergabe.pause();
      this.wiedergabe.springe(Number(e.target.value));
      this.startKnopfAktualisieren();
    });
    document.getElementById('tempo').addEventListener('change', (e) => {
      this.wiedergabe.tempo = Number(e.target.value);
    });
  }

  /* ------------------------------------------------------------ Editor */

  zeichneEditor() {
    const zeilen = this.editor.value.split('\n');
    /* Jede Textzeile ist ein eigener Block, ohne '\n' dazwischen — sonst käme durch
       das pre-wrap hinter jeder Zeile eine leere zweite heraus. */
    this.hervorhebung.innerHTML = zeilen
      .map((zeile, i) => {
        const aktiv = this.aktiveZeile === i + 1 ? ' zeile-aktiv' : '';
        return `<span class="zl${aktiv}">${this.faerbe(zeile) || ' '}</span>`;
      })
      .join('');
    this.zeilennummern.innerHTML = zeilen
      .map((_, i) => {
        const nummer = i + 1;
        let klasse = 'zn';
        if (this.fehlerZeilen.has(nummer)) klasse += ' zn-fehler';
        else if (this.aktiveZeile === nummer) klasse += ' zn-aktiv';
        return `<span class="${klasse}">${nummer}</span>`;
      })
      .join('');
    this.nummernAusrichten();
  }

  nummernAusrichten() {
    /* Eine lange Regel wird umgebrochen und ist dann mehrere Bildschirmzeilen hoch.
       Ihre Nummer bekommt dieselbe Höhe, sonst zeigt ab da jede Nummer auf die
       falsche Zeile — und mit ihr die Fehlermarkierung. */
    const zeilen = this.hervorhebung.children;
    const nummern = this.zeilennummern.children;
    for (let i = 0; i < nummern.length; i++) {
      /* Gerundete Höhen summieren sich über viele Zeilen zu einem sichtbaren
         Versatz — deshalb die genaue Höhe aus getBoundingClientRect. */
      const hoehe = zeilen[i] ? zeilen[i].getBoundingClientRect().height : 0;
      nummern[i].style.height = hoehe ? `${hoehe}px` : '';
    }
  }

  faerbe(zeile) {
    const raute = zeile.indexOf('#');
    let rumpf = zeile;
    let kommentar = '';
    if (raute >= 0) {
      rumpf = zeile.slice(0, raute);
      kommentar = `<span class="s-kommentar">${schuetze(zeile.slice(raute))}</span>`;
    }
    const gefaerbt = rumpf.replace(
      /([A-Za-zÄÖÜäöüß_][A-Za-zÄÖÜäöüß0-9_]*|\d+)/g,
      (treffer) => {
        const klein = treffer.toLowerCase();
        if (/^\d+$/.test(treffer)) return `<span class="s-zahl">${treffer}</span>`;
        if (BLOCKWOERTER.has(klein)) return `<span class="s-python">${schuetze(treffer)}</span>`;
        if (SCHLUESSELWOERTER.has(klein)) return `<span class="s-schluessel">${schuetze(treffer)}</span>`;
        if (AKTIONSWOERTER.has(klein)) return `<span class="s-aktion">${schuetze(treffer)}</span>`;
        if (ZIELWOERTER.has(klein)) return `<span class="s-ziel">${schuetze(treffer)}</span>`;
        return schuetze(treffer);
      });
    return gefaerbt + kommentar;
  }

  zeileAnspringen(nummer) {
    const zeilen = this.editor.value.split('\n');
    let stelle = 0;
    for (let i = 0; i < Math.min(nummer - 1, zeilen.length); i++) stelle += zeilen[i].length + 1;
    this.editor.focus();
    this.editor.setSelectionRange(stelle, stelle + (zeilen[nummer - 1] || '').length);
  }

  /* ------------------------------------------------------------ Prüfen */

  /* Eine noch offene Prüfung verwerfen: Sonst überschreibt ihre Antwort später
     das Ergebnis eines Testlaufs oder einer Abgabe. */
  pruefungVerwerfen() {
    clearTimeout(this.pruefUhr);
    this.pruefNr += 1;
  }

  async pruefen() {
    const nr = ++this.pruefNr;
    try {
      const ergebnis = await hole('/api/pruefen', { quelltext: this.editor.value });
      if (nr !== this.pruefNr) return null;      // eine neuere Prüfung ist unterwegs
      this.meldungenZeigen(ergebnis);
      return ergebnis;
    } catch (fehler) {
      if (nr === this.pruefNr) {
        this.meldungSetzen([{ klasse: 'fehler', text: fehler.message }]);
      }
      return null;
    }
  }

  meldungenZeigen(ergebnis) {
    this.letzteRegeln = ergebnis.regeln || [];
    this.fehlerZeilen = new Set(ergebnis.fehler.map((f) => f.zeile));
    const eintraege = [];
    ergebnis.fehler.forEach((f) => eintraege.push(
      { klasse: 'fehler', text: f.meldung, zeile: f.zeile }));
    ergebnis.hinweise.forEach((h) => eintraege.push(
      { klasse: 'hinweis', text: h.meldung, zeile: h.zeile }));
    /* Die Schritte einer Folge sind intern eigene Regeln — gezählt wird, was dasteht. */
    const sichtbar = ergebnis.regeln.filter((r) => !r.folge);
    if (!eintraege.length && sichtbar.length) {
      const zahl = sichtbar.length;
      const modi = (ergebnis.modi || []).length;
      eintraege.push({ klasse: 'gut',
        text: `Alles in Ordnung — ${zahl} ${zahl === 1 ? 'Regel' : 'Regeln'} erkannt`
            + (modi ? ` in ${modi} ${modi === 1 ? 'Modus' : 'Modi'}.` : '.') });
    }
    /* Erklärungen zu Folgen: kein Fehler, kein Hinweis — nur, was die Zeile tut. */
    (ergebnis.erklaerungen || []).forEach((e) => eintraege.push(
      { klasse: 'erklaerung', titel: e.titel, text: e.text, zeile: e.zeile }));
    this.meldungSetzen(eintraege);
    this.zeichneEditor();
  }

  meldungSetzen(eintraege) {
    this.meldungen.innerHTML = '';
    eintraege.forEach((e) => {
      const kasten = document.createElement('div');
      kasten.className = `meldung ${e.klasse}`;
      if (e.titel) {
        const titel = document.createElement('b');
        titel.textContent = e.titel;
        kasten.appendChild(titel);
        kasten.appendChild(document.createElement('br'));
      }
      kasten.appendChild(document.createTextNode(e.text));
      if (e.zeile) kasten.addEventListener('click', () => this.zeileAnspringen(e.zeile));
      this.meldungen.appendChild(kasten);
    });
  }

  /* ------------------------------------------------------------ Testlauf */

  async testlauf() {
    const knopf = document.getElementById('knopf-testlauf');
    knopf.disabled = true;
    this.pruefungVerwerfen();
    this.meldungSetzen([{ klasse: 'lade', text: 'Der Testlauf läuft …' }]);
    try {
      const ergebnis = await hole('/api/testlauf', {
        quelltext: this.editor.value,
        teamname: this.teamname.value,
        gegner: this.gegnerAuswahl.value,
        seed: Number(this.seedFeld.value) || 0,
      });
      this.meldungenZeigen(ergebnis.programm);
      if (ergebnis.aufzeichnung) {
        this.aufzeichnungZeigen(ergebnis.aufzeichnung, ergebnis.bericht || []);
      }
    } catch (fehler) {
      this.meldungSetzen([{ klasse: 'fehler', text: fehler.message }]);
    } finally {
      knopf.disabled = false;
    }
  }

  aufzeichnungZeigen(aufzeichnung, bericht = []) {
    this.aufzeichnung = aufzeichnung;
    /* Die Regelnummern der Aufzeichnung gehören zum Quelltext von *jetzt*. Wird
       während der Wiedergabe getippt, zeigt die Anzeige weiter auf die alte
       Fassung — sonst markiert sie die falsche Zeile. */
    this.regelnDerAufzeichnung = this.letzteRegeln;
    document.getElementById('feld-hinweis').hidden = true;
    document.getElementById('wiedergabe').hidden = false;
    document.getElementById('anzeige-karte').hidden = false;
    const schieber = document.getElementById('schieber');
    schieber.max = aufzeichnung.ticks.length;
    schieber.value = 0;
    this.wiedergabe.laden(aufzeichnung);
    this.botmeldungenZeigen(aufzeichnung, bericht);
    this.wiedergabe.start();
    this.startKnopfAktualisieren();
  }

  botmeldungenZeigen(aufzeichnung, bericht = []) {
    const eintraege = [];
    (aufzeichnung.bots || []).forEach((bot, i) => {
      if (i !== 0) return;                       // nur der eigene Roboter
      bot.fehler.forEach((f) => eintraege.push(
        { klasse: 'fehler', text: `Dein Roboter: ${f.split('\n').filter(Boolean).pop()}` }));
      if (bot.statistik.ueberzogen > 0) {
        eintraege.push({ klasse: 'hinweis',
          text: `Dein Roboter hat ${bot.statistik.ueberzogen} Züge über dem Zeitlimit `
              + `von ${this.status.spiel.zeitlimit_ms} ms gebraucht und dabei ausgesetzt.` });
      }
      if (bot.meldungen.length) {
        eintraege.push({ klasse: 'hinweis',
          text: `Ausgaben deines Roboters (${bot.meldungen.length}): `
              + bot.meldungen.slice(0, 3).join(' · ') });
      }
    });
    const ergebnis = aufzeichnung.ergebnis;
    if (ergebnis) {
      const meiner = ergebnis.roboter[0];
      const gegner = ergebnis.roboter[1];
      let text;
      if (!gegner) {
        /* Allein gefahren — da gibt es nichts zu gewinnen, nur etwas zu sehen. */
        const teile = meiner.statistik.abgeliefert_stueck;
        text = `Allein gefahren: ${meiner.punkte} Punkte, ${teile} `
             + `${teile === 1 ? 'Teil' : 'Teile'} abgeliefert.`;
      } else if (ergebnis.unentschieden) text = 'Unentschieden.';
      else if (ergebnis.sieger === 0) text = `Gewonnen! ${meiner.punkte} : ${gegner.punkte}`;
      else text = `Verloren. ${meiner.punkte} : ${gegner.punkte}`;
      eintraege.unshift({ klasse: ergebnis.sieger === 0 ? 'gut' : 'hinweis', text });
    }
    /* Was der Server im Lauf gefunden hat: Stillstand, Folgen ins Leere, Kreise. */
    bericht.forEach((e) => eintraege.push(e));
    if (eintraege.length) {
      eintraege.forEach((e) => {
        const kasten = document.createElement('div');
        kasten.className = `meldung ${e.klasse}`;
        kasten.textContent = e.text;
        if (e.zeile) kasten.addEventListener('click', () => this.zeileAnspringen(e.zeile));
        this.meldungen.appendChild(kasten);
      });
    }
  }

  startKnopfAktualisieren() {
    document.getElementById('knopf-start').textContent = this.wiedergabe.laeuft ? '❚❚' : '▶';
  }

  rahmenGezeichnet(index) {
    const a = this.aufzeichnung;
    if (!a) return;
    document.getElementById('schieber').value = index;
    document.getElementById('tickanzeige').textContent = `${index} / ${a.ticks.length}`;
    const zustand = index <= 0 ? a.start : a.ticks[index - 1];

    /* Punktestand */
    const langsamAb = this.status && this.status.spiel
      ? this.status.spiel.akku_langsam_ab : null;
    const kacheln = zustand.roboter.map((r, i) => {
      const s = a.spieler[i];
      const akku = Math.max(0, Math.min(100, r.akku));
      return `<div class="spieler-kachel" style="border-left-color:${s.farbe}">
        <div class="name"><span>${schuetze(s.name)}</span></div>
        <div class="punkte">${r.punkte}</div>
        <div class="zeile"><span>Akku ${r.akku}${r.laedt > 0 ? ' ⚡ lädt' : ''}</span></div>
        <div class="balken${akku < langsamAb ? ' leer' : ''}"><div style="width:${akku}%"></div></div>
        ${MuellAnzeige.kachelInhalt(a, r, i, index)}
      </div>`;
    }).join('');
    document.getElementById('punktestand').innerHTML = kacheln;

    /* Welche Regel greift gerade? */
    const anzeige = document.getElementById('regelanzeige');
    if (index > 0 && zustand.regeln) {
      const nummer = zustand.regeln[0];
      const eintrag = this.regelEintrag(nummer);
      const quelle = eintrag ? eintrag.quelle : (nummer ? `Regel ${nummer}` : null);
      const modus = (eintrag && eintrag.modus ? `Modus ${eintrag.modus} · ` : '')
        + (eintrag && eintrag.folge
          ? `Folge aus Zeile ${eintrag.folge.zeile}, Schritt ${eintrag.folge.schritt}/`
            + `${eintrag.folge.von} · ` : '');
      anzeige.innerHTML = `<span class="marke">${schuetze(modus)}Aktive Regel deines
        Roboters · Aktion: ${schuetze(zustand.aktionen[0] || 'warte')}</span>` +
        (quelle ? schuetze(quelle) : '<i>keine Regel — es wird gewartet</i>') +
        (eintrag && eintrag.kosten
          ? `<span class="kosten">${schuetze(eintrag.kosten)}</span>` : '');
      this.aktiveZeile = nummer ? this.regelZeile(nummer) : null;
      this.zeichneEditor();
    } else {
      anzeige.innerHTML = '<span class="marke">Startaufstellung</span>';
    }

    /* Ereignisse */
    const ereignisse = (zustand.ereignisse || []).map((e) => {
      if (e.art === 'rammen') {
        const wer = a.spieler[e.von].name;
        const wen = a.spieler[e.auf].name;
        return `<span class="ereignis rammen">${schuetze(wer)} rammt ${schuetze(wen)}`
             + `${e.geklaut ? ' und klaut ' + e.geklaut : ''}</span>`;
      }
      if (e.art === 'abliefern') {
        return `<span class="ereignis abliefern">${schuetze(a.spieler[e.wer].name)} liefert `
             + `${e.anzahl} Teile für ${e.punkte} Punkte ab</span>`;
      }
      if (e.art === 'aufnahme') {
        return `<span class="ereignis${e.sorte === 'radioaktiv' ? ' rammen' : ''}">${
          schuetze(a.spieler[e.wer].name)} nimmt ${schuetze(MuellAnzeige.name(e.sorte, a))} `
             + `(${MuellAnzeige.zahl(e.wert)}) auf</span>`;
      }
      if (e.art === 'akku_leer') {
        return `<span class="ereignis rammen">${schuetze(a.spieler[e.wer].name)}: Akku leer — `
             + `${e.teile.length} ${e.teile.length === 1 ? 'Teil' : 'Teile'} verloren</span>`;
      }
      if (e.art === 'presse') {
        return `<span class="ereignis">${schuetze(a.spieler[e.wer].name)} presst `
             + `${e.anzahl}× ${e.sorte} zu einem Ballen (${e.wert})</span>`;
      }
      if (e.art === 'zone') return '<span class="ereignis zone">Bonuszone wandert</span>';
      return '';
    }).join('');
    document.getElementById('ereignisse').innerHTML = ereignisse;
  }

  regelEintrag(nummer) {
    if (!this.regelnDerAufzeichnung || !nummer) return null;
    return this.regelnDerAufzeichnung.find((r) => r.nummer === nummer) || null;
  }

  regelZeile(nummer) {
    if (!this.regelnDerAufzeichnung) return null;
    const regel = this.regelnDerAufzeichnung.find((r) => r.nummer === nummer);
    return regel ? regel.zeile : null;
  }

  /* ------------------------------------------------------------ Dateien */

  herunterladen(dateiname, inhalt) {
    const behaelter = new Blob([inhalt], { type: 'text/plain;charset=utf-8' });
    const adresse = URL.createObjectURL(behaelter);
    const verweis = document.createElement('a');
    verweis.href = adresse;
    verweis.download = dateiname;
    document.body.appendChild(verweis);
    verweis.click();
    document.body.removeChild(verweis);
    setTimeout(() => URL.revokeObjectURL(adresse), 1000);
  }

  async speichern() {
    const ergebnis = await this.abgabeErzeugen();
    if (ergebnis) this.herunterladen(ergebnis.dateiname, ergebnis.quelle);
  }

  async abgeben() {
    const ergebnis = await this.abgabeErzeugen();
    if (!ergebnis) return;
    this.herunterladen(ergebnis.dateiname, ergebnis.quelle);
    const kasten = document.createElement('div');
    kasten.className = 'meldung gut';
    kasten.textContent = `Abgabedatei ${ergebnis.dateiname} wurde heruntergeladen. `
      + 'Gib sie so bei der Fachschaft ab.';
    this.meldungen.appendChild(kasten);
  }

  async abgabeErzeugen() {
    this.pruefungVerwerfen();
    try {
      const ergebnis = await hole('/api/abgabe', {
        quelltext: this.editor.value,
        teamname: this.teamname.value,
      });
      this.meldungenZeigen(ergebnis.programm);
      if (!ergebnis.quelle) {
        const kasten = document.createElement('div');
        kasten.className = 'meldung fehler';
        kasten.textContent = 'Solange oben Fehler stehen, lässt sich keine Datei erzeugen.';
        this.meldungen.appendChild(kasten);
        return null;
      }
      return ergebnis;
    } catch (fehler) {
      this.meldungSetzen([{ klasse: 'fehler', text: fehler.message }]);
      return null;
    }
  }

  async dateiOeffnen(ereignis) {
    const datei = ereignis.target.files[0];
    if (!datei) return;
    let inhalt;
    try {
      inhalt = await datei.text();
    } catch (fehler) {
      ereignis.target.value = '';
      this.meldungSetzen([{ klasse: 'fehler',
        text: 'Die Datei ließ sich nicht lesen.' }]);
      return;
    }
    ereignis.target.value = '';
    this.pruefungVerwerfen();
    if (inhalt.includes('PSEUDOCODE')) {
      try {
        const gelesen = await hole('/api/oeffnen', { inhalt });
        this.editor.value = gelesen.pseudocode;
        if (gelesen.name) this.teamname.value = gelesen.name;
      } catch (fehler) {
        this.meldungSetzen([{ klasse: 'fehler', text: fehler.message }]);
        return;
      }
    } else {
      this.editor.value = inhalt;
    }
    this.sichern();
    this.zeichneEditor();
    this.pruefen();
  }
}

window.Werkstatt = Werkstatt;
window.hole = hole;
window.holeGet = holeGet;
window.schuetze = schuetze;
