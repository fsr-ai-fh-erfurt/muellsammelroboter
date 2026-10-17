import sys

NAME = "Stderr-Flut"


class Roboter:
    def entscheide(self, zustand):
        for nummer in range(300):
            print("Flut %d" % nummer, file=sys.stderr)
        return "warte"
