/* FSR-Modus: Bots einlesen, Einzelmatch, Gruppenphase, K.-o., Config, Beamer, Balance.
   Auch hier gilt: der Browser zeigt nur an. Gespielt und gerechnet wird in Python. */

const FSR_REITER = [
  ['bots', 'Roboter'],
  ['match', 'Einzelmatch'],
  ['gruppe', 'Gruppenphase'],
  ['ko', 'K.-o.-Runden'],
  ['turniere', 'Turnierarchiv'],
  ['balance', 'Massenauswertung'],
  ['config', 'Einstellungen'],
];

window.fsr = {
  angemeldet: false,
  marke: null,
  reiter: 'bots',
  daten: { abgaben: [], mitgeliefert: [] },
  config: null,
  auswahl: new Set(),
  spielfeld: null,
  wiedergabe: null,
  aufzeichnung: null,
  beamer: false,
  ko: null,
  koSchritt: 0,
  koSchritte: [],
  koSpiel: null,
  koCache: new Map(),
  koCacheFuer: null,
  koKette: Promise.resolve(),
  buehne: null,
  buehneToken: 0,
  aufbauToken: 0,
  konfetti: null,
  /* Eigener Schlüssel seit der neuen Tempo-Skala (1× = 120 ms je Tick): Ein alter
     Wert unter `fsr-tempo` hieße heute doppelt so schnell. */
  tempo: (() => {
    try { return Number(localStorage.getItem('ko-tempo')) || 1; } catch (e) { return 1; }
  })(),

  async anmelden(marke) {
    this.marke = marke;
    this.angemeldet = true;
    if (!this.vollbildVerdrahtet) {
      this.vollbildVerdrahtet = true;
      document.addEventListener('fullscreenchange',
        () => setTimeout(() => this.felderAnpassen(), 60));
      window.addEventListener('resize', () => this.felderAnpassen());
      document.addEventListener('keydown', (e) => this.koTaste(e));
    }
    /* Explizit zeigen, nicht togglen: Nach Ablauf der Marke ist FSR noch sichtbar,
       und eine Neuanmeldung würde sonst zurück in die Werkstatt schalten. */
    this.umschalten(true);
  },

  umschalten(zeigen) {
    const fsr = document.getElementById('fsr');
    const werkstatt = document.getElementById('werkstatt');
    if (zeigen === undefined) zeigen = fsr.hidden;
    fsr.hidden = !zeigen;
    werkstatt.hidden = zeigen;
    document.getElementById('unterzeile').textContent = zeigen ? 'FSR-Modus' : 'Werkstatt';
    document.getElementById('knopf-fsr').textContent = zeigen ? 'Zur Werkstatt' : 'FSR-Modus';
    /* Nur eine Wiedergabe zur Zeit: die versteckte Seite läuft sonst unsichtbar weiter. */
    if (zeigen) {
      if (window.werkstatt && window.werkstatt.wiedergabe) {
        window.werkstatt.wiedergabe.pause();
        window.werkstatt.startKnopfAktualisieren();
      }
      this.aufbauen();
    } else if (this.wiedergabe) {
      this.wiedergabe.pause();
    }
    if (!zeigen && this.buehne) this.buehne.pause();
  },

  async ruf(pfad, daten) {
    try {
      return await hole(pfad, Object.assign({ marke: this.marke }, daten || {}));
    } catch (fehler) {
      /* Nach einem Serverneustart ist die Marke unbekannt. Dann gilt die Sitzung
         als beendet, und der FSR-Knopf öffnet wieder die Anmeldung. */
      if (/anmelden/i.test(fehler.message)) {
        this.angemeldet = false;
        this.marke = null;
      }
      throw fehler;
    }
  },

  async aufbauen() {
    /* Der Reiterwechsel wirft den alten Inhalt weg. Eine noch laufende Wiedergabe
       würde danach auf Elemente zugreifen, die es nicht mehr gibt; eine noch
       laufende Hintergrundaufgabe darf ihren Bericht nicht in den neuen Reiter
       schreiben. Beide bekommen deshalb eine neue Generation. */
    this.aufbauToken += 1;
    this.buehneToken += 1;
    const token = this.aufbauToken;
    if (this.wiedergabe) this.wiedergabe.verwerfen();
    if (this.buehne) this.buehne.verwerfen();
    this.wiedergabe = null;
    this.spielfeld = null;
    this.buehne = null;
    const wurzel = document.getElementById('fsr');
    wurzel.innerHTML = `
      <div class="reiter" id="fsr-reiter"></div>
      <div id="fsr-inhalt"></div>`;
    const leiste = document.getElementById('fsr-reiter');
    FSR_REITER.forEach(([schluessel, beschriftung]) => {
      const knopf = document.createElement('button');
      knopf.textContent = beschriftung;
      knopf.className = this.reiter === schluessel ? 'aktiv' : '';
      knopf.addEventListener('click', () => { this.reiter = schluessel; this.aufbauen(); });
      leiste.appendChild(knopf);
    });
    try {
      const [bots, einstellungen] = await Promise.all([
        this.ruf('/api/fsr/bots'), this.ruf('/api/fsr/config')]);
      if (token !== this.aufbauToken) return;   // inzwischen neu aufgebaut
      this.daten = bots;
      this.config = einstellungen.config;
    } catch (fehler) {
      if (token === this.aufbauToken) {
        document.getElementById('fsr-inhalt').innerHTML =
          `<div class="karte meldung fehler">${schuetze(fehler.message)}</div>`;
      }
      return;
    }
    if (token !== this.aufbauToken) return;
    ({
      bots: () => this.zeigeBots(),
      match: () => this.zeigeMatch(),
      gruppe: () => this.zeigeGruppe(),
      ko: () => this.zeigeKo(),
      turniere: () => this.zeigeTurniere(),
      balance: () => this.zeigeBalance(),
      config: () => this.zeigeConfig(),
    })[this.reiter]();
  },

  alleBots() {
    return [
      ...this.daten.abgaben.map((b) => ({ ...b, kennung: `abgaben/${b.datei}`, quelle: 'Abgabe' })),
      ...this.daten.mitgeliefert.map((b) => ({ ...b, kennung: `bots/${b.datei}`, quelle: 'mitgeliefert' })),
    ];
  },

  auswahlListe(nurAbgaben) {
    const bots = nurAbgaben ? this.alleBots().filter((b) => b.quelle === 'Abgabe') : this.alleBots();
    return `<div class="liste">${bots.map((b) => `
      <label><input type="checkbox" value="${schuetze(b.kennung)}"
        ${this.auswahl.has(b.kennung) ? 'checked' : ''}>
        ${this.logoTile(b, 'mittel')}
        <b>${schuetze(b.name)}</b>
        <span class="klein">${schuetze(b.datei)} · ${schuetze(b.quelle)}</span></label>`).join('')}</div>`;
  },

  auswahlVerdrahten() {
    document.querySelectorAll('#fsr-inhalt .liste input').forEach((kasten) => {
      kasten.addEventListener('change', () => {
        if (kasten.checked) this.auswahl.add(kasten.value);
        else this.auswahl.delete(kasten.value);
        const anzeige = document.getElementById('auswahl-zahl');
        if (anzeige) anzeige.textContent = this.auswahl.size;
      });
    });
  },

  /* ---------------------------------------------------------------- Logos */

  /* Das Logo liegt neben der Bot-Datei und trägt denselben Stamm; der Server
     hat es beim Auflisten gefunden. Ein neu abgelegtes Logo braucht deshalb wie
     ein neuer Bot einen Reload. Ordnet Kennung, Dateiname und Teamname zu. */
  logoIndex() {
    const index = new Map();
    this.alleBots().forEach((b) => {
      if (!b.logo) return;
      const ordner = b.quelle === 'Abgabe' ? 'abgaben' : 'bots';
      const url = `/logos/${ordner}/${encodeURIComponent(b.logo)}`;
      [b.kennung, b.datei, b.name].forEach((schluessel) => {
        if (schluessel && !index.has(schluessel)) index.set(schluessel, url);
      });
    });
    return index;
  },

  logoUrl(bot) {
    /* Ein Turnierergebnis trägt Kennung und Logonamen selbst mit — dann ist der
       Weg direkt, auch wenn die Bot-Datei inzwischen umbenannt wurde. */
    if (typeof bot !== 'string' && bot && bot.kennung && bot.logo) {
      const ordner = bot.kennung.split('/')[0] === 'abgaben' ? 'abgaben' : 'bots';
      return `/logos/${ordner}/${encodeURIComponent(bot.logo)}`;
    }
    const index = this.logoIndex();
    const schluessel = typeof bot === 'string'
      ? [bot] : [bot && bot.kennung, bot && bot.datei, bot && bot.name];
    for (const wert of schluessel) {
      if (wert && index.has(wert)) return index.get(wert);
    }
    return '';
  },

  /* Quadratisches Logo oder Ersatzkachel mit dem Anfangsbuchstaben. `groesse`
     ist 'klein', 'mittel', 'gross', 'podest', 'vs' oder 'feier' — die Größen stehen
     in style.css, damit die Beamer-Ansicht sie vergrößern kann. `farbe` färbt die Ersatzkachel,
     wo die Roboterfarbe bekannt ist. `onerror` räumt ein nachträglich gelöschtes
     Bild weg, statt ein kaputtes Symbol zu zeigen. */
  logoTile(bot, groesse = 'mittel', farbe = '') {
    const name = (typeof bot === 'string' ? bot : (bot && bot.name)) || '';
    const klasse = `logo-quadrat logo-${groesse}`;
    const url = this.logoUrl(bot);
    if (url) {
      return `<img class="${klasse}" src="${url}" alt=""
        loading="lazy" onerror="this.remove()">`;
    }
    const buchstabe = (name.trim()[0] || '?').toUpperCase();
    const hintergrund = farbe ? ` style="background:${schuetze(farbe)}"` : '';
    return `<span class="${klasse} ersatz"${hintergrund}
      aria-hidden="true">${schuetze(buchstabe)}</span>`;
  },

  /* ---------------------------------------------------------------- Roboter */

  /* Der Server vergleicht jede Abgabe mit einer frischen Übersetzung ihres Pseudocodes. */
  standHinweis(stand) {
    if (stand === 'veraltet') {
      return `<br><span class="stand-warnung">⚠ mit älterer Werkstatt erzeugt — in der
        Werkstatt öffnen und neu speichern</span>`;
    }
    if (stand === 'ungueltig') {
      return `<br><span class="stand-warnung">⚠ Pseudocode lässt sich mit der jetzigen
        Werkstatt nicht mehr übersetzen</span>`;
    }
    return '';
  },

  zeigeBots() {
    const bots = this.alleBots();
    document.getElementById('fsr-inhalt').innerHTML = `
      <div class="karte">
        <h2>Abgegebene Roboter</h2>
        <p class="klein">Ordner <code>${schuetze(this.daten.abgaben_ordner)}</code>.
          Neue Abgaben einfach dort ablegen und diese Seite neu laden.</p>
        <table class="tabelle">
          <thead><tr><th>Name</th><th>Datei</th><th>Herkunft</th><th>Beschreibung</th></tr></thead>
          <tbody>${bots.map((b) => `<tr>
            <td><span class="mit-logo">${this.logoTile(b, 'mittel')}<b>${schuetze(b.name)}</b></span></td>
            <td><code>${schuetze(b.datei)}</code></td>
            <td>${schuetze(b.quelle)}${this.standHinweis(b.stand)}</td>
            <td class="klein">${schuetze(b.beschreibung || '')}</td></tr>`).join('')}</tbody>
        </table>
        <p class="klein">${this.daten.abgaben.length} Abgaben,
          ${this.daten.mitgeliefert.length} mitgelieferte Gegner.</p>
      </div>`;
  },

  /* ---------------------------------------------------------------- Match */

  zeigeMatch() {
    document.getElementById('fsr-inhalt').innerHTML = `
      <div class="fsr-gitter">
        <div class="karte">
          <h2>Einzelmatch</h2>
          <p class="klein">2 bis 4 Roboter auswählen (<span id="auswahl-zahl">${this.auswahl.size}</span> gewählt).</p>
          ${this.auswahlListe(false)}
          <div class="werkzeugleiste">
            <label class="feld">Seed <input id="match-seed" type="number" value="1" min="0"></label>
            <label class="feld">Ticks <input id="match-ticks" type="number" value="" placeholder="Standard"></label>
            <button id="match-start" class="haupt">Match spielen</button>
            <button id="beamer-knopf" class="flach">Beamer-Ansicht</button>
          </div>
          <div id="match-meldung" class="meldungen"></div>
        </div>
        <div class="karte" id="fsr-feld-karte">
          <div class="spielfeld-huelle"><canvas id="fsr-feld" width="720" height="720"
            aria-label="Spielfeld"></canvas></div>
          <div class="wiedergabe">
            <button id="fsr-start" class="rund" aria-label="Abspielen">▶</button>
            <button id="fsr-zurueck" class="rund" aria-label="Ein Tick zurück">⏴</button>
            <button id="fsr-vor" class="rund" aria-label="Ein Tick vor">⏵</button>
            <input id="fsr-schieber" type="range" min="0" max="0" value="0">
            <span class="tickanzeige" id="fsr-tick">0 / 0</span>
            <label class="feld">Tempo <select id="fsr-tempo">
              <option value="1" selected>1×</option><option value="2">2×</option>
              <option value="4">4×</option><option value="8">8×</option>
              <option value="24">24×</option></select></label>
            <button id="fsr-vollbild" class="flach" title="Vollbild">⛶ Vollbild</button>
          </div>
          <div id="fsr-punkte" class="punktestand"></div>
        </div>
      </div>`;
    this.auswahlVerdrahten();
    this.spielfeld = new Spielfeld(document.getElementById('fsr-feld'));
    this.spielfeld.beamer = this.beamer;
    this.spielfeld.werteZeigen = true;
    this.spielfeld.pfeileZeigen = true;
    this.wiedergabe = new Wiedergabe(this.spielfeld, (i) => this.rahmen(i));
    this.wiedergabe.tempo = 1;
    this.wiedergabe.aufEnde = () => this.fsrKnoepfe();

    document.getElementById('match-start').addEventListener('click', () => this.matchSpielen());
    document.getElementById('beamer-knopf').addEventListener('click', () => this.beamerUmschalten());
    document.getElementById('fsr-start').addEventListener('click', () => {
      this.wiedergabe.umschalten();
      this.fsrKnoepfe();
    });
    document.getElementById('fsr-vor').addEventListener('click', () => {
      this.wiedergabe.schritt(1);
      this.fsrKnoepfe();
    });
    document.getElementById('fsr-zurueck').addEventListener('click', () => {
      this.wiedergabe.schritt(-1);
      this.fsrKnoepfe();
    });
    document.getElementById('fsr-schieber').addEventListener('input', (e) => {
      this.wiedergabe.pause();
      this.wiedergabe.springe(Number(e.target.value));
      this.fsrKnoepfe();
    });
    document.getElementById('fsr-tempo').addEventListener('change', (e) => {
      this.wiedergabe.tempo = Number(e.target.value);
    });
    document.getElementById('fsr-vollbild').addEventListener('click',
      () => this.vollbildUmschalten('fsr-feld-karte'));
    if (this.aufzeichnung) this.aufzeichnungZeigen(this.aufzeichnung);
  },

  async matchSpielen() {
    const knopf = document.getElementById('match-start');
    const bots = [...this.auswahl];
    const meldung = document.getElementById('match-meldung');
    if (bots.length < 2 || bots.length > 4) {
      meldung.innerHTML = '<div class="meldung fehler">Bitte 2 bis 4 Roboter auswählen.</div>';
      return;
    }
    meldung.innerHTML = '<div class="meldung lade">Das Match läuft …</div>';
    const token = this.aufbauToken;
    knopf.disabled = true;
    try {
      const ticks = Number(document.getElementById('match-ticks').value) || undefined;
      const antwort = await this.ruf('/api/fsr/match', {
        bots, seed: Number(document.getElementById('match-seed').value) || 0, ticks,
      });
      if (token !== this.aufbauToken || !this.wiedergabe) return;
      meldung.innerHTML = '';
      this.aufzeichnungZeigen(antwort.aufzeichnung);
    } catch (fehler) {
      if (token === this.aufbauToken) {
        meldung.innerHTML = `<div class="meldung fehler">${schuetze(fehler.message)}</div>`;
      }
    } finally {
      knopf.disabled = false;
    }
  },

  aufzeichnungZeigen(aufzeichnung) {
    this.aufzeichnung = aufzeichnung;
    document.getElementById('fsr-schieber').max = aufzeichnung.ticks.length;
    this.wiedergabe.laden(aufzeichnung);
    this.wiedergabe.start();
    this.felderAnpassen();
    this.fsrKnoepfe();
    const kaputt = (aufzeichnung.bots || []).filter((b) => b.tot || b.fehler.length);
    if (kaputt.length) {
      document.getElementById('match-meldung').innerHTML = kaputt.map((b) =>
        `<div class="meldung hinweis">${schuetze(b.name)}: ${b.tot ? 'lief nicht' : 'Fehler'} —
         ${schuetze((b.fehler[0] || '').split('\n').filter(Boolean).pop() || '')}</div>`).join('');
    }
  },

  fsrKnoepfe() {
    const start = document.getElementById('fsr-start');
    if (start && this.wiedergabe) {
      start.textContent = this.wiedergabe.laeuft ? '❚❚' : '▶';
    }
  },

  rahmen(index) {
    const a = this.aufzeichnung;
    const schieber = document.getElementById('fsr-schieber');
    if (!a || !schieber) {
      if (this.wiedergabe) this.wiedergabe.pause();
      return;
    }
    schieber.value = index;
    document.getElementById('fsr-tick').textContent = `${index} / ${a.ticks.length}`;
    const zustand = index <= 0 ? a.start : a.ticks[index - 1];
    const langsamAb = this.config && this.config.akku
      ? this.config.akku.langsam_ab : null;
    document.getElementById('fsr-punkte').innerHTML = zustand.roboter.map((r, i) => {
      const s = a.spieler[i];
      const akku = Math.max(0, Math.min(100, r.akku));
      return `<div class="spieler-kachel" style="border-left-color:${schuetze(s.farbe)}">
        <div class="name"><span class="mit-logo">${
          this.logoTile(s, 'gross', s.farbe)}<span>${schuetze(s.name)}</span></span></div>
        <div class="punkte">${r.punkte}</div>
        <div class="zeile"><span>Akku ${r.akku}${r.laedt > 0 ? ' ⚡ lädt' : ''}</span></div>
        <div class="balken${akku < langsamAb ? ' leer' : ''}"><div style="width:${akku}%"></div></div>
        ${MuellAnzeige.kachelInhalt(a, r, i, index)}
      </div>`;
    }).join('');
  },

  beamerUmschalten() {
    this.beamer = !this.beamer;
    document.body.classList.toggle('beamer', this.beamer);
    if (this.spielfeld) {
      this.spielfeld.beamer = this.beamer;
      this.wiedergabe.zeichne();
    }
    if (this.buehne) {
      this.buehne.duelle.forEach((d) => { d.spielfeld.beamer = this.beamer; });
      this.buehne.zeichne();
    }
    const beschriftung = this.beamer ? 'Werkstatt-Farben' : 'Beamer-Ansicht';
    ['beamer-knopf', 'buehne-beamer'].forEach((id) => {
      const knopf = document.getElementById(id);
      if (knopf) knopf.textContent = beschriftung;
    });
  },

  /* Vollbild für die Karte, in der gerade gespielt wird — nicht für die ganze
     Seite: Header, Reiter und Auswahl sollen verschwinden. Konfetti und
     Siegerehrung liegen deshalb innerhalb der Karte bzw. ziehen mit ihr um. */
  vollbildUmschalten(kennung) {
    if (document.fullscreenElement) {
      if (document.exitFullscreen) document.exitFullscreen().catch(() => {});
      return;
    }
    const ziel = document.getElementById(kennung || 'ko-buehne-karte');
    if (ziel && ziel.requestFullscreen) ziel.requestFullscreen().catch(() => {});
  },

  /* Wie viel Platz bleibt dem Feld im Vollbild-Kasten? Gemessen wird vom Rand des
     Kastens bis zum Feld und alles, was darunter noch steht (Bedienleiste,
     Punktestand). */
  platzImVollbild(kasten, huelle) {
    const kastenRect = kasten.getBoundingClientRect();
    const huelleRect = huelle.getBoundingClientRect();
    const oben = huelleRect.top - kastenRect.top + kasten.scrollTop;
    return {
      breite: Math.max(160, huelle.clientWidth),
      hoehe: Math.max(160, kasten.clientHeight - oben
        - this.geschwisterHoehe(huelle, kasten) - 24),
    };
  },

  /* Die Höhe dessen, was nach `start` noch im Vollbild-Kasten steht. Über
     `scrollHeight` gemessen ging das schief: Der Wert fällt nie unter die Höhe
     des Kastens — bei einer einzelnen Finalpartie sah es aus, als stünde der
     halbe Schirm voll, und das Feld schrumpfte auf die Mindestgröße. */
  geschwisterHoehe(start, kasten) {
    let summe = 0;
    let knoten = start;
    while (knoten && knoten !== kasten) {
      let bruder = knoten.nextElementSibling;
      while (bruder) {
        const stil = getComputedStyle(bruder);
        if (stil.display !== 'none' && stil.position !== 'fixed') {
          summe += bruder.offsetHeight + (parseFloat(stil.marginTop) || 0)
            + (parseFloat(stil.marginBottom) || 0);
        }
        bruder = bruder.nextElementSibling;
      }
      knoten = knoten.parentElement;
    }
    return summe;
  },

  /* Im Vollbild bekommen die Spielfelder ihre Grenzen gesetzt, sonst werden sie
     wieder freigelassen. Beim Verlassen stellt das die alte Breitenregel her. */
  felderAnpassen() {
    const kasten = document.fullscreenElement;
    if (this.spielfeld) {
      const huelle = this.spielfeld.canvas.closest('.spielfeld-huelle');
      if (kasten && huelle && kasten.contains(huelle)) {
        const masse = this.platzImVollbild(kasten, huelle);
        this.spielfeld.breitePlatz = masse.breite;
        this.spielfeld.hoehePlatz = masse.hoehe;
      } else {
        this.spielfeld.breitePlatz = 0;
        this.spielfeld.hoehePlatz = 0;
      }
      if (this.spielfeld.groesseAnpassen() && this.wiedergabe) this.wiedergabe.zeichne();
    }
    if (this.buehne) {
      const raster = document.getElementById('buehne-raster');
      const arena = document.getElementById('ko-arena');
      if (arena) {
        const masse = this.arenaPlatz(arena);
        this.buehne.platzSetzen(masse.breite, masse.hoehe);
      } else if (kasten && raster && kasten.contains(raster)) {
        const masse = this.platzImVollbild(kasten, raster);
        this.buehne.platzSetzen(masse.breite, masse.hoehe);
      } else {
        this.buehne.platzSetzen(0, 0);
      }
      this.buehne.zeichne();
    }
  },

  /* Platz für das Feld in der K.-o.-Arena: die ganze Höhe bis zum unteren Rand
     (Fenster oder Vollbild), in der Breite abzüglich der beiden Seitenspalten. */
  arenaPlatz(arena) {
    const kasten = document.fullscreenElement;
    const rechteck = arena.getBoundingClientRect();
    const oben = kasten ? rechteck.top : rechteck.top + window.scrollY;
    /* Unten bleibt Platz für Innenabstand der Karte und Seitenrand — ohne Vollbild
       soll die Seite nicht scrollen. */
    const unten = kasten ? kasten.getBoundingClientRect().bottom - 18 : window.innerHeight - 40;
    const spalte = Math.max(170, rechteck.width * 0.17);
    const luecke = parseFloat(getComputedStyle(arena).columnGap) || 24;
    /* 20 Pixel für Innenabstand und Rahmen der Feldkarte. */
    return {
      breite: Math.max(220, rechteck.width - 2 * spalte - 2 * luecke - 20),
      hoehe: Math.max(220, unten - oben - 20),
    };
  },

  konfettiHolen() {
    if (!this.konfetti) {
      this.konfetti = new Konfetti();
      const ziel = document.fullscreenElement || document.body;
      if (this.konfetti.canvas.parentElement !== ziel) ziel.appendChild(this.konfetti.canvas);
      document.addEventListener('fullscreenchange', () => {
        const neu = document.fullscreenElement || document.body;
        if (this.konfetti.canvas.parentElement !== neu) neu.appendChild(this.konfetti.canvas);
      });
    }
    return this.konfetti;
  },

  /* ---------------------------------------------------------------- Aufgaben */

  async aufgabeVerfolgen(id, anzeige, fertig, scheitern) {
    const token = this.aufbauToken;
    const takt = async () => {
      if (token !== this.aufbauToken) return;   // Reiter wurde gewechselt
      let eintrag;
      try {
        eintrag = await this.ruf('/api/fsr/aufgabe', { id });
      } catch (fehler) {
        if (token === this.aufbauToken) {
          anzeige.innerHTML = `<div class="meldung fehler">${schuetze(fehler.message)}</div>`;
          if (scheitern) scheitern();
        }
        return;
      }
      if (token !== this.aufbauToken) return;
      if (!eintrag.fertig) {
        const teil = eintrag.gesamt ? ` (${eintrag.fortschritt}/${eintrag.gesamt})` : '';
        anzeige.innerHTML = `<div class="meldung lade">${
          schuetze(eintrag.beschreibung)} läuft …${schuetze(teil)}</div>`;
        setTimeout(takt, 700);
        return;
      }
      if (eintrag.fehler) {
        anzeige.innerHTML = `<div class="meldung fehler">Abgebrochen:<br><pre>${
          schuetze(eintrag.fehler)}</pre></div>`;
        if (scheitern) scheitern();
        return;
      }
      anzeige.innerHTML = '';
      fertig(eintrag.ergebnis);
    };
    takt();
  },

  /* ---------------------------------------------------------------- Gruppe */

  zeigeGruppe() {
    document.getElementById('fsr-inhalt').innerHTML = `
      <div class="fsr-gitter">
        <div class="karte">
          <h2>Gruppenphase</h2>
          <p class="klein">Genau ${this.config.turnier.gruppen_groesse} Roboter wählen
            (<span id="auswahl-zahl">${this.auswahl.size}</span> gewählt).
            Sie spielen gemeinsam auf einem Feld, mehrere Runden mit wechselnden Seeds.
            Punkte je Runde nach Platz: ${schuetze(this.config.turnier.punkte_je_platz.join(' · '))}.
            Bei Gleichstand entscheiden Siege, dann Spielpunkte.</p>
          ${this.auswahlListe(false)}
          <div class="werkzeugleiste">
            <label class="feld">Seed <input id="gruppe-seed" type="number" value="1" min="0"></label>
            <button id="gruppe-start" class="haupt">Gruppe spielen</button>
          </div>
          <div id="gruppe-meldung" class="meldungen"></div>
        </div>
        <div class="karte"><h2>Tabelle</h2><div id="gruppe-tabelle" class="klein">
          Noch nichts gespielt.</div></div>
      </div>`;
    this.auswahlVerdrahten();
    document.getElementById('gruppe-start').addEventListener('click', async () => {
      const knopf = document.getElementById('gruppe-start');
      const anzeige = document.getElementById('gruppe-meldung');
      const token = this.aufbauToken;
      knopf.disabled = true;
      try {
        const antwort = await this.ruf('/api/fsr/gruppe', {
          bots: [...this.auswahl],
          seed: Number(document.getElementById('gruppe-seed').value) || 0,
        });
        if (token !== this.aufbauToken) return;
        this.aufgabeVerfolgen(antwort.aufgabe, anzeige, (e) => this.gruppeZeigen(e));
      } catch (fehler) {
        if (token === this.aufbauToken) {
          anzeige.innerHTML = `<div class="meldung fehler">${schuetze(fehler.message)}</div>`;
        }
      } finally {
        knopf.disabled = false;
      }
    });
  },

  gruppeZeigen(ergebnis) {
    document.getElementById('gruppe-tabelle').innerHTML = this.gruppeTabelleHtml(ergebnis);
  },

  gruppeTabelleHtml(ergebnis) {
    const zeilen = ergebnis.platzierung.map((index, platz) => {
      const e = ergebnis.tabelle[index];
      return `<tr class="${platz === 0 ? 'hervor' : ''}">
        <td>${platz + 1}.</td>
        <td><span class="mit-logo">${this.logoTile(e, 'mittel')}<b>${schuetze(e.name)}</b></span></td>
        <td class="zahl">${e.punkte}</td><td class="zahl">${e.siege}</td>
        <td class="zahl">${e.gesamtpunkte}</td></tr>`;
    }).join('');
    return `
      <table class="tabelle">
        <thead><tr><th></th><th>Roboter</th><th class="zahl">Tabellenpunkte</th>
          <th class="zahl">Siege</th><th class="zahl">Spielpunkte</th></tr></thead>
        <tbody>${zeilen}</tbody></table>
      <p class="klein">${ergebnis.partien.length} Runden gespielt.${
        ergebnis.gespeichert ? ` Gespeichert als <code>${
          schuetze(ergebnis.gespeichert)}</code>.` : ''}</p>`;
  },

  /* ---------------------------------------------------------------- K.-o. */

  zeigeKo() {
    /* Ein Turnier ist bereits gespielt: die Bühne zeigen, nicht wieder die Auswahl. */
    if (this.ko) {
      this.koZeigen(this.ko, { schritt: this.koSchritt });
      return;
    }
    document.getElementById('fsr-inhalt').innerHTML = `
      <div class="karte">
        <h2>K.-o.-Runden</h2>
        <p class="klein">Gespielt wird im Baum bis zum Finale, dazu ein Spiel um Platz 3.
          Fehlen Roboter bis zur nächsten vollen Größe (16, 8, 4), bekommen die ersten der
          Setzliste ein Freilos. Mit <b>Auslosen</b> bestimmt der Zufall aus dem Seed die
          Setzliste, sonst die Reihenfolge, in der hier angeklickt wird. Unentschieden
          wird bis zu ${this.config.turnier.gleichstand_wiederholungen}-mal mit dem
          nächsten Seed wiederholt, danach entscheidet die Setzung.
          (<span id="auswahl-zahl">${this.auswahl.size}</span> gewählt)</p>
        ${this.auswahlListe(false)}
        <div class="werkzeugleiste">
          <label class="feld">Seed <input id="ko-seed" type="number"
            value="${this.koSeedWuerfeln()}" min="0"></label>
          <button id="ko-wuerfeln" class="flach" title="Neuen Seed würfeln">🎲</button>
          <label class="feld"><input type="checkbox" id="ko-losen" checked> Auslosen</label>
          <button id="ko-start" class="haupt">Turnier starten</button>
        </div>
        <div id="ko-meldung" class="meldungen"></div>
      </div>`;
    this.auswahlVerdrahten();
    document.getElementById('ko-wuerfeln').addEventListener('click', () => {
      document.getElementById('ko-seed').value = this.koSeedWuerfeln();
    });
    document.getElementById('ko-start').addEventListener('click', async () => {
      const knopf = document.getElementById('ko-start');
      const anzeige = document.getElementById('ko-meldung');
      const token = this.aufbauToken;
      const seed = Number(document.getElementById('ko-seed').value) || 0;
      const losen = document.getElementById('ko-losen').checked;
      knopf.disabled = true;
      try {
        const antwort = await this.ruf('/api/fsr/ko', {
          bots: [...this.auswahl], seed, auslosen: losen,
        });
        if (token !== this.aufbauToken) return;
        this.koVorspann(antwort.aufgabe, seed, losen);
      } catch (fehler) {
        if (token === this.aufbauToken) {
          anzeige.innerHTML = `<div class="meldung fehler">${schuetze(fehler.message)}</div>`;
          knopf.disabled = false;
        }
      }
    });
  },

  /* Der Seed ist eine Eingabe wie der Name eines Teams, keine Spiellogik — deshalb
     darf `Math.random` ihn vorschlagen. Was er im Spiel bewirkt, rechnet Python
     mit dem eigenen Zufallsgenerator. */
  koSeedWuerfeln() {
    return 100000 + Math.floor(Math.random() * 900000);
  },

  /* Eine Pause, die „Zum Ende" abkürzen kann: `spiel.springen` lässt sie sofort
     enden, `spiel.weiter()` beendet die laufende. */
  warten(ms, spiel) {
    return new Promise((fertig) => {
      if (spiel && spiel.springen) { fertig(); return; }
      const uhr = setTimeout(fertig, ms);
      if (spiel) spiel.weiter = () => { clearTimeout(uhr); fertig(); };
    });
  },

  /* Vorspann, während Python das Turnier ausspielt (bei 16 Teams einige Sekunden):
     Der Würfel rollt, die Ziffern des Seeds laufen durch und bleiben eine nach der
     anderen stehen. Danach geht es mit der Auslosung im Turnierbaum weiter. */
  async koVorspann(aufgabe, seed, losen) {
    this.ko = null;
    this.koCacheFuer = null;
    this.koGeruest();
    const token = ++this.buehneToken;
    const flaeche = document.getElementById('ko-flaeche');
    const ziffern = String(seed).split('');
    flaeche.innerHTML = `
      <div class="ko-vorspann">
        <div class="ko-vs-runde">${losen ? 'Auslosung' : 'Turnier'}</div>
        <div class="ko-vs-info" id="ko-vorspann-info">Der Seed wird gewürfelt</div>
        <div class="ko-wuerfel" id="ko-wuerfel">🎲</div>
        <div class="ko-seed">${ziffern.map(() => '<span>0</span>').join('')}</div>
        <div class="ko-fortschritt" id="ko-fortschritt"></div>
        <div class="ko-aktion" id="ko-vorspann-aktion"></div>
      </div>`;
    let ergebnis = null;
    let gescheitert = false;
    const fertig = new Promise((aufloesen) => {
      this.aufgabeVerfolgen(aufgabe, document.getElementById('ko-fortschritt'),
        (e) => { ergebnis = e; aufloesen(); },
        () => { gescheitert = true; aufloesen(); });
    });
    const stellen = [...flaeche.querySelectorAll('.ko-seed span')];
    const wirbel = setInterval(() => stellen.forEach((stelle) => {
      if (!stelle.classList.contains('steht')) stelle.textContent = Math.floor(Math.random() * 10);
    }), 70);
    await this.warten(1300);
    for (let i = 0; i < stellen.length; i++) {
      if (token !== this.buehneToken) break;
      stellen[i].textContent = ziffern[i];
      stellen[i].classList.add('steht');
      await this.warten(280);
    }
    clearInterval(wirbel);
    if (token !== this.buehneToken) return;
    document.getElementById('ko-wuerfel').classList.add('steht');
    document.getElementById('ko-vorspann-info').textContent = `Seed ${seed}`;
    await fertig;
    if (token !== this.buehneToken) return;
    if (gescheitert || !ergebnis) {
      document.getElementById('ko-vorspann-aktion').appendChild(
        this.hauptknopf('Zurück zur Auswahl', () => this.zeigeKo()));
      return;
    }
    await this.warten(700);
    if (token !== this.buehneToken) return;
    this.koZeigen(ergebnis, { auslosung: true });
  },

  /* Die Show nach dem gespielten Turnier: Turnierbaum, dann jede Partie einzeln
     (VS-Bild, Spiel, Sieger), nach jeder Runde wieder der Baum, am Ende Spiel um
     Platz 3, Finale und Siegertreppe. Weiter geht es nur auf Klick oder Taste.

     Das Turnier ist in Python längst entschieden. Für jede Partie spielt Python
     sie mit ihrem Seed und ihrer Länge noch einmal nach und liefert die
     Aufzeichnung; der Browser zeigt sie nur und verrät vorher nichts. */
  koZeigen(ergebnis, optionen = {}) {
    if (this.koCacheFuer !== ergebnis) {
      this.koCacheFuer = ergebnis;
      this.koCache = new Map();
      this.koKette = Promise.resolve();
      this.koSchritt = 0;
    }
    this.ko = ergebnis;
    this.koSchritte = this.koAblauf(ergebnis);
    this.koGeruest();
    const start = optionen.schritt !== undefined ? optionen.schritt : this.koSchritt;
    this.koSchrittZeigen(Math.max(0, Math.min(start, this.koSchritte.length - 1)),
                         { auslosung: optionen.auslosung });
  },

  /* Die Karte der Bühne: oben eine schmale Leiste (Wiedergabe links, Runde und
     Spiel in der Mitte, Tempo/Beamer/Vollbild rechts), darunter die Fläche, auf
     der die Schritte der Show wechseln. */
  koGeruest() {
    if (this.buehne) { this.buehne.verwerfen(); this.buehne = null; }
    this.koSpiel = null;
    /* Steht die Karte schon (Vorspann → Turnierbaum), bleibt sie stehen: Würde sie
       ersetzt, verließe der Browser das Vollbild, das an ihr hängt. */
    if (document.getElementById('ko-buehne-karte')) return;
    document.getElementById('fsr-inhalt').innerHTML = `
      <div class="karte" id="ko-buehne-karte">
        <div class="buehne-kopf">
          <div class="werkzeugleiste buehne-knoepfe" id="buehne-steuerung" hidden>
            <button id="buehne-start" class="rund haupt" title="Abspielen / Pause (Leertaste)">▶</button>
            <input id="buehne-schieber" type="range" min="0" max="0" value="0">
            <span class="tickanzeige" id="buehne-tick">0 / 0</span>
            <button id="buehne-ende" class="flach" title="Direkt zum Endstand">Zum Ende ⏭</button>
          </div>
          <div class="buehne-info" id="buehne-info"></div>
          <div class="werkzeugleiste buehne-knoepfe">
            <label class="feld"><span class="buehne-tempo-wort">Tempo</span> <select id="buehne-tempo">
              ${[1, 2, 4, 8, 16, 24].map((t) => `<option value="${t}"${
                t === this.tempo ? ' selected' : ''}>${t}×</option>`).join('')}</select></label>
            <button id="buehne-beamer" class="flach">${
              this.beamer ? 'Werkstatt-Farben' : 'Beamer-Ansicht'}</button>
            <button id="buehne-vollbild" class="flach" title="Vollbild">⛶</button>
            <button id="buehne-neu" class="flach">Neues Turnier</button>
          </div>
        </div>
        <div id="ko-flaeche" class="ko-flaeche"></div>
      </div>`;
    this.buehneVerdrahten();
  },

  /* Die Reihenfolge der Show. Freilose spielen nicht, sie stehen nur im Baum. Vor
     jeder Runde der Baum; in der letzten Runde kommt das Spiel um Platz 3 vor dem
     Finale. Zum Schluss Siegertreppe und der fertige Baum. */
  koAblauf(ergebnis) {
    const schritte = [];
    const runden = ergebnis.runden || [];
    runden.forEach((runde, r) => {
      const partien = runde.partien.filter((p) => !p.freilos);
      const liste = [];
      if (r === runden.length - 1 && ergebnis.spiel_um_platz_3) {
        liste.push({ partie: ergebnis.spiel_um_platz_3, name: 'Spiel um Platz 3' });
      }
      partien.forEach((p, i) => liste.push({
        partie: p, name: runde.name,
        info: partien.length > 1 ? `Spiel ${i + 1} von ${partien.length}` : '',
      }));
      if (!liste.length) return;
      schritte.push({ art: 'baum', bis: r, naechste: liste[0].name, vorher: r > 0 ? runden[r - 1].name : '' });
      liste.forEach((e) => schritte.push({ art: 'partie', ...e }));
    });
    schritte.push({ art: 'podest' });
    schritte.push({ art: 'baum', bis: runden.length + 1 });
    return schritte;
  },

  buehneVerdrahten() {
    const karte = document.getElementById('ko-buehne-karte');
    /* Mit der Maus geklickte Knöpfe sofort wieder loslassen: Sonst löst die
       Leertaste des Clickers beim nächsten Mal „Vollbild" oder „Beamer" aus. */
    karte.addEventListener('click', (e) => {
      const knopf = e.target.closest('button');
      if (knopf && e.detail > 0) knopf.blur();
    });
    document.getElementById('buehne-start').addEventListener('click', () => {
      if (!this.buehne || !this.buehne.duelle.length) return;
      if (this.buehne.beendet) this.spielZuruecksetzen();
      this.buehne.umschalten();
      this.buehneKnoepfe();
    });
    document.getElementById('buehne-schieber').addEventListener('input', (e) => {
      if (!this.buehne) return;
      this.spielZuruecksetzen();
      this.buehne.pause();
      this.buehne.springe(Number(e.target.value));
      this.buehneKnoepfe();
    });
    document.getElementById('buehne-ende').addEventListener('click', () => {
      /* Läuft schon die Abrechnung, springt „Zum Ende" auch über sie hinweg. */
      const spiel = this.koSpiel;
      if (spiel && spiel.phase === 'abrechnung') {
        spiel.springen = true;
        if (spiel.weiter) spiel.weiter();
      } else if (this.buehne) {
        this.buehne.zumEnde();
      }
    });
    document.getElementById('buehne-tempo').addEventListener('change', (e) => {
      this.tempoSetzen(Number(e.target.value));
    });
    document.getElementById('buehne-beamer').addEventListener('click', () => this.beamerUmschalten());
    document.getElementById('buehne-vollbild').addEventListener('click',
      () => this.vollbildUmschalten('ko-buehne-karte'));
    document.getElementById('buehne-neu').addEventListener('click', () => {
      if (this.buehne) { this.buehne.verwerfen(); this.buehne = null; }
      this.buehneToken += 1;
      this.ko = null;
      this.koCacheFuer = null;
      this.koSchritt = 0;
      if (document.fullscreenElement && document.exitFullscreen) {
        document.exitFullscreen().catch(() => {});
      }
      this.zeigeKo();
    });
  },

  /* Das Tempo gilt für alle folgenden Partien, auch nach einem Neuladen der Seite. */
  tempoSetzen(tempo) {
    this.tempo = tempo || 1;
    try { localStorage.setItem('ko-tempo', String(this.tempo)); } catch (e) { /* egal */ }
    if (this.buehne) this.buehne.tempo = this.tempo;
  },

  /* Weiter mit Tastatur oder Präsentations-Clicker (die senden →, Bild↓ oder
     Leertaste). Ausgelöst wird der eine Hauptknopf des Bildschirms. Läuft gerade
     ein Spiel, gibt es keinen — dann hält die Leertaste an. */
  koTaste(e) {
    if (this.reiter !== 'ko' || !this.ko || e.altKey || e.ctrlKey || e.metaKey) return;
    const karte = document.getElementById('ko-buehne-karte');
    const fsr = document.getElementById('fsr');
    if (!karte || !fsr || fsr.hidden) return;
    if (!['Enter', ' ', 'ArrowRight', 'PageDown'].includes(e.key)) return;
    const ziel = e.target;
    if (ziel && ziel.closest && ziel.closest('input, select, textarea')) return;
    /* Ein mit Tab angesteuerter Knopf reagiert auf Enter und Leertaste selbst. */
    if (ziel && ziel.closest && ziel.closest('button') && (e.key === 'Enter' || e.key === ' ')) {
      return;
    }
    e.preventDefault();
    const knopf = karte.querySelector('[data-aktion]:not([disabled])');
    if (knopf) {
      knopf.click();
    } else if (e.key === ' ' && this.buehne && this.buehne.duelle.length
               && !document.getElementById('buehne-steuerung').hidden) {
      this.buehne.umschalten();
      this.buehneKnoepfe();
    }
  },

  buehneKnoepfe() {
    const start = document.getElementById('buehne-start');
    if (start && this.buehne) start.textContent = this.buehne.laeuft ? '❚❚' : '▶';
  },

  buehneRahmen(index, laenge) {
    const schieber = document.getElementById('buehne-schieber');
    if (!schieber) return;
    schieber.max = laenge;
    schieber.value = index;
    document.getElementById('buehne-tick').textContent = `${index} / ${laenge}`;
  },

  /* Einen Schritt der Show zeigen. Jeder Schritt bekommt eine neue Generation,
     damit Countdown, Nachladen oder Feier eines alten Schritts nicht in den
     neuen hineinplatzen. */
  koSchrittZeigen(index, optionen = {}) {
    const schritt = this.koSchritte[index];
    const flaeche = document.getElementById('ko-flaeche');
    if (!schritt || !flaeche) return;
    this.koSchritt = index;
    const token = ++this.buehneToken;
    if (this.buehne) { this.buehne.verwerfen(); this.buehne = null; }
    this.koSpiel = null;
    document.getElementById('buehne-steuerung').hidden = true;
    this.infoSetzen('');
    flaeche.innerHTML = '';
    if (schritt.art === 'baum') this.baumZeigen(schritt, index, token, optionen.auslosung);
    else if (schritt.art === 'partie') this.vsZeigen(schritt, index, token);
    else this.podestZeigen(index, token);
  },

  /* Ein Hauptknopf je Bildschirm, markiert mit `data-aktion` — den löst auch die
     Tastatur aus. Er sperrt sich beim ersten Klick, ein Doppelklick überspringt
     sonst einen Schritt. */
  hauptknopf(text, aktion) {
    const knopf = document.createElement('button');
    knopf.className = 'haupt ko-hauptknopf';
    knopf.dataset.aktion = '1';
    knopf.textContent = text;
    knopf.addEventListener('click', () => {
      if (knopf.disabled) return;
      knopf.disabled = true;
      aktion();
    });
    return knopf;
  },

  baumZeigen(schritt, index, token, auslosung = false) {
    const flaeche = document.getElementById('ko-flaeche');
    const ko = this.ko;
    const ende = !schritt.naechste;
    auslosung = auslosung && !ende && Array.isArray(ko.setzliste);
    let unterzeile;
    if (ende) unterzeile = 'Endstand';
    else if (schritt.vorher) unterzeile = `nach dem ${schritt.vorher}`;
    else unterzeile = ko.ausgelost ? `ausgelost · Seed ${ko.seed}` : `Setzliste · Seed ${ko.seed}`;
    flaeche.innerHTML = `
      <div class="ko-baumansicht">
        <div class="ko-ueberschrift">
          <div class="buehne-titel">${auslosung && ko.ausgelost ? 'Auslosung' : 'Turnierbaum'}</div>
          <div class="ko-unterzeile">${schuetze(unterzeile)}</div>
        </div>
        ${this.koBaumHtml(ko, schritt.bis)}
        <div class="ko-aktion"></div>
      </div>`;
    const aktion = flaeche.querySelector('.ko-aktion');
    if (auslosung) this.auslosungZeigen(flaeche, aktion);
    if (ende) {
      aktion.appendChild(this.hauptknopf('Zur Siegerehrung', () => this.koSchrittZeigen(index - 1)));
    } else {
      aktion.appendChild(this.hauptknopf(`${schritt.naechste} starten ▶`,
        () => this.koSchrittZeigen(index + 1)));
      /* Die erste Partie schon nachspielen lassen, während alle auf den Baum schauen. */
      const folgend = this.koSchritte[index + 1];
      if (folgend && folgend.art === 'partie') this.aufzeichnungHolen(folgend.partie);
    }
  },

  /* Die Teams fliegen in der Reihenfolge der Setzliste auf ihre Plätze im Baum,
     Freilose zuletzt; erst dann erscheint der Startknopf. */
  auslosungZeigen(flaeche, aktion) {
    const baum = flaeche.querySelector('.turnierbaum');
    if (!baum) return;
    const rang = new Map();
    this.ko.setzliste.forEach((bot, i) => rang.set(bot.kennung || bot.name, i));
    const zeilen = [...baum.querySelectorAll('.zeile[data-bot]')];
    const normal = zeilen.filter((z) => !z.closest('.freilos'));
    const freilos = zeilen.filter((z) => z.closest('.freilos'));
    const takt = 160;
    normal.sort((x, y) => (rang.get(x.dataset.bot) ?? 99) - (rang.get(y.dataset.bot) ?? 99));
    normal.forEach((zeile, i) => { zeile.style.animationDelay = `${300 + i * takt}ms`; });
    freilos.forEach((zeile, i) => {
      zeile.style.animationDelay = `${700 + (normal.length + i) * takt}ms`;
    });
    baum.classList.add('auslosung');
    aktion.style.animationDelay = `${900 + zeilen.length * takt}ms`;
    aktion.classList.add('nach-auslosung');
  },

  /* Die Aufzeichnung einer Partie, einmal geholt und gemerkt. Die Abrufe laufen
     nacheinander in einer Kette: Nur eine Partie zur Zeit wird auf dem Server
     nachgespielt, damit sich die Bot-Prozesse kein Zeitlimit wegnehmen. */
  aufzeichnungHolen(p) {
    if (this.koCache.has(p)) return this.koCache.get(p);
    const versprechen = this.koKette.then(async () => {
      if (!(p.a && p.a.kennung && p.b && p.b.kennung)) {
        throw new Error('Für dieses Turnier fehlen die Bot-Kennungen.');
      }
      const letzter = p.spiele && p.spiele.length ? p.spiele[p.spiele.length - 1] : null;
      const antwort = await this.ruf('/api/fsr/match', {
        bots: [p.a.kennung, p.b.kennung], seed: letzter ? letzter.seed : p.seed, ticks: p.ticks,
      });
      return antwort.aufzeichnung;
    });
    versprechen.catch(() => {});   // vorgeladen und nie abgeholt: kein Konsolenfehler
    this.koKette = versprechen.catch(() => {});
    this.koCache.set(p, versprechen);
    return versprechen;
  },

  vsZeigen(schritt, index, token) {
    const p = schritt.partie;
    const flaeche = document.getElementById('ko-flaeche');
    flaeche.innerHTML = `
      <div class="ko-vs">
        <div class="ko-vs-runde">${schuetze(schritt.name)}</div>
        <div class="ko-vs-info">${schuetze(schritt.info || '')}</div>
        <div class="ko-vs-paar">
          <div class="ko-vs-team links">${this.logoTile(p.a, 'vs')}
            <div class="ko-vs-name">${schuetze(p.a.name)}</div></div>
          <div class="ko-vs-mitte">VS</div>
          <div class="ko-vs-team rechts">${this.logoTile(p.b, 'vs')}
            <div class="ko-vs-name">${schuetze(p.b.name)}</div></div>
        </div>
        <div class="ko-aktion"><span class="klein ko-lade" id="ko-lade">wird vorbereitet …</span></div>
      </div>`;
    const aktion = flaeche.querySelector('.ko-aktion');
    aktion.insertBefore(this.hauptknopf('Anpfiff ▶', () => this.spielZeigen(schritt, index, token)),
                        aktion.firstChild);
    const lade = document.getElementById('ko-lade');
    this.aufzeichnungHolen(p).then(() => {
      if (token === this.buehneToken && lade) lade.textContent = '';
    }, () => {
      if (token === this.buehneToken && lade) lade.textContent = '';
    });
    /* Gleich die nächste Partie hinterher, dann wartet nach diesem Spiel niemand. */
    const folgend = this.koSchritte.slice(index + 1).find((s) => s.art === 'partie');
    if (folgend) this.aufzeichnungHolen(folgend.partie);
  },

  async spielZeigen(schritt, index, token) {
    const p = schritt.partie;
    const flaeche = document.getElementById('ko-flaeche');
    const lade = document.getElementById('ko-lade');
    if (lade) lade.textContent = 'wird nachgespielt …';
    let aufzeichnung = null;
    let grund = '';
    try {
      aufzeichnung = await this.aufzeichnungHolen(p);
    } catch (fehler) {
      grund = fehler.message;
    }
    if (token !== this.buehneToken) return;
    this.infoSetzen(schritt.info ? `${schritt.name} · ${schritt.info}` : schritt.name);
    flaeche.innerHTML = `
      <div class="ko-spiel">
        <div class="ko-arena" id="ko-arena">
          ${this.seiteHtml(p.a, 'a')}
          <div class="buehne">
            <div class="buehne-banner" id="buehne-banner" hidden></div>
            <div class="buehne-raster" id="buehne-raster"></div>
          </div>
          ${this.seiteHtml(p.b, 'b')}
        </div>
      </div>`;
    const arena = document.getElementById('ko-arena');
    const spiel = {
      p, arena, aufzeichnung, phase: 'spiel', lauf: 0, springen: false, weiter: null,
      zuletzt: null,
      kapazitaet: aufzeichnung ? aufzeichnung.kapazitaet : 0,
      lieferungen: aufzeichnung ? this.lieferungenAus(aufzeichnung) : [[], []],
      seiten: ['a', 'b'].map((seite) => {
        const knoten = arena.querySelector(`.ko-seite[data-seite="${seite}"]`);
        return {
          knoten,
          punkte: knoten.querySelector('.ko-punkte'),
          ladung: knoten.querySelector('.ko-ladung'),
          lieferung: knoten.querySelector('.ko-lieferung'),
          depot: knoten.querySelector('.ko-depot'),
          depotZahl: knoten.querySelector('.ko-depot-zahl'),
          ladungSig: null,
          anzahlLieferungen: -1,
        };
      }),
    };
    this.koSpiel = spiel;
    const raster = document.getElementById('buehne-raster');
    const karte = this.duellKarte();
    raster.appendChild(karte.knoten);
    if (!aufzeichnung) {
      karte.ohneAufzeichnung(grund);
      spiel.phase = 'ende';
      this.spielEnde(spiel, schritt, index, token);
      return;
    }
    (aufzeichnung.spieler || []).forEach((s, k) => {
      const chip = spiel.seiten[k] && spiel.seiten[k].knoten.querySelector('.chip');
      if (chip && s.farbe) chip.style.background = s.farbe;
    });
    const buehne = new Buehne(raster);
    buehne.tempo = this.tempo;
    buehne.aufRahmen = (i, laenge) => this.buehneRahmen(i, laenge);
    buehne.aufEnde = () => this.abrechnungAbspielen(spiel, schritt, index, token);
    this.buehne = buehne;
    karte.fuellen(aufzeichnung);
    /* Punkte, Ladung und Depot stehen in den Seitenspalten; die Bühne meldet nur
       den Zustand. Sieger- und Führungsklassen hängen an der ganzen Arena. */
    karte.duell.karte = arena;
    karte.duell.aufZeichnen = (zustand, i) => this.seitenAktualisieren(spiel, zustand, i);
    buehne.anlegen(karte.duell);
    buehne.zeichne();
    this.felderAnpassen();
    /* Während des Countdowns gibt es nichts zu bedienen: Ein vorzeitiges „Zum
       Ende" würde sonst vom ablaufenden Countdown wieder zugedeckt. */
    for (const zahl of ['3', '2', '1']) {
      if (!await this.bannerZeigen(`<div class="buehne-countdown">${zahl}</div>`, 650, token)) {
        return;
      }
    }
    if (!await this.bannerZeigen('<div class="buehne-countdown los">LOS!</div>', 550, token)) return;
    if (token !== this.buehneToken || this.buehne !== buehne) return;
    document.getElementById('buehne-steuerung').hidden = false;
    buehne.start();
    this.buehneKnoepfe();
  },

  infoSetzen(text) {
    const info = document.getElementById('buehne-info');
    if (info) info.textContent = text || '';
  },

  /* Eine Seitenspalte: Team, Live-Punkte, Ladung und was im Depot liegt. */
  seiteHtml(bot, seite) {
    return `
      <aside class="ko-seite" data-seite="${seite}">
        <div class="ko-team">${this.logoTile(bot, 'seite')}
          <div class="ko-team-name"><i class="chip"></i><span>${schuetze(bot.name)}</span></div>
        </div>
        <div class="ko-punkte">0</div>
        <div class="ko-block">
          <div class="ko-block-titel">Ladung</div>
          <div class="ko-ladung"></div>
        </div>
        <div class="ko-block">
          <div class="ko-block-titel">Im Depot <span class="ko-depot-zahl"></span></div>
          <div class="ko-depot"></div>
          <div class="ko-block-titel klein ko-lieferung-titel">zuletzt abgeliefert</div>
          <div class="ko-lieferung"></div>
        </div>
      </aside>`;
  },

  /* Die Karte in der Mitte: nur noch das Spielfeld. */
  duellKarte() {
    const knoten = document.createElement('article');
    knoten.className = 'duell';
    knoten.innerHTML = `
      <div class="duell-feld">
        <canvas width="240" height="240"></canvas>
        <span class="duell-live"><i></i>LIVE</span>
      </div>`;
    const eintrag = {
      knoten,
      duell: null,
      fuellen: (aufzeichnung) => {
        const spielfeld = new Spielfeld(knoten.querySelector('canvas'));
        spielfeld.beamer = document.body.classList.contains('beamer');
        eintrag.duell = { spielfeld, aufzeichnung, karte: knoten, punkte: [] };
      },
      ohneAufzeichnung: (grund) => {
        knoten.classList.add('ohne-bild');
        const feld = knoten.querySelector('.duell-feld');
        if (feld) {
          feld.outerHTML = `<div class="duell-fuss">${
            schuetze(grund || 'nicht nachspielbar')} — es zählt der Endstand.</div>`;
        }
      },
    };
    return eintrag;
  },

  /* Ein Müllteil als Kachel: Farbe und Zeichen wie auf dem Feld, darunter der Wert. */
  teilHtml(teil, mitWert = true, klasse = '') {
    return MuellAnzeige.teil(teil, mitWert, klasse);
  },

  ladungHtml(ladung, kapazitaet) {
    return MuellAnzeige.ladung(ladung, kapazitaet, this.koSpiel && this.koSpiel.aufzeichnung);
  },

  /* Alle Ablieferungen einer Aufzeichnung je Roboter, mit dem Schritt der
     Wiedergabe, ab dem sie gelten: Ein Ereignis aus `ticks[t]` ist ab Schritt
     t + 1 sichtbar (Schritt 0 ist die Startaufstellung). */
  lieferungenAus(aufzeichnung) {
    return MuellAnzeige.lieferungen(aufzeichnung);
  },

  /* Wird bei jedem gezeichneten Bild gerufen, schreibt aber nur, wenn sich etwas
     geändert hat — 60 Bilder je Sekunde voller DOM-Arbeit ruckeln am Beamer. */
  seitenAktualisieren(spiel, zustand, index) {
    if (spiel.phase !== 'spiel' || spiel.zuletzt === index) return;
    spiel.zuletzt = index;
    const punkte = zustand.roboter.map((r) => r.punkte);
    zustand.roboter.forEach((r, k) => {
      const seite = spiel.seiten[k];
      if (!seite) return;
      seite.punkte.textContent = r.punkte;
      const signatur = JSON.stringify(r.ladung);
      if (signatur !== seite.ladungSig) {
        seite.ladungSig = signatur;
        seite.ladung.innerHTML = this.ladungHtml(r.ladung, spiel.kapazitaet);
      }
      const bisher = (spiel.lieferungen[k] || []).filter((l) => l.index <= index);
      if (bisher.length !== seite.anzahlLieferungen) {
        const neu = bisher.length > seite.anzahlLieferungen && seite.anzahlLieferungen >= 0;
        seite.anzahlLieferungen = bisher.length;
        this.depotZeichnen(seite, bisher, neu);
      }
    });
    this.fuehrungSetzen(spiel, punkte);
  },

  fuehrungSetzen(spiel, punkte) {
    spiel.arena.classList.toggle('fuehrt-a', punkte[0] > punkte[1]);
    spiel.arena.classList.toggle('fuehrt-b', punkte[1] > punkte[0]);
  },

  /* Das Depot bleibt übersichtlich, egal wie viel abgeliefert wird: je Sorte eine
     Zeile mit Anzahl und Summe der Werte, darunter die letzte Lieferung Teil für
     Teil. Es sind höchstens so viele Zeilen, wie es Sorten gibt. */
  depotZeichnen(seite, lieferungen, neu) {
    const depot = MuellAnzeige.depot(lieferungen, this.koSpiel && this.koSpiel.aufzeichnung);
    const stueck = depot.stueck;
    seite.depotZahl.textContent = stueck ? `· ${stueck} ${stueck === 1 ? 'Teil' : 'Teile'}` : '';
    seite.depot.innerHTML = depot.zeilen;
    seite.lieferung.innerHTML = depot.letzte;
    const letzte = depot.letzte;
    seite.knoten.classList.toggle('hat-lieferung', !!letzte);
    if (neu) {
      seite.lieferung.classList.remove('neu');
      void seite.lieferung.offsetWidth;
      seite.lieferung.classList.add('neu');
    }
  },

  /* Nach dem letzten Tick: Die Ladung an Bord wird Teil für Teil abgerechnet,
     abwechselnd zwischen den Teams. Erst danach steht fest, wer gewonnen hat.
     Was jedes Teil bringt, hat Python ausgerechnet (`ergebnis.roboter[].abrechnung`). */
  async abrechnungAbspielen(spiel, schritt, index, token) {
    if (token !== this.buehneToken) return;
    const lauf = ++spiel.lauf;
    const vorbei = () => lauf !== spiel.lauf || token !== this.buehneToken;
    spiel.phase = 'abrechnung';
    spiel.springen = false;
    const roboter = ((spiel.aufzeichnung || {}).ergebnis || {}).roboter || [];
    const posten = roboter.map((r) => (r.abrechnung && r.abrechnung.posten) || []);
    const stand = roboter.map((r) => (r.abrechnung ? r.abrechnung.punkte_vorher : r.punkte));
    if (posten.some((liste) => liste.length)) {
      spiel.seiten.forEach((seite, k) => {
        seite.ladung.innerHTML = this.ladungHtml(posten[k] || [], spiel.kapazitaet);
        seite.punkte.textContent = stand[k];
      });
      const banner = document.getElementById('buehne-banner');
      if (banner) {
        banner.innerHTML = '<div class="ko-abrechnung-titel">Abrechnung der Ladung</div>';
        banner.hidden = false;
        banner.classList.remove('ergebnis');
        banner.classList.add('abrechnung');
      }
      await this.warten(1100, spiel);
      const reihe = [];
      const laengste = Math.max(...posten.map((liste) => liste.length));
      for (let i = 0; i < laengste; i++) {
        posten.forEach((liste, k) => { if (i < liste.length) reihe.push([k, i]); });
      }
      for (const [k, i] of reihe) {
        if (vorbei()) return;
        const seite = spiel.seiten[k];
        const eintrag = posten[k][i];
        const kachel = seite.ladung.querySelectorAll('.teil')[i];
        if (kachel) kachel.classList.add('abrechnen');
        stand[k] += eintrag.punkte;
        seite.punkte.textContent = stand[k];
        seite.punkte.classList.remove('zaehlt');
        void seite.punkte.offsetWidth;
        seite.punkte.classList.add('zaehlt');
        const flug = document.createElement('span');
        flug.className = 'ko-flug' + (eintrag.punkte < 0 ? ' minus' : '');
        flug.textContent = `${eintrag.punkte > 0 ? '+' : ''}${eintrag.punkte}`;
        seite.punkte.appendChild(flug);
        setTimeout(() => flug.remove(), 1300);
        this.fuehrungSetzen(spiel, stand);
        await this.warten(850, spiel);
        if (kachel) kachel.classList.add('weg');
      }
      await this.warten(500, spiel);
      if (banner && !vorbei()) {
        banner.hidden = true;
        banner.classList.remove('abrechnung');
      }
    }
    if (vorbei()) return;
    spiel.phase = 'ende';
    this.spielEnde(spiel, schritt, index, token);
  },

  bannerZeigen(html, dauer, token) {
    const banner = document.getElementById('buehne-banner');
    if (!banner) return Promise.resolve(false);
    banner.innerHTML = html;
    banner.hidden = false;
    banner.classList.remove('zeigt');
    void banner.offsetWidth;
    banner.classList.add('zeigt');
    return new Promise((fertig) => {
      setTimeout(() => {
        if (token !== undefined && token !== this.buehneToken) {
          fertig(false);
          return;
        }
        banner.hidden = true;
        banner.classList.remove('zeigt');
        fertig(true);
      }, dauer);
    });
  },

  /* Sieger und Verlierer kommen aus dem Turnierergebnis, nicht aus der Wiedergabe. */
  siegerSeite(p) {
    if (p.unentschieden && p.entschieden_durch === 'Setzliste') {
      const kennung = (p.sieger_bot || {}).kennung;
      if (kennung && p.a && kennung === p.a.kennung) return 'a';
      if (kennung && p.b && kennung === p.b.kennung) return 'b';
      return (p.sieger_bot || {}).name === (p.a || {}).name ? 'a' : 'b';
    }
    if (p.sieger === 0) return 'a';
    if (p.sieger === 1) return 'b';
    return null;
  },

  /* Die Partie ist durch: Sieger hervorheben, Konfetti, und über dem Feld der
     Sieger samt Weiter-Knopf. Der Banner bleibt stehen, bis jemand klickt. Die
     Punkte sind ab hier der Endstand aus dem Turnierergebnis. */
  spielEnde(spiel, schritt, index, token) {
    if (token !== this.buehneToken) return;
    const p = schritt.partie;
    (p.punkte || []).forEach((wert, k) => {
      if (spiel.seiten[k]) spiel.seiten[k].punkte.textContent = wert;
    });
    if (p.punkte) this.fuehrungSetzen(spiel, p.punkte);
    const seite = this.siegerSeite(p);
    if (seite) {
      spiel.arena.classList.add('gewinner-' + seite);
      const sieger = spiel.arena.querySelector(`.ko-seite[data-seite="${seite}"]`);
      const besiegt = spiel.arena.querySelector(`.ko-seite[data-seite="${seite === 'a' ? 'b' : 'a'}"]`);
      if (sieger) sieger.classList.add('sieger');
      if (besiegt) besiegt.classList.add('besiegt');
    }
    this.buehneKnoepfe();
    const gewinner = p.sieger_bot || {};
    const folgend = this.koSchritte[index + 1];
    const wohin = !folgend ? '' : (folgend.art === 'baum' ? 'Turnierbaum'
      : (folgend.art === 'podest' ? 'Siegerehrung' : folgend.name));
    const zusatz = [];
    if (p.wiederholungen) zusatz.push(`${p.wiederholungen}× wiederholt wegen Gleichstand`);
    if (p.entschieden_durch === 'Setzliste') zusatz.push('nach Gleichstand durch die Setzung entschieden');
    const banner = document.getElementById('buehne-banner');
    if (!banner) return;
    banner.innerHTML = `
      <div class="ko-sieger">
        <div class="ko-sieger-titel">${schritt.name === 'Finale' ? 'Turniersieger'
          : (schritt.name === 'Spiel um Platz 3' ? 'Platz 3' : 'Sieger')}</div>
        ${this.logoTile(gewinner, 'feier')}
        <div class="ko-sieger-name">${schuetze(gewinner.name || '—')}</div>
        <div class="ko-sieger-stand">${schuetze((p.punkte || []).join(' : '))}</div>
        ${zusatz.length ? `<div class="klein">${schuetze(zusatz.join(' · '))}</div>` : ''}
        <div class="ko-aktion"></div>
      </div>`;
    banner.hidden = false;
    banner.classList.remove('abrechnung');
    banner.classList.add('ergebnis');
    const aktion = banner.querySelector('.ko-aktion');
    if (folgend) {
      aktion.appendChild(this.hauptknopf('Weiter ▶', () => this.koSchrittZeigen(index + 1)));
      const hinweis = document.createElement('span');
      hinweis.className = 'klein';
      hinweis.textContent = `als Nächstes: ${wohin}`;
      aktion.appendChild(hinweis);
    }
    const konfetti = this.konfettiHolen();
    const rechteck = banner.getBoundingClientRect();
    konfetti.stossen(rechteck.left + rechteck.width / 2, rechteck.top + rechteck.height * 0.35,
                     schritt.name === 'Finale' ? 90 : 40);
  },

  /* Wer nach dem Ende ▶ drückt oder am Schieber zieht, sieht die Partie noch
     einmal: laufende Abrechnung abbrechen, Banner weg, Seiten wieder live. */
  spielZuruecksetzen() {
    const spiel = this.koSpiel;
    if (!spiel || spiel.phase === 'spiel') return;
    spiel.lauf += 1;
    spiel.phase = 'spiel';
    spiel.springen = false;
    spiel.zuletzt = null;
    spiel.seiten.forEach((seite) => {
      seite.ladungSig = null;
      seite.anzahlLieferungen = -1;
      seite.knoten.classList.remove('sieger', 'besiegt');
    });
    spiel.arena.classList.remove('gewinner-a', 'gewinner-b');
    const banner = document.getElementById('buehne-banner');
    if (banner) {
      banner.hidden = true;
      banner.classList.remove('ergebnis', 'abrechnung');
    }
  },

  /* Die Siegertreppe: Platz 2 links, 1 in der Mitte, 3 rechts. Die Plätze kommen
     aus `podest` im Turnierergebnis; alte Archive ohne Podest zeigen nur den Sieger. */
  podestZeigen(index, token) {
    const ko = this.ko;
    const podest = ko.podest || [ko.sieger, null, null];
    const platz = (nummer) => {
      const bot = podest[nummer - 1];
      return `
        <div class="podest-platz p${nummer}">
          <div class="podest-team">
            ${nummer === 1 ? '<div class="podest-pokal">🏆</div>' : ''}
            ${bot ? this.logoTile(bot, nummer === 1 ? 'feier' : 'podest') : ''}
            <div class="podest-name">${schuetze(bot ? bot.name : '—')}</div>
          </div>
          <div class="podest-block">${nummer}</div>
        </div>`;
    };
    const flaeche = document.getElementById('ko-flaeche');
    flaeche.innerHTML = `
      <div class="ko-podest">
        <div class="ko-ueberschrift">
          <div class="buehne-titel">Siegerehrung</div>
        </div>
        <div class="podest">${platz(2)}${platz(1)}${platz(3)}</div>
        <div class="ko-aktion"></div>
      </div>`;
    flaeche.querySelector('.ko-aktion').appendChild(
      this.hauptknopf('Turnierbaum ansehen', () => this.koSchrittZeigen(index + 1)));
    setTimeout(() => {
      if (token !== this.buehneToken) return;
      const konfetti = this.konfettiHolen();
      konfetti.regen(6500);
      const erster = flaeche.querySelector('.podest-platz.p1 .podest-team');
      if (erster) {
        const rechteck = erster.getBoundingClientRect();
        konfetti.stossen(rechteck.left + rechteck.width / 2, rechteck.top + rechteck.height / 2, 90);
      }
    }, 1900);
  },

  /* Gleiches Bot-Objekt? Aus dem Archiv kommen Kopien, deshalb über die Kennung. */
  gleicherBot(x, y) {
    if (!x || !y) return false;
    if (x.kennung && y.kennung) return x.kennung === y.kennung;
    return x.name === y.name;
  },

  /* Der Turnierbaum als Baum: eine Spalte je Runde, Linien zur nächsten Runde.
     `bis` ist die erste Runde, deren Ergebnisse noch nicht verraten werden; von
     dort an stehen nur Paarungen, die schon feststehen, sonst „?". Ohne `bis`
     ist alles aufgedeckt (Archiv, Endstand). */
  koBaumHtml(ergebnis, bis = Infinity) {
    const runden = ergebnis.runden || [];
    const letzte = runden.length - 1;
    const aufgedeckt = (r, p) => r < bis || (p && p.freilos);
    /* Eine Zeile im Kasten: `undefined` heißt „steht noch nicht fest". */
    const zeile = (bot, rechts, klasse, erste = false) => {
      if (bot === undefined) {
        return '<div class="zeile offen"><span class="mit-logo"><span class="logo-quadrat logo-klein ersatz">?</span>' +
          '<span>?</span></span></div>';
      }
      if (!bot) return '';
      const merkmal = erste ? ` data-bot="${schuetze(bot.kennung || bot.name)}"` : '';
      return `<div class="zeile ${klasse}"${merkmal}><span class="mit-logo">${this.logoTile(bot, 'klein')}
        <span class="baum-name">${schuetze(bot.name)}</span></span>
        <span class="baum-punkte">${schuetze(String(rechts))}</span></div>`;
    };
    const paar = (p, a, b, zeigen, erste = false) => {
      if (p.freilos) {
        return `<div class="baum-paar freilos">${zeile(p.sieger_bot, 'Freilos', 'sieger', erste)}</div>`;
      }
      const punkte = p.punkte || [];
      const seite = (bot, wert) => {
        if (!zeigen || !bot) return zeile(bot, '', '', erste);
        return zeile(bot, wert === undefined ? '' : wert,
                     this.gleicherBot(p.sieger_bot, bot) ? 'sieger' : 'raus', erste);
      };
      return `<div class="baum-paar">${seite(a, punkte[0])}${seite(b, punkte[1])}</div>`;
    };
    const spalten = runden.map((runde, r) => {
      const vorher = r > 0 ? runden[r - 1].partien : null;
      /* Wer in Runde r steht, ist erst bekannt, wenn die Partie davor aufgedeckt ist. */
      const kennt = (k) => r === 0 || !vorher[k] || aufgedeckt(r - 1, vorher[k]);
      const plaetze = runde.partien.map((p, i) => {
        const a = kennt(2 * i) ? p.a : undefined;
        const b = kennt(2 * i + 1) ? p.b : undefined;
        let platz3 = '';
        const dritte = ergebnis.spiel_um_platz_3;
        if (r === letzte && dritte) {
          const bekannt = bis > letzte - 1;
          platz3 = `<div class="baum-platz3"><div class="baum-platz3-titel">Spiel um Platz 3</div>${
            paar(dritte, bekannt ? dritte.a : undefined, bekannt ? dritte.b : undefined, bis > letzte)}</div>`;
        }
        return `<div class="baum-slot"><div class="baum-huelle">${paar(p, a, b, aufgedeckt(r, p), r === 0)}${platz3}</div></div>`;
      }).join('');
      return `<div class="baum-spalte"><h3>${schuetze(runde.name)}</h3>
        <div class="baum-slots">${plaetze}</div></div>`;
    }).join('');
    const sieger = bis > letzte ? ergebnis.sieger : undefined;
    const siegerSpalte = `<div class="baum-spalte baum-ende"><h3>Sieger</h3><div class="baum-slots">
      <div class="baum-slot"><div class="baum-huelle"><div class="baum-paar baum-champion">${
        sieger ? `<span class="baum-pokal">🏆</span>${this.logoTile(sieger, 'mittel')}<b>${
          schuetze(sieger.name)}</b>` : '<span class="baum-pokal">🏆</span><b>?</b>'}</div></div></div>
      </div></div>`;
    return `<div class="turnierbaum">${spalten}${siegerSpalte}</div>`;
  },

  /* ---------------------------------------------------------------- Archiv */

  async zeigeTurniere() {
    const token = this.aufbauToken;
    const inhalt = document.getElementById('fsr-inhalt');
    inhalt.innerHTML = `
      <div class="karte">
        <h2>Turnierarchiv</h2>
        <p class="klein">Jede Gruppenphase und jedes K.-o.-Turnier wird beim Spielen
          abgelegt. Hier lässt sich alles wieder anzeigen — auch nach einem Neustart.</p>
        <div id="archiv-liste" class="meldungen">
          <div class="meldung lade">Wird gelesen …</div></div>
      </div>
      <div class="karte" id="archiv-karte" hidden>
        <h2 id="archiv-titel"></h2>
        <div id="archiv-inhalt" class="klein"></div>
      </div>`;
    let antwort;
    try {
      antwort = await this.ruf('/api/fsr/turniere');
    } catch (fehler) {
      if (token === this.aufbauToken) {
        document.getElementById('archiv-liste').innerHTML =
          `<div class="meldung fehler">${schuetze(fehler.message)}</div>`;
      }
      return;
    }
    if (token !== this.aufbauToken) return;
    const turniere = antwort.turniere || [];
    if (!turniere.length) {
      document.getElementById('archiv-liste').innerHTML =
        '<div class="meldung hinweis">Noch nichts gespielt.</div>';
      return;
    }
    const zeilen = turniere.map((e) => `<tr>
      <td>${schuetze(e.zeit || e.datei)}</td>
      <td>${e.art === 'ko' ? 'K.-o.-Runden' : (e.art === 'gruppe' ? 'Gruppenphase' : '?')}</td>
      <td><b>${schuetze(e.sieger || '—')}</b></td>
      <td class="zahl">${e.teilnehmer.length}</td>
      <td class="klein">${schuetze(e.teilnehmer.join(', '))}</td>
      <td>${e.lesbar
        ? `<button class="flach" data-datei="${schuetze(e.datei)}"
             data-titel="${schuetze(this.archivTitel(e))}">Anzeigen</button>`
        : '<span class="klein">unlesbar</span>'}</td></tr>`).join('');
    document.getElementById('archiv-liste').innerHTML = `
      <table class="tabelle">
        <thead><tr><th>Wann</th><th>Art</th><th>Sieger</th><th class="zahl">Roboter</th>
          <th>Teilnehmer</th><th></th></tr></thead>
        <tbody>${zeilen}</tbody></table>`;
    document.querySelectorAll('#archiv-liste button[data-datei]').forEach((knopf) => {
      knopf.addEventListener('click',
        () => this.turnierOeffnen(knopf.dataset.datei, knopf.dataset.titel));
    });
  },

  archivTitel(eintrag) {
    const art = eintrag.art === 'ko' ? 'K.-o.-Runden'
      : (eintrag.art === 'gruppe' ? 'Gruppenphase' : 'Turnier');
    return eintrag.zeit ? `${art} vom ${eintrag.zeit}` : `${art} · ${eintrag.datei}`;
  },

  async turnierOeffnen(datei, titel) {
    const token = this.aufbauToken;
    const karte = document.getElementById('archiv-karte');
    const ziel = document.getElementById('archiv-inhalt');
    karte.hidden = false;
    document.getElementById('archiv-titel').textContent = titel || datei;
    ziel.innerHTML = '<div class="meldung lade">Wird geladen …</div>';
    let antwort;
    try {
      antwort = await this.ruf('/api/fsr/turniere', { datei });
    } catch (fehler) {
      if (token === this.aufbauToken) {
        ziel.innerHTML = `<div class="meldung fehler">${schuetze(fehler.message)}</div>`;
      }
      return;
    }
    if (token !== this.aufbauToken) return;
    const turnier = antwort.turnier;
    if (turnier.art === 'ko') {
      ziel.innerHTML = this.koBaumHtml(turnier) +
        '<div class="werkzeugleiste"><button id="archiv-buehne" class="haupt">' +
        'Bühne öffnen</button></div>';
      const knopf = document.getElementById('archiv-buehne');
      if (knopf) {
        knopf.addEventListener('click', () => {
          this.ko = turnier;
          this.koSchritt = 0;
          this.reiter = 'ko';
          this.aufbauen();
        });
      }
    } else if (turnier.art === 'gruppe') {
      ziel.innerHTML = this.gruppeTabelleHtml(turnier);
    } else {
      ziel.innerHTML = '<div class="meldung fehler">Unbekannte Turnierart.</div>';
    }
    karte.scrollIntoView({ behavior: 'smooth', block: 'start' });
  },

  /* ---------------------------------------------------------------- Balance */

  zeigeBalance() {
    document.getElementById('fsr-inhalt').innerHTML = `
      <div class="karte">
        <h2>Massenauswertung</h2>
        <p class="klein">Alle Paarungen über viele Seeds, mit getauschten Startplätzen.
          Faustregel: Wenn ein Roboter alle anderen schlägt, stimmen die Zahlen nicht.
          Das dauert je nach Anzahl einige Minuten.</p>
        <div class="werkzeugleiste">
          <label class="feld">Ordner <select id="bal-ordner">
            <option value="bots">mitgelieferte Gegner</option>
            <option value="abgaben">Abgaben</option></select></label>
          <label class="feld">Seeds <input id="bal-seeds" type="number"
            value="${this.config.balance.seeds}" min="1" max="200"></label>
          <button id="bal-start" class="haupt">Rechnen</button>
        </div>
        <div id="bal-meldung" class="meldungen"></div>
        <div id="bal-ergebnis"></div>
      </div>`;
    document.getElementById('bal-start').addEventListener('click', async () => {
      const knopf = document.getElementById('bal-start');
      const anzeige = document.getElementById('bal-meldung');
      const token = this.aufbauToken;
      knopf.disabled = true;
      try {
        const antwort = await this.ruf('/api/fsr/balance', {
          ordner: document.getElementById('bal-ordner').value,
          seeds: Number(document.getElementById('bal-seeds').value)
            || this.config.balance.seeds,
        });
        if (token !== this.aufbauToken) return;
        this.aufgabeVerfolgen(antwort.aufgabe, anzeige, (e) => this.balanceZeigen(e));
      } catch (fehler) {
        if (token === this.aufbauToken) {
          anzeige.innerHTML = `<div class="meldung fehler">${schuetze(fehler.message)}</div>`;
        }
      } finally {
        knopf.disabled = false;
      }
    });
  },

  balanceZeigen(bericht) {
    const namen = bericht.bots.map((b) => b.name);
    const kopf = `<tr><th></th>${namen.map((n) => `<th class="zahl">${schuetze(n)}</th>`).join('')}</tr>`;
    const zeilen = bericht.quoten.map((zeile, i) => `<tr>
      <th><span class="mit-logo">${this.logoTile(bericht.bots[i], 'klein')}${
        schuetze(namen[i])}</span></th>
      ${zeile.map((wert) => {
        if (wert === null) return '<td class="zahl">—</td>';
        const klasse = wert >= 65 ? 'stark' : (wert <= 35 ? 'schwach' : '');
        return `<td class="zahl ${klasse}">${wert.toFixed(0)}%</td>`;
      }).join('')}</tr>`).join('');
    const gesamt = [...bericht.gesamt].sort((a, b) => b.siegquote - a.siegquote)
      .map((e) => `<tr><td><span class="mit-logo">${this.logoTile(e, 'mittel')}${
        schuetze(e.name)}</span></td>
        <td class="zahl">${e.siegquote}%</td><td class="zahl">${e.punkte_schnitt}</td>
        <td>${e.kaputt ? 'lief nicht!' : ''}</td></tr>`).join('');
    document.getElementById('bal-ergebnis').innerHTML = `
      <table class="tabelle matrix"><thead>${kopf}</thead><tbody>${zeilen}</tbody></table>
      <p class="klein">Zeile gewinnt gegen Spalte in x % der Spiele.</p>
      <table class="tabelle"><thead><tr><th>Roboter</th><th class="zahl">Siegquote</th>
        <th class="zahl">Ø Punkte</th><th></th></tr></thead><tbody>${gesamt}</tbody></table>
      <div class="meldung hinweis">${schuetze(bericht.urteil)}</div>`;
  },

  /* ---------------------------------------------------------------- Config */

  zeigeConfig() {
    document.getElementById('fsr-inhalt').innerHTML = `
      <div class="karte">
        <h2>Einstellungen</h2>
        <p class="klein">Sämtliche Zahlenwerte des Spiels. Änderungen gelten sofort für
          alle folgenden Matches. „Dauerhaft speichern" schreibt sie in die
          <code>config.json</code>.</p>
        <textarea id="config-text" style="width:100%;min-height:460px;font-family:var(--mono);
          font-size:12.5px;padding:10px;border:1px solid var(--rand);border-radius:8px"></textarea>
        <div class="werkzeugleiste">
          <button id="config-uebernehmen" class="haupt">Übernehmen</button>
          <button id="config-speichern" class="flach">Dauerhaft speichern</button>
        </div>
        <div id="config-meldung" class="meldungen"></div>
      </div>`;
    document.getElementById('config-text').value = JSON.stringify(this.config, null, 2);
    const senden = async (dauerhaft) => {
      const anzeige = document.getElementById('config-meldung');
      let neu;
      try {
        neu = JSON.parse(document.getElementById('config-text').value);
      } catch (fehler) {
        anzeige.innerHTML = `<div class="meldung fehler">Das ist kein gültiges JSON: ${
          schuetze(fehler.message)}</div>`;
        return;
      }
      try {
        const antwort = await this.ruf('/api/fsr/config', { config: neu, dauerhaft });
        this.config = antwort.config;
        anzeige.innerHTML = `<div class="meldung gut">Übernommen${
          dauerhaft ? ' und gespeichert' : ''}.</div>`;
      } catch (fehler) {
        anzeige.innerHTML = `<div class="meldung fehler">${schuetze(fehler.message)}</div>`;
      }
    };
    document.getElementById('config-uebernehmen').addEventListener('click', () => senden(false));
    document.getElementById('config-speichern').addEventListener('click', () => senden(true));
  },
};
