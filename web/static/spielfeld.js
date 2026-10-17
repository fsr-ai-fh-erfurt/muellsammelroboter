/* Zeichnen und Abspielen einer Aufzeichnung.
   Hier steht ausschließlich Darstellung — keine Spielregel, keine Bewertung.
   Alles, was hier gezeichnet wird, hat Python vorher ausgerechnet. */

const SORTEN_FARBEN = {
  papier:     '#7d8b9c',
  bio:        '#3d8f45',
  metall:     '#4a7fa5',
  elektro:    '#8a4fbe',
  radioaktiv: '#1b1b1b',
  ballen:     '#a0782c',
};

const SORTEN_ZEICHEN = {
  papier: 'P', bio: 'B', metall: 'M', elektro: 'E', radioaktiv: '☢', ballen: '▣',
};

/* Müllteile als Kacheln — dieselbe Darstellung in Werkstatt, Einzelmatch und
   Turnier-Show. Alle Werte stehen in der Aufzeichnung; hier wird nur gezeigt und
   gezählt, was Python geliefert hat. */
const MuellAnzeige = {
  REIHENFOLGE: ['papier', 'bio', 'metall', 'elektro', 'ballen', 'radioaktiv'],

  /* Der Name, den die Teams sehen — aus der config.json über die Aufzeichnung. */
  name(sorte, aufzeichnung) {
    if (sorte === 'ballen') return 'Ballen';
    if (aufzeichnung) {
      if (sorte === 'radioaktiv' && aufzeichnung.radioaktiv) return aufzeichnung.radioaktiv.anzeige;
      if (aufzeichnung.sorten && aufzeichnung.sorten[sorte]) return aufzeichnung.sorten[sorte].anzeige;
    }
    return sorte;
  },

  zahl(wert) {
    const w = Number(wert) || 0;
    return (w > 0 ? '+' : '') + w;
  },

  teil(teil, mitWert = true, klasse = '', titel = '') {
    const farbe = SORTEN_FARBEN[teil.sorte] || '#888888';
    const zeichen = SORTEN_ZEICHEN[teil.sorte] || '?';
    const wert = Number(teil.wert) || 0;
    const hinweis = titel ? ` title="${schuetze(titel)}"` : '';
    return `<span class="teil ${klasse}" style="--teil-farbe:${farbe}"${hinweis}><b>${zeichen}</b>${
      mitWert ? `<small${wert < 0 ? ' class="minus"' : ''}>${this.zahl(wert)}</small>` : ''
    }</span>`;
  },

  ladung(ladung, kapazitaet, aufzeichnung) {
    const teile = ladung.map((teil) => this.teil(teil, true, '',
      `${this.name(teil.sorte, aufzeichnung)}: ${this.zahl(teil.wert)}`));
    for (let i = ladung.length; i < kapazitaet; i++) teile.push('<span class="teil leer"></span>');
    return teile.join('');
  },

  /* Alle Ablieferungen je Roboter mit dem Wiedergabeschritt, ab dem sie gelten:
     Ein Ereignis aus `ticks[t]` ist ab Schritt t + 1 sichtbar. */
  lieferungen(aufzeichnung) {
    const lieferungen = (aufzeichnung.spieler || []).map(() => []);
    (aufzeichnung.ticks || []).forEach((tick, t) => {
      (tick.ereignisse || []).forEach((e) => {
        if (e.art === 'abliefern' && e.teile && lieferungen[e.wer]) {
          lieferungen[e.wer].push({ index: t + 1, teile: e.teile });
        }
      });
    });
    return lieferungen;
  },

  /* Gemerkt je Aufzeichnung: Die Wiedergabe fragt bei jedem Bild danach. */
  _lieferungenCache: new WeakMap(),
  lieferungenFuer(aufzeichnung) {
    if (!this._lieferungenCache.has(aufzeichnung)) {
      this._lieferungenCache.set(aufzeichnung, this.lieferungen(aufzeichnung));
    }
    return this._lieferungenCache.get(aufzeichnung);
  },

  /* Ladung und Depot eines Roboters für die Kacheln unter dem Feld (Werkstatt,
     Einzelmatch) — wie die Seitenspalten der Turnier-Show, nur kompakter. */
  kachelInhalt(aufzeichnung, roboter, i, index) {
    const alle = this.lieferungenFuer(aufzeichnung)[i] || [];
    const bisher = alle.filter((l) => l.index <= index);
    const depot = this.depot(bisher, aufzeichnung);
    return `<div class="kachel-block">
        <div class="kachel-titel">Ladung · ${roboter.ladung.length} / ${aufzeichnung.kapazitaet}</div>
        <div class="teil-reihe">${this.ladung(roboter.ladung, aufzeichnung.kapazitaet, aufzeichnung)}</div>
      </div>
      <div class="kachel-block">
        <div class="kachel-titel">Im Depot${depot.stueck ? ` · ${depot.stueck} ${depot.stueck === 1 ? 'Teil' : 'Teile'}` : ''}</div>
        <div class="depot-liste">${depot.zeilen}</div>
        ${depot.letzte ? `<div class="kachel-titel klein">zuletzt abgeliefert</div>
        <div class="teil-reihe klein">${depot.letzte}</div>` : ''}
      </div>`;
  },

  /* Je Sorte eine Zeile mit Anzahl und Summe — so bleibt es kurz, egal wie viel
     abgeliefert wurde. Dazu die letzte Lieferung Teil für Teil. */
  depot(lieferungen, aufzeichnung) {
    const summen = new Map();
    let stueck = 0;
    lieferungen.forEach((l) => l.teile.forEach((teil) => {
      const eintrag = summen.get(teil.sorte) || { anzahl: 0, wert: 0 };
      eintrag.anzahl += 1;
      eintrag.wert += Number(teil.wert) || 0;
      summen.set(teil.sorte, eintrag);
      stueck += 1;
    }));
    const rang = (sorte) => (this.REIHENFOLGE.indexOf(sorte) < 0 ? 99 : this.REIHENFOLGE.indexOf(sorte));
    const sorten = [...summen.keys()].sort((x, y) => rang(x) - rang(y) || x.localeCompare(y));
    const zeilen = sorten.length ? sorten.map((sorte) => {
      const e = summen.get(sorte);
      return `<div class="depot-zeile">${this.teil({ sorte, wert: 0 }, false, '',
        this.name(sorte, aufzeichnung))}
        <span class="depot-anzahl">× ${e.anzahl}</span>
        <span class="depot-summe${e.wert < 0 ? ' minus' : ''}">${this.zahl(e.wert)}</span>
      </div>`;
    }).join('') : '<div class="depot-leer">noch nichts</div>';
    const letzte = lieferungen[lieferungen.length - 1];
    return {
      stueck,
      zeilen,
      letzte: letzte ? letzte.teile.map((teil) => this.teil(teil, true, '',
        `${this.name(teil.sorte, aufzeichnung)}: ${this.zahl(teil.wert)}`)).join('') : '',
    };
  },
};

function mische(farbe, ziel, anteil) {
  const zerlege = (f) => [parseInt(f.slice(1, 3), 16), parseInt(f.slice(3, 5), 16),
                          parseInt(f.slice(5, 7), 16)];
  const [r1, g1, b1] = zerlege(farbe);
  const [r2, g2, b2] = zerlege(ziel);
  const m = (a, b) => Math.round(a + (b - a) * anteil);
  return `rgb(${m(r1, r2)}, ${m(g1, g2)}, ${m(b1, b2)})`;
}

class Spielfeld {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.aufzeichnung = null;
    this.beamer = false;
    /* 0 heißt: die angezeigte Breite gibt das Maß vor. Im Vollbild setzt der
       FSR-Modus beide Werte, damit das Feld auch in die Höhe passt. */
    this.breitePlatz = 0;
    this.hoehePlatz = 0;
    /* Werkstatt und Einzelmatch zeigen mehr als die Show: die Punktzahl jedes
       Müllstücks und einen Pfeil, wohin jeder Roboter als Nächstes fährt. */
    this.werteZeigen = false;
    this.pfeileZeigen = false;
  }

  laden(aufzeichnung) {
    this.aufzeichnung = aufzeichnung;
    this.zelle = null;
    this.groesseAnpassen();
  }

  /* Die Auflösung richtet sich nach der angezeigten Breite. Seit die Spalte ziehbar
     ist, kann das Feld deutlich breiter werden als die früheren festen 30 Pixel je
     Zelle — der Browser würde das Bild dann hochrechnen und das Feld weich machen.
     Ganze Pixel je Zelle halten die Gitterlinien scharf. Gibt zurück, ob sich etwas
     geändert hat; nur dann muss neu gezeichnet werden. */
  groesseAnpassen() {
    const a = this.aufzeichnung;
    if (!a) return false;
    const seite = Math.max(a.breite, a.hoehe);
    const breite = this.breitePlatz > 0
      ? this.breitePlatz
      : (this.canvas.clientWidth || seite * 30);
    /* 96 als Deckel: Das reicht für die volle Höhe eines 4K-Beamers
       (24 Felder × 96 = 2304 Pixel) und begrenzt den Speicher nach oben. */
    let zelle = Math.floor(breite / seite);
    if (this.hoehePlatz > 0) zelle = Math.min(zelle, Math.floor(this.hoehePlatz / seite));
    zelle = Math.max(12, Math.min(96, zelle));
    if (zelle === this.zelle) return false;
    this.zelle = zelle;
    this.canvas.width = seite * zelle;
    this.canvas.height = seite * zelle;
    return true;
  }

  /* Zustand eines Wiedergabeschritts: 0 = Startaufstellung, 1..n = nach Tick n. */
  zustandVon(index) {
    if (!this.aufzeichnung) return null;
    if (index <= 0) return this.aufzeichnung.start;
    return this.aufzeichnung.ticks[Math.min(index, this.aufzeichnung.ticks.length) - 1];
  }

  zeichne(index, fortschritt = 1) {
    const a = this.aufzeichnung;
    if (!a) return;
    const jetzt = this.zustandVon(index);
    const vorher = this.zustandVon(index - 1);
    const ctx = this.ctx;
    const z = this.zelle;

    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    const bodenFarbe = this.beamer ? '#181d27' : '#fdfdfe';
    const wandFarbe = this.beamer ? '#39415a' : '#c3c8d1';
    const gitterFarbe = this.beamer ? '#232a38' : '#eef0f4';

    /* Boden und Wände */
    ctx.fillStyle = bodenFarbe;
    ctx.fillRect(0, 0, a.breite * z, a.hoehe * z);
    ctx.fillStyle = wandFarbe;
    for (let x = 0; x < a.breite; x++) {
      for (let y = 0; y < a.hoehe; y++) {
        if (x === 0 || y === 0 || x === a.breite - 1 || y === a.hoehe - 1) {
          ctx.fillRect(x * z, y * z, z, z);
        }
      }
    }

    /* Innenwände der Karte. Sie stehen nicht auf der Wurzel der Aufzeichnung,
       sondern in der Startaufstellung und in jedem Tick — deshalb aus `jetzt`. */
    const hindernisse = (jetzt && jetzt.hindernisse) || a.hindernisse || [];
    ctx.fillStyle = wandFarbe;
    hindernisse.forEach(([hx, hy]) => ctx.fillRect(hx * z, hy * z, z, z));

    /* Gitterlinien */
    ctx.strokeStyle = gitterFarbe;
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let x = 1; x < a.breite; x++) { ctx.moveTo(x * z + 0.5, z); ctx.lineTo(x * z + 0.5, (a.hoehe - 1) * z); }
    for (let y = 1; y < a.hoehe; y++) { ctx.moveTo(z, y * z + 0.5); ctx.lineTo((a.breite - 1) * z, y * z + 0.5); }
    ctx.stroke();

    /* Bonuszone */
    const [zx, zy] = jetzt.zone;
    const g = a.zone_groesse;
    ctx.fillStyle = this.beamer ? 'rgba(255, 214, 64, 0.16)' : 'rgba(255, 205, 60, 0.28)';
    ctx.fillRect(zx * z, zy * z, g * z, g * z);
    ctx.strokeStyle = this.beamer ? '#f0c040' : '#e0a400';
    ctx.lineWidth = 2;
    ctx.setLineDash([6, 4]);
    ctx.strokeRect(zx * z + 1, zy * z + 1, g * z - 2, g * z - 2);
    ctx.setLineDash([]);

    /* Depots */
    a.spieler.forEach((s) => {
      const [dx, dy] = s.depot;
      ctx.fillStyle = this.beamer ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.045)';
      ctx.fillRect(dx * z, dy * z, z, z);
      ctx.strokeStyle = s.farbe;
      ctx.lineWidth = 2.5;
      ctx.strokeRect(dx * z + 2, dy * z + 2, z - 4, z - 4);
      ctx.fillStyle = s.farbe;
      ctx.font = `bold ${Math.round(z * 0.42)}px system-ui, sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('⌂', dx * z + z / 2, dy * z + z / 2 + 1);
    });

    /* Müll */
    jetzt.muell.forEach(([mx, my, sorte, wert]) => {
      const grundfarbe = SORTEN_FARBEN[sorte] || '#888888';
      const basis = sorte === 'radioaktiv' ? a.radioaktiv.wert
                                           : (a.sorten[sorte] ? a.sorten[sorte].wert : 10);
      let farbe = grundfarbe;
      if (sorte !== 'radioaktiv') {
        if (wert <= 0) {
          farbe = '#c02626';
        } else {
          const anteil = 1 - Math.max(0, Math.min(1, wert / basis));
          farbe = mische(grundfarbe, this.beamer ? '#2b3242' : '#dfe3e9', anteil * 0.75);
        }
      }
      const rand = this.werteZeigen ? z * 0.08 : z * 0.17;
      ctx.fillStyle = farbe;
      this._rundesRechteck(mx * z + rand, my * z + rand, z - 2 * rand, z - 2 * rand, 3);
      ctx.fill();
      if (this.werteZeigen) {
        this._wertZeichnen(mx, my, sorte, wert);
      } else if (sorte === 'radioaktiv') {
        ctx.fillStyle = '#f5d020';
        ctx.font = `bold ${Math.round(z * 0.5)}px system-ui, sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('☢', mx * z + z / 2, my * z + z / 2 + 1);
      } else if (z >= 22) {
        ctx.fillStyle = 'rgba(255,255,255,0.92)';
        ctx.font = `bold ${Math.round(z * 0.34)}px system-ui, sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(SORTEN_ZEICHEN[sorte] || '?', mx * z + z / 2, my * z + z / 2 + 1);
      }
    });

    /* Roboter */
    jetzt.roboter.forEach((r, i) => {
      const alt = vorher ? vorher.roboter[i] : r;
      const px = (alt.x + (r.x - alt.x) * fortschritt) * z + z / 2;
      const py = (alt.y + (r.y - alt.y) * fortschritt) * z + z / 2;
      const farbe = a.spieler[i].farbe;
      const radius = z * 0.38;

      ctx.beginPath();
      ctx.arc(px, py, radius, 0, Math.PI * 2);
      ctx.fillStyle = farbe;
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = this.beamer ? '#0e121a' : '#ffffff';
      ctx.stroke();

      /* Akku als Ring */
      const anteil = Math.max(0, Math.min(1, r.akku / 100));
      ctx.beginPath();
      ctx.arc(px, py, radius + 3.5, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * anteil);
      ctx.lineWidth = 3;
      ctx.strokeStyle = anteil > 0.3 ? '#2f9e44' : '#e03131';
      ctx.stroke();

      /* Ladung als Zahl */
      ctx.fillStyle = '#ffffff';
      ctx.font = `bold ${Math.round(z * 0.4)}px system-ui, sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(String(r.ladung.length), px, py + 1);

      if (r.laedt > 0) {
        ctx.fillStyle = '#f5d020';
        ctx.font = `bold ${Math.round(z * 0.42)}px system-ui, sans-serif`;
        ctx.fillText('⚡', px + radius, py - radius);
      }

      if (this.pfeileZeigen) this._pfeilZeichnen(index, i, px, py, radius, farbe);
    });

    /* Rammen im aktuellen Tick hervorheben */
    if (jetzt.ereignisse) {
      jetzt.ereignisse.filter((e) => e.art === 'rammen').forEach((e) => {
        const opfer = jetzt.roboter[e.auf];
        ctx.beginPath();
        ctx.arc(opfer.x * z + z / 2, opfer.y * z + z / 2, z * 0.55, 0, Math.PI * 2);
        ctx.strokeStyle = '#e03131';
        ctx.lineWidth = 3;
        ctx.globalAlpha = 0.55 + 0.45 * (1 - fortschritt);
        ctx.stroke();
        ctx.globalAlpha = 1;
      });
    }
  }

  /* Kachel mit Punktzahl: das Zeichen klein oben links, der Wert groß in der Mitte.
     Weiß mit dunklem Rand, damit er auch auf verblassten Kacheln lesbar bleibt. */
  _wertZeichnen(mx, my, sorte, wert) {
    const ctx = this.ctx;
    const z = this.zelle;
    const x0 = mx * z;
    const y0 = my * z;
    const text = String(wert);
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.lineJoin = 'round';
    if (z >= 20) {
      ctx.font = `bold ${Math.round(z * 0.24)}px system-ui, sans-serif`;
      ctx.fillStyle = sorte === 'radioaktiv' ? '#f5d020' : 'rgba(255,255,255,0.9)';
      ctx.fillText(sorte === 'radioaktiv' ? '☢' : (SORTEN_ZEICHEN[sorte] || '?'),
                   x0 + z * 0.24, y0 + z * 0.24);
    }
    const groesse = text.length >= 4 ? 0.3 : 0.36;
    ctx.font = `bold ${Math.round(z * groesse)}px system-ui, sans-serif`;
    ctx.lineWidth = Math.max(2, z * 0.09);
    ctx.strokeStyle = 'rgba(0,0,0,0.55)';
    ctx.strokeText(text, x0 + z / 2, y0 + z * 0.6);
    ctx.fillStyle = '#ffffff';
    ctx.fillText(text, x0 + z / 2, y0 + z * 0.6);
  }

  /* Wohin fährt der Roboter im nächsten Zug? Steht in der Aufzeichnung schon drin —
     der Pfeil zeigt es nur an. Kein Pfeil, wenn er stehen bleibt. */
  _pfeilZeichnen(index, i, px, py, radius, farbe) {
    const naechster = this.zustandVon(index + 1);
    const jetzt = this.zustandVon(index);
    if (!naechster || naechster === jetzt) return;
    const dx = Math.sign(naechster.roboter[i].x - jetzt.roboter[i].x);
    const dy = Math.sign(naechster.roboter[i].y - jetzt.roboter[i].y);
    if (!dx && !dy) return;
    const ctx = this.ctx;
    const spitze = radius * 1.95;
    const basis = radius * 1.3;
    const breite = radius * 0.55;
    const sx = px + dx * spitze;
    const sy = py + dy * spitze;
    const bx = px + dx * basis;
    const by = py + dy * basis;
    ctx.beginPath();
    ctx.moveTo(sx, sy);
    ctx.lineTo(bx - dy * breite, by + dx * breite);
    ctx.lineTo(bx + dy * breite, by - dx * breite);
    ctx.closePath();
    ctx.fillStyle = farbe;
    ctx.fill();
    ctx.lineWidth = 1.5;
    ctx.strokeStyle = this.beamer ? '#0e121a' : '#ffffff';
    ctx.stroke();
  }

  _rundesRechteck(x, y, breite, hoehe, radius) {
    const ctx = this.ctx;
    ctx.beginPath();
    ctx.moveTo(x + radius, y);
    ctx.arcTo(x + breite, y, x + breite, y + hoehe, radius);
    ctx.arcTo(x + breite, y + hoehe, x, y + hoehe, radius);
    ctx.arcTo(x, y + hoehe, x, y, radius);
    ctx.arcTo(x, y, x + breite, y, radius);
    ctx.closePath();
  }
}

/* --------------------------------------------------------------- Wiedergabe */

class Wiedergabe {
  constructor(spielfeld, aufRahmen) {
    this.spielfeld = spielfeld;
    this.aufRahmen = aufRahmen || (() => {});
    this.aufEnde = null;
    this.index = 0;
    this.laeuft = false;
    this.tempo = 1;
    /* 1× ist bewusst gemächlich: 120 ms je Tick, eine Runde zu 400 Ticks dauert
       damit 48 Sekunden. Die K.-o.-Bühne in arena.js nutzt dasselbe Maß. */
    this.msProTick = 120;
    this.letzteZeit = 0;
    this.fortschritt = 1;
    this.aufzeichnung = null;
    /* Wird die Spalte gezogen oder das Fenster geändert, bekommt der Canvas eine
       neue Auflösung — und muss danach einmal neu gezeichnet werden. Steht hier
       und nicht in der Werkstatt, damit der FSR-Modus es genauso bekommt. */
    this.beobachter = null;
    if (window.ResizeObserver) {
      this.beobachter = new ResizeObserver(() => {
        if (this.spielfeld.groesseAnpassen()) this.zeichne();
      });
      this.beobachter.observe(this.spielfeld.canvas);
    }
  }

  /* Vor dem Ersetzen aufrufen: Der Beobachter hielte sonst Canvas und
     Aufzeichnung am Leben — bei jedem Reiterwechsel einer mehr. */
  verwerfen() {
    this.pause();
    if (this.beobachter) {
      this.beobachter.disconnect();
      this.beobachter = null;
    }
  }

  laden(aufzeichnung) {
    this.aufzeichnung = aufzeichnung;
    this.spielfeld.laden(aufzeichnung);
    this.index = 0;
    this.fortschritt = 1;
    this.pause();
    this.zeichne();
  }

  get laenge() {
    return this.aufzeichnung ? this.aufzeichnung.ticks.length : 0;
  }

  zeichne() {
    this.spielfeld.zeichne(this.index, this.fortschritt);
    this.aufRahmen(this.index);
  }

  springe(index) {
    this.index = Math.max(0, Math.min(this.laenge, Math.round(index)));
    this.fortschritt = 1;
    this.zeichne();
  }

  schritt(richtung) {
    this.pause();
    this.springe(this.index + richtung);
  }

  start() {
    if (!this.aufzeichnung || this.laeuft) return;
    if (this.index >= this.laenge) this.index = 0;
    this.laeuft = true;
    this.letzteZeit = performance.now();
    const rahmen = (jetzt) => {
      if (!this.laeuft) return;
      const vergangen = jetzt - this.letzteZeit;
      const dauer = this.msProTick / this.tempo;
      this.fortschritt = Math.min(1, this.fortschritt + vergangen / dauer);
      this.letzteZeit = jetzt;
      if (this.fortschritt >= 1) {
        if (this.index >= this.laenge) {
          this.pause();
          this.zeichne();
          if (this.aufEnde) this.aufEnde();
          return;
        }
        this.index += 1;
        this.fortschritt = this.tempo >= 8 ? 1 : 0;
      }
      this.zeichne();
      requestAnimationFrame(rahmen);
    };
    requestAnimationFrame(rahmen);
  }

  pause() {
    this.laeuft = false;
    this.fortschritt = 1;
  }

  umschalten() {
    if (this.laeuft) this.pause(); else this.start();
  }
}

window.Spielfeld = Spielfeld;
window.Wiedergabe = Wiedergabe;
window.SORTEN_FARBEN = SORTEN_FARBEN;
