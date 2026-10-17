"""Alle Tests ausführen.

    python3 -m tests.run              # alles
    python3 -m tests.run --golden-neu # Golden Tests neu aufnehmen (nur bewusst!)
    python3 -m tests.run --golden-neu --nur <name>   # nur ein Golden-Szenario
    python3 -m tests.run -v

Einzelne Dateien gehen mit dem üblichen unittest-Weg:

    python3 -m unittest tests.test_web -v
"""

import argparse
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main(argv=None):
    zerleger = argparse.ArgumentParser(description="Testlauf")
    zerleger.add_argument("--golden-neu", action="store_true",
                          help="Golden Tests neu aufnehmen — nur nach bewusster Regeländerung")
    zerleger.add_argument("--nur", default=None, help="nur ein Golden-Szenario aufnehmen")
    zerleger.add_argument("--config-neu", action="store_true",
                          help="beim Aufnehmen auch die eingefrorene config.json erneuern")
    zerleger.add_argument("-v", "--ausfuehrlich", action="store_true")
    args = zerleger.parse_args(argv)

    if (args.nur or args.config_neu) and not args.golden_neu:
        zerleger.error("--nur und --config-neu gehören zu --golden-neu.")

    if args.golden_neu:
        from tests import golden_hilfe
        try:
            namen = golden_hilfe.aufnehmen(nur=args.nur, config_neu=args.config_neu)
        except ValueError as fehler:
            zerleger.error(str(fehler))
        print("Neu aufgenommen: %s" % (", ".join(namen) or "nichts"))
        return 0

    lader = unittest.TestLoader()
    ordner = os.path.dirname(os.path.abspath(__file__))
    sammlung = lader.discover(ordner, pattern="test_*.py",
                              top_level_dir=os.path.dirname(ordner))
    laeufer = unittest.TextTestRunner(verbosity=2 if args.ausfuehrlich else 1)
    ergebnis = laeufer.run(sammlung)
    return 0 if ergebnis.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
