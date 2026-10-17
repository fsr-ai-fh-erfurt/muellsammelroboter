"""Tick-Schleife, Bewegungsauflösung und Wertung.

Die maßgebliche Beschreibung steht in SPEC.md §2 und §7. Wer hier etwas ändert,
ändert die SPEC mit — und nimmt die Golden Tests neu auf.
"""

from .world import Welt, RICHTUNGEN, RICHTUNGS_REIHENFOLGE, SORTE_RADIOAKTIV

AKTIONEN = ("oben", "unten", "links", "rechts", "warte", "presse")


class Ergebnis:
    def __init__(self, seed, ticks, roboter, sieger, reihenfolge, unentschieden):
        self.seed = seed
        self.ticks = ticks
        self.roboter = roboter
        self.sieger = sieger
        self.reihenfolge = reihenfolge
        self.unentschieden = unentschieden

    def als_dict(self):
        return {
            "seed": self.seed,
            "ticks": self.ticks,
            "roboter": self.roboter,
            "sieger": self.sieger,
            "reihenfolge": self.reihenfolge,
            "unentschieden": self.unentschieden,
        }


class Spiel:
    """Eine Runde. `bots` sind Anschlüsse mit .name und .frage(sicht) -> (aktion, regel)."""

    def __init__(self, config, bots, seed, spieler=None, runden_laenge=None,
                 aufzeichnen=True):
        self.config = config
        self.bots = list(bots)
        namen = [getattr(b, "name", "Roboter %d" % i) for i, b in enumerate(self.bots)]
        self.runden_laenge = (config.spiel.runden_laenge if runden_laenge is None
                              else runden_laenge)
        self.welt = Welt(config, namen, seed, spieler=spieler)
        # Turnier und Vorführung spielen manchmal kürzer als in der config.json. Die
        # Bots erfahren die Länge über die Sicht (`restliche_ticks`) — also muss die
        # Welt die tatsächlich gespielte Länge kennen, nicht die aus der Datei.
        self.welt.runden_laenge = self.runden_laenge
        self.beendet = False
        self.aufzeichnen = aufzeichnen
        self.ticks = []              # je Tick: Abbild + Aktionen + Ereignisse
        self.start_abbild = self.welt.abbild() if aufzeichnen else None
        self.ergebnis = None
        self.abrechnung = {}

    # ------------------------------------------------------------------ Schleife

    def spiele(self):
        while not self.beendet:
            self.schritt()
        return self.ergebnis

    def schritt(self):
        if self.beendet:
            return None
        w = self.welt
        cfg = self.config
        w.tick += 1
        ereignisse = []

        # 1. Bonuszone
        if w.tick % cfg.zone.wechsel_alle == 0:
            w._zone_neu()
            ereignisse.append({"art": "zone", "x": w.zone[0], "y": w.zone[1]})

        # 2. Nachschub
        if w.tick % cfg.muell.nachschub_intervall == 0:
            neu = w._muell_streuen(cfg.muell.nachschub_anzahl)
            if neu:
                ereignisse.append({"art": "nachschub", "anzahl": len(neu)})

        # Für die Akku-Regel (§6): wer in diesem Tick auf 0 fällt, verliert die Ladung.
        akku_vorher = [r.akku for r in w.roboter]

        # 3./4. Aktionen einholen (Startreihenfolge, alle sehen den Stand vom Tickbeginn)
        rohe = []
        regeln = []
        for r in w.roboter:
            sicht = w.sicht(r.index)
            aktion, regel = self.bots[r.index].frage(sicht)
            if aktion not in AKTIONEN:
                aktion = "warte"
            rohe.append(aktion)
            regeln.append(regel)

        # 5. Filtern: Presse, Ladepause und Langsamkeit
        aktionen = []
        # Pausen sind keine eigenen Bewegungsversuche. Ein Standstreit-Flag aus dem
        # letzten Versuch überdauert sie, sonst verfiele es in langsamen Ticks, in
        # denen der Ausweichzug ohnehin verworfen würde.
        pausiert = [False] * len(w.roboter)
        langsam_tick = w.tick % cfg.akku.langsam_modulo == cfg.akku.langsam_rest
        for r in w.roboter:
            aktion = rohe[r.index]
            if r.presse_ticks > 0:
                # Eine laufende Presse zählt herunter und hält den Roboter fest.
                r.presse_ticks -= 1
                if r.presse_ticks == 0:
                    eintrag = self._presse_abschliessen(r)
                    if eintrag:
                        ereignisse.append(eintrag)
                aktion = "warte"
                pausiert[r.index] = True
            elif r.lade_ticks > 0:
                r.lade_ticks -= 1
                aktion = "warte"
                pausiert[r.index] = True
            elif r.akku < cfg.akku.langsam_ab and langsam_tick:
                aktion = "warte"
                pausiert[r.index] = True
            if aktion == "presse":
                if self._presse_starten(r):
                    if r.presse_ticks == 0:
                        eintrag = self._presse_abschliessen(r)
                        if eintrag:
                            ereignisse.append(eintrag)
                aktion = "warte"
                pausiert[r.index] = True
            aktionen.append(aktion)

        # 6. Bewegung
        ereignisse.extend(self._bewegung_aufloesen(aktionen, pausiert))

        # 7./8. Aufnahme und Abliefern
        for r in w.roboter:
            eintrag = self._abliefern(r)
            if eintrag:
                ereignisse.append(eintrag)

        # 9. Akku leer: Wer in diesem Tick auf 0 gefallen ist und es nicht mehr bis
        # ins Depot geschafft hat, verliert seine Ladung — bis auf radioaktive Fässer.
        for r in w.roboter:
            eintrag = self._akku_leer(r, akku_vorher[r.index])
            if eintrag:
                ereignisse.append(eintrag)

        if self.aufzeichnen:
            self.ticks.append({
                "tick": w.tick,
                "aktionen": list(aktionen),
                "gewuenscht": list(rohe),
                "regeln": list(regeln),
                "ereignisse": ereignisse,
                **w.abbild(),
            })

        if w.tick >= self.runden_laenge:
            self._beenden()
        return self.ticks[-1] if self.aufzeichnen else None

    # ------------------------------------------------------------------ Bewegung

    def _bewegung_aufloesen(self, aktionen, pausiert=None):
        """SPEC §7. Reihenfolge A–F, vollständig deterministisch."""
        w = self.welt
        cfg = self.config
        roboter = w.roboter
        n = len(roboter)
        ereignisse = []
        if pausiert is None:
            pausiert = [False] * n

        pos = [(r.x, r.y) for r in roboter]
        besetzt = {p: i for i, p in enumerate(pos)}
        richtung = [RICHTUNGEN.get(a) for a in aktionen]
        # Das Flag beschreibt den letzten Bewegungsversuch (nicht Pausenticks);
        # sicht() läuft vor dieser Auflösung.
        for i, r in enumerate(roboter):
            if not pausiert[i]:
                r.blockiert = False

        # A — Wunschfelder
        wunsch = []
        for i in range(n):
            d = richtung[i]
            if d is None:
                wunsch.append(pos[i])
                continue
            ziel = (pos[i][0] + d[0], pos[i][1] + d[1])
            if w.ist_blockiert(*ziel):
                richtung[i] = None
                wunsch.append(pos[i])
            else:
                wunsch.append(ziel)

        status = ["offen"] * n       # offen | steht | bewegt | geschoben
        tausch_paare = []

        # B — Platztausch gilt als Rammen für beide, niemand bewegt sich
        for i in range(n):
            for j in range(i + 1, n):
                if status[i] == "offen" and status[j] == "offen" \
                        and wunsch[i] == pos[j] and wunsch[j] == pos[i]:
                    status[i] = status[j] = "steht"
                    wunsch[i], wunsch[j] = pos[i], pos[j]
                    tausch_paare.append((i, j))

        # C — umstrittene Zielfelder: alle bleiben stehen
        gruppen = {}
        for i in range(n):
            if status[i] == "offen" and wunsch[i] != pos[i]:
                gruppen.setdefault(wunsch[i], []).append(i)
        for feld in sorted(gruppen):
            gruppe = gruppen[feld]
            if len(gruppe) >= 2:
                for i in gruppe:
                    status[i] = "steht"
                    wunsch[i] = pos[i]
                    roboter[i].blockiert = True

        # Wer gar nicht weg will, steht
        for i in range(n):
            if status[i] == "offen" and wunsch[i] == pos[i]:
                status[i] = "steht"

        # D — Nachrücken bis nichts mehr passiert
        neue_pos = list(pos)
        geaendert = True
        while geaendert:
            geaendert = False
            for i in range(n):
                if status[i] != "offen":
                    continue
                belegt_von = besetzt.get(wunsch[i])
                if belegt_von is None or status[belegt_von] in ("bewegt", "geschoben"):
                    status[i] = "bewegt"
                    neue_pos[i] = wunsch[i]
                    geaendert = True

        # E/F — was offen blieb: Rammen oder Ring.
        # Erst einordnen, dann festschreiben: würde man `status` schon in der ersten
        # Schleife setzen, machte man den letzten Roboter eines Rings zum Rammer.
        offene = [i for i in range(n) if status[i] == "offen"]
        rammer = []
        for i in offene:
            j = besetzt.get(wunsch[i])
            if j is not None and status[j] == "steht":
                rammer.append((i, j))
        angreifer = {i for i, _ in rammer}
        for i in offene:
            if i not in angreifer:
                # Ring aus drei oder mehr, oder Warteschlange hinter einem Rammenden
                status[i] = "steht"
                roboter[i].blockiert = True

        # Platztausch abrechnen (kein Schub, aber Klauen und Energie)
        for i, j in tausch_paare:
            a, b = roboter[i], roboter[j]
            geklaut_a, geklaut_b = self._klauen_gegenseitig(a, b)
            a.akku = max(0, a.akku - cfg.akku.kosten_rammen)
            b.akku = max(0, b.akku - cfg.akku.kosten_rammen)
            a.statistik["rammangriffe"] += 1
            b.statistik["rammangriffe"] += 1
            a.statistik["gerammt_worden"] += 1
            b.statistik["gerammt_worden"] += 1
            ereignisse.append({
                "art": "rammen", "von": i, "auf": j, "geschoben": False, "tausch": True,
                "geklaut": geklaut_a["sorte"] if geklaut_a else None,
            })
            ereignisse.append({
                "art": "rammen", "von": j, "auf": i, "geschoben": False, "tausch": True,
                "geklaut": geklaut_b["sorte"] if geklaut_b else None,
            })

        # Rammen in Startreihenfolge
        for i, j in rammer:
            a, o = roboter[i], roboter[j]
            d = richtung[i]
            schub_ziel = (neue_pos[j][0] + d[0], neue_pos[j][1] + d[1])
            belegt_jetzt = {neue_pos[k] for k in range(n) if k != j}
            geschoben = (not w.ist_blockiert(*schub_ziel)) and schub_ziel not in belegt_jetzt
            if geschoben:
                neue_pos[j] = schub_ziel
                neue_pos[i] = wunsch[i]
                status[i] = "bewegt"
                status[j] = "geschoben"
            else:
                status[i] = "steht"

            geklaut = self._klauen(a, o)
            a.akku = max(0, a.akku - cfg.akku.kosten_rammen)
            o.akku = max(0, o.akku - cfg.akku.kosten_rammen)
            a.statistik["rammangriffe"] += 1
            o.statistik["gerammt_worden"] += 1
            ereignisse.append({
                "art": "rammen", "von": i, "auf": j, "geschoben": geschoben,
                "tausch": False, "geklaut": geklaut["sorte"] if geklaut else None,
            })

        # Positionen übernehmen, Energie für eigene Bewegung abziehen
        for i in range(n):
            r = roboter[i]
            if neue_pos[i] != pos[i]:
                r.x, r.y = neue_pos[i]
                if status[i] == "bewegt":
                    r.akku = max(0, r.akku - cfg.akku.kosten_bewegung)
                    r.statistik["bewegungen"] += 1

        # 7. Zwangsaufnahme für alle, die ihr Feld gewechselt haben
        for i in range(n):
            if neue_pos[i] == pos[i]:
                continue
            eintrag = self._aufnehmen(roboter[i])
            if eintrag:
                ereignisse.append(eintrag)

        return ereignisse

    # ------------------------------------------------------------------ Aktionen

    def _klauen(self, angreifer, opfer):
        if len(angreifer.ladung) >= self.welt.kapazitaet or not opfer.ladung:
            return None
        index = self.welt.zufall.zahl(len(opfer.ladung))
        teil = opfer.ladung.pop(index)
        angreifer.ladung.append(teil)
        angreifer.statistik["geklaut"] += 1
        opfer.statistik["bestohlen"] += 1
        self._presse_pruefen(opfer)
        return teil

    def _klauen_gegenseitig(self, a, b):
        """Beim Platztausch klauen beide gleichzeitig — Auswahl vor jeder Änderung."""
        kap = self.welt.kapazitaet
        idx_a = self.welt.zufall.zahl(len(b.ladung)) if (b.ladung and len(a.ladung) < kap) else None
        idx_b = self.welt.zufall.zahl(len(a.ladung)) if (a.ladung and len(b.ladung) < kap) else None
        teil_a = b.ladung[idx_a] if idx_a is not None else None
        teil_b = a.ladung[idx_b] if idx_b is not None else None
        if idx_a is not None:
            b.ladung.pop(idx_a)
        if idx_b is not None:
            a.ladung.pop(idx_b)
        if teil_a is not None:
            a.ladung.append(teil_a)
            a.statistik["geklaut"] += 1
            b.statistik["bestohlen"] += 1
        if teil_b is not None:
            b.ladung.append(teil_b)
            b.statistik["geklaut"] += 1
            a.statistik["bestohlen"] += 1
        self._presse_pruefen(a)
        self._presse_pruefen(b)
        return teil_a, teil_b

    # ------------------------------------------------------------------ Presse

    def _presse_starten(self, r):
        """Beginnt das Pressen. Gibt zurück, ob es losgeht.

        Gepresst wird die Sorte, von der die meisten Teile an Bord sind (bei
        Gleichstand die alphabetisch erste) — eine feste Regel, damit derselbe
        Spielstand immer dieselbe Entscheidung ergibt. Nur Teile mit positivem
        Wert lassen sich pressen; abgewertete Teile zählen nicht mit.
        """
        cfg = self.config.presse
        zaehler = {}
        for teil in r.ladung:
            if teil.get("gepresst") or teil["sorte"] == SORTE_RADIOAKTIV \
                    or teil["wert"] <= 0:
                continue
            zaehler[teil["sorte"]] = zaehler.get(teil["sorte"], 0) + 1
        moeglich = [sorte for sorte, anzahl in zaehler.items() if anzahl >= cfg.anzahl]
        if not moeglich:
            return False
        r.presse_sorte = min(moeglich, key=lambda sorte: (-zaehler[sorte], sorte))
        r.presse_ticks = max(0, cfg.dauer_ticks - 1)
        return True

    def _presse_abschliessen(self, r):
        """Macht aus den Teilen den Ballen. Gibt das Ereignis zurück (oder None)."""
        cfg = self.config.presse
        sorte = r.presse_sorte
        r.presse_ticks = 0
        r.presse_sorte = None
        if sorte is None:
            return None
        nummeriert = [(i, teil) for i, teil in enumerate(r.ladung)
                      if teil["sorte"] == sorte and not teil.get("gepresst")
                      and teil["wert"] > 0]
        if len(nummeriert) < cfg.anzahl:
            return None
        # Die billigsten Teile zuerst: Sie kosten am wenigsten, wenn 20 % wegfallen.
        nummeriert.sort(key=lambda paar: (paar[1]["wert"], paar[0]))
        ausgewaehlt = nummeriert[:cfg.anzahl]
        summe = sum(teil["wert"] for _, teil in ausgewaehlt)
        for index in sorted((i for i, _ in ausgewaehlt), reverse=True):
            del r.ladung[index]
        wert = summe * (100 - cfg.abschlag_prozent) // 100
        r.ladung.append({"sorte": "ballen", "wert": wert, "gepresst": True})
        r.statistik["gepresst"] += 1
        return {"art": "presse", "wer": r.index, "sorte": sorte,
                "anzahl": cfg.anzahl, "wert": wert}

    def _presse_pruefen(self, r):
        """Bricht eine laufende Presse ab, wenn die Teile nicht mehr reichen.

        Wird ein Roboter während des Pressens bestohlen und fällt die Sorte damit
        unter die nötige Anzahl, ist die Presse hinfällig — es sind ja keine drei
        gleichen mehr. Dasselbe gilt, wenn unter den Teilen keins mehr einen
        positiven Wert hat: Solche Teile lassen sich nicht pressen.
        """
        if r.presse_ticks <= 0:
            return
        anzahl = sum(1 for teil in r.ladung
                     if teil["sorte"] == r.presse_sorte and not teil.get("gepresst")
                     and teil["wert"] > 0)
        if anzahl < self.config.presse.anzahl:
            r.presse_ticks = 0
            r.presse_sorte = None

    def _akku_leer(self, r, vorher):
        """SPEC §6: Fällt der Akku in diesem Tick auf 0, verschwindet die Ladung.

        Nur im Moment des Fallens, nicht in jedem Tick mit leerem Akku: Abliefern lädt
        nach der Zahl der Teile, ein Roboter ohne Ladung käme sonst nie wieder hoch.
        Radioaktive Fässer bleiben — doppelt bestraft, wer leer fährt und eins trägt.
        """
        if not self.config.akku.leer_verliert_ladung:
            return None
        if vorher <= 0 or r.akku > 0:
            return None
        verloren = [teil for teil in r.ladung if teil["sorte"] != SORTE_RADIOAKTIV]
        if not verloren:
            return None
        r.ladung = [teil for teil in r.ladung if teil["sorte"] == SORTE_RADIOAKTIV]
        r.statistik["verloren"] += len(verloren)
        self._presse_pruefen(r)
        return {"art": "akku_leer", "wer": r.index,
                "teile": [{"sorte": t["sorte"], "wert": t["wert"]} for t in verloren]}

    def _aufnehmen(self, r):
        w = self.welt
        stueck = w.muell.get((r.x, r.y))
        if stueck is None or len(r.ladung) >= w.kapazitaet:
            return None
        wert = w.aufnahme_wert(stueck)
        del w.muell[(r.x, r.y)]
        r.ladung.append({"sorte": stueck.sorte, "wert": wert})
        r.statistik["aufgenommen"] += 1
        return {"art": "aufnahme", "wer": r.index, "sorte": stueck.sorte, "wert": wert,
                "x": r.x, "y": r.y}

    def _abliefern(self, r):
        if (r.x, r.y) != r.depot or not r.ladung:
            return None
        cfg = self.config
        anzahl = len(r.ladung)
        summe = sum(teil["wert"] for teil in r.ladung)
        # Welche Teile im Depot gelandet sind, steht mit im Ereignis — die Show im
        # FSR-Modus zeigt sie neben dem Feld an, ohne selbst etwas rechnen zu müssen.
        teile = [{"sorte": teil["sorte"], "wert": teil["wert"]} for teil in r.ladung]
        r.punkte += summe
        r.ladung = []
        r.statistik["abgeliefert_stueck"] += anzahl
        r.statistik["abgeliefert_punkte"] += summe

        nominal = (anzahl * cfg.akku.max) // self.welt.kapazitaet
        gewinn = min(cfg.akku.max - r.akku, nominal)
        if gewinn > 0:
            r.akku += gewinn
            pro_tick = max(1, cfg.akku.max * cfg.akku.laden_prozent_pro_tick // 100)
            r.lade_ticks = (gewinn + pro_tick - 1) // pro_tick
        return {"art": "abliefern", "wer": r.index, "anzahl": anzahl, "punkte": summe,
                "geladen": gewinn, "lade_ticks": r.lade_ticks, "teile": teile}

    # ------------------------------------------------------------------ Schluss

    def _beenden(self):
        cfg = self.config
        teiler = cfg.rundenende.positiv_teiler
        # Die Abrechnung der Ladung Teil für Teil: Die Show spielt sie am Ende einzeln
        # vor, statt den Endstand einfach hinzuschreiben.
        self.abrechnung = {}
        for r in self.welt.roboter:
            posten = []
            vorher = r.punkte
            for teil in r.ladung:
                wert = teil["wert"]
                punkte = wert if wert < 0 else wert // teiler
                r.punkte += punkte
                posten.append({"sorte": teil["sorte"], "wert": wert, "punkte": punkte})
            r.ladung = []
            self.abrechnung[r.index] = {"punkte_vorher": vorher, "posten": posten}
        self.beendet = True
        self.ergebnis = self._auswerten()

    def _auswerten(self):
        eintraege = []
        for r in self.welt.roboter:
            eintraege.append({
                "index": r.index,
                "name": r.name,
                "punkte": r.punkte,
                "akku": r.akku,
                "statistik": dict(r.statistik),
                "abrechnung": self.abrechnung.get(
                    r.index, {"punkte_vorher": r.punkte, "posten": []}),
            })
        reihenfolge = sorted(
            range(len(eintraege)),
            key=lambda i: (
                -eintraege[i]["punkte"],
                -eintraege[i]["akku"],
                -eintraege[i]["statistik"]["abgeliefert_stueck"],
                i,
            ),
        )
        erster = reihenfolge[0]
        unentschieden = False
        if len(reihenfolge) > 1:
            zweiter = reihenfolge[1]
            a, b = eintraege[erster], eintraege[zweiter]
            if (a["punkte"], a["akku"], a["statistik"]["abgeliefert_stueck"]) == \
               (b["punkte"], b["akku"], b["statistik"]["abgeliefert_stueck"]):
                unentschieden = True
        return Ergebnis(
            seed=self.welt.seed,
            ticks=self.welt.tick,
            roboter=eintraege,
            sieger=None if unentschieden else erster,
            reihenfolge=reihenfolge,
            unentschieden=unentschieden,
        )
