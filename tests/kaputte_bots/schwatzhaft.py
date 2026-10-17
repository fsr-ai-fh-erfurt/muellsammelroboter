NAME = "Schwatzhaft"


class Roboter:
    def entscheide(self, zustand):
        print("Ich denke nach ...", zustand.tick)
        return zustand.fahre_zu_muell()
