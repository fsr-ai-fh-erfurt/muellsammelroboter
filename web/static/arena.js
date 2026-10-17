/* Die Bühne für die K.-o.-Runden. Die Show zeigt eine Partie zur Zeit; die Bühne
   kann aber beliebig viele Spielfelder im Takt abspielen.

   Hier steht ausschließlich Darstellung. Die Aufzeichnungen kommen aus Python,
   der Browser entscheidet nichts.
   Baut auf `Spielfeld` aus spielfeld.js auf. */

class Buehne {
  constructor(raster) {
    this.raster = raster;
    this.duelle = [];
    this.index = 0;
    this.laenge = 0;
    this.laeuft = false;
    this.tempo = 1;
    this.msProTick = 120;   // wie Wiedergabe in spielfeld.js
    this.fortschritt = 1;
    this.letzteZeit = 0;
    this.beendet = false;
    this.aufRahmen = null;
    this.aufEnde = null;
    /* Wird das Fenster geändert oder in den Vollbild gewechselt, bekommt jedes
       Spielfeld eine neue Auflösung und muss einmal neu gezeichnet werden. */
    this.beobachter = null;
    if (window.ResizeObserver) {
      this.beobachter = new ResizeObserver(() => {
        if (this.duelle.some((d) => d.spielfeld.groesseAnpassen())) this.zeichne();
      });
      this.beobachter.observe(raster);
    }
  }

  /* Vor dem Ersetzen aufrufen — sonst hält der Beobachter Raster, Felder und
     Aufzeichnungen der alten Runde am Leben. */
  verwerfen() {
    this.pause();
    if (this.beobachter) {
      this.beobachter.disconnect();
      this.beobachter = null;
    }
  }

  /* Ein Duell aufnehmen: Aufzeichnung, Spielfeld und die Textknoten am Rand. */
  anlegen(duell) {
    this.duelle.push(duell);
    if (duell.aufzeichnung) {
      this.laenge = Math.max(this.laenge, duell.aufzeichnung.ticks.length);
      duell.spielfeld.laden(duell.aufzeichnung);
    }
    if (duell.karte) duell.karte.classList.add('geladen');
  }

  /* Im Vollbild soll die ganze Runde auf den Schirm passen. `breite` und `hoehe`
     sind der verfügbare Platz des Rasters; für jede Karte wird abgezogen, was
     Kopf, Fuß und Innenabstand ohnehin belegen. `0, 0` setzt die Grenzen zurück,
     dann gilt wieder die angezeigte Breite. */
  platzSetzen(breite, hoehe) {
    if (!this.duelle.length) return;
    const spalten = Math.max(1,
      getComputedStyle(this.raster).gridTemplateColumns.split(' ').filter(Boolean).length);
    const zeilen = Math.ceil(this.duelle.length / spalten);
    const proSpalte = breite > 0 ? (breite - 12 * (spalten - 1)) / spalten : 0;
    const proZeile = hoehe > 0 ? (hoehe - 12 * (zeilen - 1)) / zeilen : 0;
    this.duelle.forEach((d) => {
      const rahmen = d.karte ? this._rahmen(d.karte) : { breite: 0, hoehe: 0 };
      d.spielfeld.breitePlatz = proSpalte > 0
        ? Math.max(120, proSpalte - rahmen.breite - 2) : 0;
      d.spielfeld.hoehePlatz = proZeile > 0
        ? Math.max(120, proZeile - rahmen.hoehe - 2) : 0;
      d.spielfeld.groesseAnpassen();
    });
  }

  /* Was Kopf, Fuß, Innenabstand und Rahmen einer Karte belegen — unabhängig
     davon, wie groß das Feld gerade gezeichnet ist. Über
     `clientHeight - canvas.clientHeight` gemessen ging es schief, sobald eine
     neue Runde im Vollbild geladen wurde: Das frische Canvas war dann noch
     240 Pixel groß, und der „Rahmen" schien den halben Schirm zu fressen. */
  _rahmen(karte) {
    const zahl = (wert) => parseFloat(wert) || 0;
    const stil = getComputedStyle(karte);
    const kopf = karte.querySelector('.duell-kopf');
    const fuss = karte.querySelector('.duell-fuss');
    const kopfStil = kopf ? getComputedStyle(kopf) : null;
    const fussStil = fuss ? getComputedStyle(fuss) : null;
    return {
      breite: zahl(stil.paddingLeft) + zahl(stil.paddingRight)
        + zahl(stil.borderLeftWidth) + zahl(stil.borderRightWidth),
      hoehe: zahl(stil.paddingTop) + zahl(stil.paddingBottom)
        + zahl(stil.borderTopWidth) + zahl(stil.borderBottomWidth)
        + (kopf ? kopf.offsetHeight + zahl(kopfStil.marginTop)
          + zahl(kopfStil.marginBottom) : 0)
        + (fuss ? fuss.offsetHeight + zahl(fussStil.marginTop)
          + zahl(fussStil.marginBottom) : 0),
    };
  }

  zeichne() {
    const index = this.index;
    this.duelle.forEach((d) => {
      if (!d.aufzeichnung) return;
      d.spielfeld.zeichne(index, this.fortschritt);
      const zustand = d.spielfeld.zustandVon(index);
      if (!zustand) return;
      /* Wer `aufZeichnen` mitgibt, trägt Punkte und Führung selbst ein — die
         K.-o.-Show braucht dazu Ladung und Depot aus demselben Zustand. */
      if (d.aufZeichnen) {
        d.aufZeichnen(zustand, index);
        return;
      }
      const punkte = zustand.roboter.map((r) => r.punkte);
      if (d.punkte[0]) d.punkte[0].textContent = punkte[0];
      if (d.punkte[1]) d.punkte[1].textContent = punkte[1];
      if (d.karte) {
        d.karte.classList.toggle('fuehrt-a', punkte[0] > punkte[1]);
        d.karte.classList.toggle('fuehrt-b', punkte[1] > punkte[0]);
      }
    });
    if (this.aufRahmen) this.aufRahmen(this.index, this.laenge);
  }

  springe(index) {
    this.index = Math.max(0, Math.min(this.laenge, Math.round(index)));
    this.fortschritt = 1;
    this.zeichne();
    /* Kein `_endePruefen` hier: Wer den Schieber selbst ans Ende zieht, will die
       Runde ansehen — nicht, dass die Show zur nächsten Runde weiterspringt. */
  }

  /* Direkt zum Endstand — für eine Partie, die schon entschieden aussieht. */
  zumEnde() {
    if (!this.duelle.length) return;
    this.pause();
    this.springe(this.laenge);
    this._endePruefen();
  }

  schritt(richtung) {
    this.pause();
    this.springe(this.index + richtung);
  }

  start() {
    if (!this.duelle.length || this.laeuft) return;
    if (this.index >= this.laenge) {
      this.index = 0;
      this.fortschritt = 1;
      this._wiederbeleben();
    }
    this.beendet = false;
    this.laeuft = true;
    this.duelle.forEach((d) => { if (d.karte) d.karte.classList.add('laeuft'); });
    this.letzteZeit = performance.now();
    const rahmen = (jetzt) => {
      if (!this.laeuft) return;
      const vergangen = jetzt - this.letzteZeit;
      const dauer = this.msProTick / this.tempo;
      this.fortschritt = Math.min(1, this.fortschritt + vergangen / dauer);
      this.letzteZeit = jetzt;
      if (this.fortschritt >= 1) {
        if (this.index >= this.laenge) {
          this.zeichne();
          this._endePruefen();
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
    this.duelle.forEach((d) => { if (d.karte) d.karte.classList.remove('laeuft'); });
  }

  umschalten() {
    if (this.laeuft) this.pause(); else this.start();
  }

  _endePruefen() {
    if (this.index < this.laenge || this.beendet) return;
    this.beendet = true;
    this.pause();
    if (this.aufEnde) this.aufEnde();
  }

  /* Nach einer Feier wieder auf Anfang: die Karten sollen erneut auflodern. */
  _wiederbeleben() {
    this.duelle.forEach((d) => {
      if (!d.karte) return;
      d.karte.classList.remove('gewinner-a', 'gewinner-b');
      d.karte.querySelectorAll('.sieger, .besiegt').forEach((el) => {
        el.classList.remove('sieger', 'besiegt');
      });
      if (d.status) d.status.textContent = 'auf geht’s';
    });
  }
}

/* ------------------------------------------------------------- Konfetti */

class Konfetti {
  constructor() {
    let canvas = document.getElementById('konfetti');
    if (!canvas) {
      canvas = document.createElement('canvas');
      canvas.id = 'konfetti';
      document.body.appendChild(canvas);
    }
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.teilchen = [];
    this.regenBis = 0;
    this.laeuft = false;
    this.farben = ['#3d8bfd', '#e8590c', '#2f9e44', '#ae3ec9', '#f5c542', '#e03131', '#ffffff'];
    this._groesse();
    window.addEventListener('resize', () => this._groesse());
  }

  _groesse() {
    const faktor = window.devicePixelRatio || 1;
    this.breite = window.innerWidth;
    this.hoehe = window.innerHeight;
    this.canvas.width = Math.round(this.breite * faktor);
    this.canvas.height = Math.round(this.hoehe * faktor);
    this.canvas.style.width = this.breite + 'px';
    this.canvas.style.height = this.hoehe + 'px';
    this.ctx.setTransform(faktor, 0, 0, faktor, 0, 0);
  }

  /* Ein Stoß aus einem Punkt — für einen Sieger auf der Bühne. */
  stossen(x, y, anzahl = 36) {
    for (let i = 0; i < anzahl; i++) {
      const winkel = Math.random() * Math.PI * 2;
      const kraft = 2.5 + Math.random() * 7;
      this.teilchen.push({
        x, y,
        vx: Math.cos(winkel) * kraft,
        vy: Math.sin(winkel) * kraft - 3.5,
        groesse: 4 + Math.random() * 5,
        drehung: Math.random() * Math.PI,
        dreh: (Math.random() - 0.5) * 0.35,
        farbe: this.farben[Math.floor(Math.random() * this.farben.length)],
        leben: 80 + Math.random() * 70,
      });
    }
    this._starten();
  }

  /* Regen von oben — für die Siegerehrung. */
  regen(dauer = 5000) {
    this.regenBis = performance.now() + dauer;
    this._starten();
  }

  _starten() {
    if (this.laeuft) return;
    this.laeuft = true;
    requestAnimationFrame((jetzt) => this._tick(jetzt));
  }

  _tick(jetzt) {
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.breite, this.hoehe);
    const regnet = jetzt < this.regenBis;
    if (regnet && Math.random() < 0.55) {
      this.teilchen.push({
        x: Math.random() * this.breite,
        y: -20,
        vx: (Math.random() - 0.5) * 2,
        vy: 2 + Math.random() * 3,
        groesse: 4 + Math.random() * 5,
        drehung: Math.random() * Math.PI,
        dreh: (Math.random() - 0.5) * 0.25,
        farbe: this.farben[Math.floor(Math.random() * this.farben.length)],
        leben: 200,
      });
    }
    this.teilchen = this.teilchen.filter((t) => t.leben > 0 && t.y < this.hoehe + 40);
    this.teilchen.forEach((t) => {
      t.vy += 0.16;
      t.vx *= 0.992;
      t.x += t.vx;
      t.y += t.vy;
      t.drehung += t.dreh;
      t.leben -= 1;
      ctx.save();
      ctx.translate(t.x, t.y);
      ctx.rotate(t.drehung);
      ctx.globalAlpha = Math.max(0, Math.min(1, t.leben / 40));
      ctx.fillStyle = t.farbe;
      ctx.fillRect(-t.groesse / 2, -t.groesse / 2, t.groesse, t.groesse * 0.62);
      ctx.restore();
    });
    if (this.teilchen.length || regnet) {
      requestAnimationFrame((weiter) => this._tick(weiter));
    } else {
      this.laeuft = false;
      ctx.clearRect(0, 0, this.breite, this.hoehe);
    }
  }
}

window.Buehne = Buehne;
window.Konfetti = Konfetti;
