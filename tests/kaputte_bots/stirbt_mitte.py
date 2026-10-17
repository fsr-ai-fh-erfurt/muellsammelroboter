import os

NAME = "Stirbt mitten im Spiel"


class Roboter:
    def entscheide(self, zustand):
        if zustand.tick >= 3:
            os._exit(1)
        return "warte"
