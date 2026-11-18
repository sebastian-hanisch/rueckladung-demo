"""Zufallsquelle: SplitMix64, nur Ganzzahl-Arithmetik, auf jeder Plattform bitgleich.

Wörtliche Kopie der Klasse aus ab-test-demo/abt_rng.py (über tourenplanung-planung/messreihe_backhaul/bh_core.py übernommen). Der Test
`tests/test_rng.py` prüft feste Ausgaben und, wenn der Nachbarordner vorhanden ist, die Gleichheit mit dem Original.
"""

_MASK = (1 << 64) - 1
_GAMMA = 0x9E3779B97F4A7C15
_M1 = 0xBF58476D1CE4E5B9
_M2 = 0x94D049BB133111EB


class SplitMix64:
    """Wörtliche Kopie von ab-test-demo/abt_rng.py (SplitMix64, nur Ganzzahl-Arithmetik)."""

    def __init__(self, seed):
        self.state = seed & _MASK

    def next(self):
        self.state = (self.state + _GAMMA) & _MASK
        z = self.state
        z = ((z ^ (z >> 30)) * _M1) & _MASK
        z = ((z ^ (z >> 27)) * _M2) & _MASK
        return z ^ (z >> 31)

    def uniform(self):
        return (self.next() >> 11) * (1.0 / (1 << 53))

    def below(self, k):
        return min(k - 1, int(self.uniform() * k))
