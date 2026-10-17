import os

NAME = "Vergisst seinen Modus"


class Roboter:
    def __init__(self):
        self.modus = "sammeln"
        self.aufrufe = 0

    def entscheide(self, zustand):
        self.aufrufe += 1
        if self.aufrufe >= 3:
            os._exit(1)
        if self.modus == "sammeln":
            self.modus = "heimweg"
            return "rechts"
        return "links"
