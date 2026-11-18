"""Gemeinsame Fixtures: die Handbeispiele, an denen jede Einheit von Hand geprüft wird (DEMO-PLAYBOOK §1b).

Handbeispiel 1 (Gerade, Depot bei 0, Abstand 10 je Schritt, Entfernungseinheit = 0,1 Längeneinheit): Lieferkunden K1 bei 10 und K2 bei 20, Abholkunde K3 bei 30, alle Menge 5, Q = 20.
  S : Liefertour 0-10-20-0 = 400, Abholtour 0-30-0 = 600, zusammen 1000
  S1: eine Tour 0-10-20-30-0 = 600 (ein Abholkunde ist erlaubt) = 600; A und M ebenso 600
Handbeispiel 2: wie 1 plus Abholkunde K4 bei 40: S = 400 + (0-30-40-0 = 800) = 1200; S1 = 1200 (zwei Abholkunden: der zweite bräuchte eine eigene Tour);
  A = M = 0-10-20-30-40-0 = 800.
Handbeispiel 3 (streng gestaffelt, von Hand aus dem Orakel gewählt): in dieser Instanz gilt S > S1 > A > M strikt (1040, 922, 905, 837).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import rkl_model as M  # noqa: E402


def _line(points, kinds, dems, Q):
    xy = [(0.0, 0.0)] + [(float(p), 0.0) for p in points]
    return M.make_custom(xy, [0] + list(kinds), [0] + list(dems), Q)


@pytest.fixture
def hand1():
    return _line([10, 20, 30], [M.L, M.L, M.B], [5, 5, 5], 20)


@pytest.fixture
def hand2():
    return _line([10, 20, 30, 40], [M.L, M.L, M.B, M.B], [5, 5, 5, 5], 20)


@pytest.fixture
def strict():
    xy = [(0.0, 0.0), (-13.0, 11.0), (9.0, 10.0), (10.0, -1.0), (-15.0, -11.0)]
    return M.make_custom(xy, [0, M.L, M.B, M.B, M.B], [0, 2, 5, 1, 2], 9)


HAND_VALUES = {"hand1": {"S": 1000, "S1": 600, "A": 600, "M": 600}, "hand2": {"S": 1200, "S1": 1200, "A": 800, "M": 800}, "strict": {"S": 1040, "S1": 922, "A": 905, "M": 837}}
