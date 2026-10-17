#!/usr/bin/env python3
"""Müllsammel-Roboter Turnier — Werkstatt und FSR-Modus starten.

    python3 start.py                # Werkstatt öffnen
    python3 start.py --port 8080
    python3 start.py --kein-browser

Braucht nur Python 3.10 oder neuer. Keine Installation, keine Bibliotheken.
"""

import argparse
import os
import sys
import threading
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MINDESTVERSION = (3, 10)
if sys.version_info < MINDESTVERSION:
    print("Dieses Programm braucht Python %d.%d oder neuer, gefunden wurde %d.%d."
          % (MINDESTVERSION + sys.version_info[:2]))
    raise SystemExit(1)

from engine import config as config_modul   # noqa: E402
from web import api                         # noqa: E402
from web.server import Anwendung, server_bauen   # noqa: E402


ARBEITSORDNER = ("abgaben", "aufzeichnungen", "turnier")


def ordner_anlegen():
    """Ein frisch entpacktes Archiv bringt leere Ordner oft nicht mit."""
    hier = os.path.dirname(os.path.abspath(__file__))
    for name in ARBEITSORDNER:
        os.makedirs(os.path.join(hier, name), exist_ok=True)


def main(argv=None):
    zerleger = argparse.ArgumentParser(description="Müllsammel-Roboter Turnier")
    zerleger.add_argument("--port", type=int, default=None)
    zerleger.add_argument("--kein-browser", action="store_true")
    zerleger.add_argument("--config", default=None)
    args = zerleger.parse_args(argv)

    ordner_anlegen()
    try:
        anwendung = Anwendung(args.config)
    except (OSError, ValueError) as fehler:
        print("Die config.json lässt sich nicht laden:\n  %s" % fehler)
        return 1
    api.registriere(anwendung)

    port = args.port or anwendung.config.server.port
    server = None
    for versuch in range(20):
        try:
            server = server_bauen(anwendung, port + versuch)
            port = server.server_address[1]
            break
        except (OSError, OverflowError):
            continue
    if server is None:
        print("Kein freier Port zwischen %d und %d gefunden."
              % (port, port + 19))
        return 1

    adresse = "http://127.0.0.1:%d/" % port
    print("Müllsammel-Roboter Turnier")
    print("  Werkstatt: %s" % adresse)
    print("  Beenden:   Strg+C")
    if not args.kein_browser and anwendung.config.server.browser_oeffnen:
        threading.Timer(0.4, lambda: webbrowser.open(adresse)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nAuf Wiedersehen.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
