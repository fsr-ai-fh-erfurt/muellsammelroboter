import unittest

from engine.rng import Zufall


class TestZufall(unittest.TestCase):
    def test_gleicher_seed_gleiche_folge(self):
        a = [Zufall(12345).zahl(1000) for _ in range(1)]
        b = Zufall(12345)
        self.assertEqual(a[0], b.zahl(1000))
        eins = Zufall(7)
        zwei = Zufall(7)
        self.assertEqual([eins.zahl(97) for _ in range(50)],
                         [zwei.zahl(97) for _ in range(50)])

    def test_verschiedene_seeds_verschiedene_folgen(self):
        eins = [Zufall(1).zahl(10000) for _ in range(1)]
        zwei = [Zufall(2).zahl(10000) for _ in range(1)]
        self.assertNotEqual(eins, zwei)

    def test_seed_null_funktioniert(self):
        z = Zufall(0)
        werte = [z.zahl(10) for _ in range(20)]
        self.assertEqual(len(set(werte)) > 1, True)

    def test_bereich_ist_einschliesslich(self):
        z = Zufall(3)
        werte = {z.bereich(5, 7) for _ in range(300)}
        self.assertEqual(werte, {5, 6, 7})

    def test_gewichtet_trifft_alle(self):
        z = Zufall(4)
        paare = [("a", 1), ("b", 99)]
        gezogen = [z.gewichtet(paare) for _ in range(500)]
        self.assertIn("a", gezogen)
        self.assertGreater(gezogen.count("b"), gezogen.count("a"))

    def test_gewicht_null_wird_nie_gezogen(self):
        z = Zufall(5)
        paare = [("nie", 0), ("immer", 3)]
        self.assertEqual({z.gewichtet(paare) for _ in range(100)}, {"immer"})

    def test_werte_bleiben_ganzzahlig(self):
        z = Zufall(9)
        for _ in range(100):
            self.assertIsInstance(z.zahl(50), int)


if __name__ == "__main__":
    unittest.main()
