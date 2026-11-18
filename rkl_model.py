"""Instanz, Zulässigkeit und Kennzahlen der Rückladungs-Planung (VRP mit Rückladungen).

Aus tourenplanung-planung/messreihe_backhaul/bh_core.py und messreihe_backhaul_ap0/ap0_core.py mechanisch übernommen (Logik unverändert).

Modell: Depot 0, Kunden 1..n. Lieferkunden (Linehaul, Lieferung d_i, nimmt die Last ab) und Abholkunden (Backhaul, Abholung q_j, nimmt Last auf),
Kapazität Q, unbegrenzte Flotte, Ziel Gesamtdistanz. Alle Entfernungen ganzzahlig (1 Einheit = 0,1 Längeneinheit des 100 x 100-Gebiets).

Planungsarten (S ⊂ S1 ⊂ A ⊂ M, im Optimum also Kosten(S) >= Kosten(S1) >= Kosten(A) >= Kosten(M)):
  S   getrennt: Touren rein Lieferung oder rein Abholung
  S1  eine Lieferstour darf nach den Lieferkunden genau EINEN Abholkunden bedienen; weitere Abholkunden nur in reinen Abholtouren
  A   VRPB: erst alle Lieferkunden, dann alle Abholkunden; Summe Lieferungen <= Q und Summe Abholungen <= Q je Tour
  M   gemischt: beliebige Reihenfolge; die Last auf jeder Teilstrecke darf Q nicht überschreiten (Last = noch auszuliefernde plus bereits abgeholte Menge)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from rkl_rng import SplitMix64

SCALE = 10
L, B = 1, 2
MODES = ("S", "S1", "A", "M")
LAYOUTS = ("gemischt", "ueberlappend", "getrennt")
DEPOTS = {"rand": (50.0, 0.0), "mitte": (50.0, 50.0)}
_ZONES = {  # x-Bereich (Lieferkunden), x-Bereich (Abholkunden); y immer 0..100
    "gemischt": ((0.0, 100.0), (0.0, 100.0)),
    "getrennt": ((0.0, 45.0), (55.0, 100.0)),
    "ueberlappend": ((0.0, 70.0), (30.0, 100.0)),
}


@dataclass
class Instance:
    n: int
    kind: list            # 0 Depot, 1 Lieferkunde, 2 Abholkunde
    dem: list             # Index 0 = 0
    Q: int
    xy: list
    D: list               # ganzzahlige Entfernungen
    meta: dict = field(default_factory=dict)
    _nbr: dict = field(default_factory=dict)

    @property
    def nL(self):
        return sum(1 for k in self.kind if k == L)

    @property
    def nB(self):
        return sum(1 for k in self.kind if k == B)

    def neighbors(self, K=10):
        if K not in self._nbr:
            nb = [[]]
            for i in range(1, self.n + 1):
                order = sorted((j for j in range(1, self.n + 1) if j != i), key=lambda j: (self.D[i][j], j))
                nb.append(order[:K])
            self._nbr[K] = nb
        return self._nbr[K]


def _dist_matrix(xy):
    n = len(xy)
    D = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = int(round(SCALE * math.hypot(xy[i][0] - xy[j][0], xy[i][1] - xy[j][1])))
            D[i][j] = D[j][i] = d
    return D


def make_instance(n, beta, layout, K_L, seed, depot=(50.0, 0.0), dem_L=(5, 25), dem_B=(5, 25)):
    """n Kunden, Anteil Abholkunden beta, Lage der Zonen, K_L = Zahl der Liefertouren, auf die Q abgestimmt ist (Q = ceil(1,1 * Summe d / K_L)).
    Zufallsströme und Ziehungsreihenfolge wie in der Messreihe (Zufalls-Seeds dort 100000 aufwärts)."""
    nB = int(round(beta * n))
    nL = n - nB
    rx = SplitMix64(seed * 8 + 1)
    rd = SplitMix64(seed * 8 + 2)
    rt = SplitMix64(seed * 8 + 3)
    if layout == "gemischt":
        keys = [rt.uniform() for _ in range(n)]
        order = sorted(range(n), key=lambda i: (keys[i], i))
        isB = set(order[:nB])
        kinds = [B if i in isB else L for i in range(n)]
    else:
        kinds = [L] * nL + [B] * nB
    (lx0, lx1), (bx0, bx1) = _ZONES[layout]
    xy = [depot]
    dem = [0]
    for i in range(n):
        u1, u2 = rx.uniform(), rx.uniform()
        x0, x1 = (lx0, lx1) if kinds[i] == L else (bx0, bx1)
        xy.append((x0 + (x1 - x0) * u1, 100.0 * u2))
        lo, hi = dem_L if kinds[i] == L else dem_B
        dem.append(lo + rd.below(hi - lo + 1))
    kind = [0] + kinds
    sumL = sum(dem[i] for i in range(1, n + 1) if kind[i] == L)
    Q = max(int(math.ceil(1.1 * sumL / K_L - 1e-9)), max(dem[1:]))
    meta = dict(n=n, beta=beta, layout=layout, K_L=K_L, seed=seed, depot=depot, dem_L=dem_L, dem_B=dem_B)
    return Instance(n, kind, dem, Q, xy, _dist_matrix(xy), meta)


def make_custom(xy, kind, dem, Q):
    """Handbeispiele und Tests: xy[0] ist das Depot, kind[0] = 0, dem[0] = 0."""
    return Instance(len(xy) - 1, list(kind), list(dem), Q, list(xy), _dist_matrix(xy), {})


def make_cvrp_instance(xy, dem, Q):
    n = len(xy) - 1
    return Instance(n, [0] + [L] * n, list(dem), Q, list(xy), _dist_matrix(xy), {})


# ------------------------------------------------------------------------------------------------ Kosten, Zulässigkeit, Kennzahlen

def route_len(D, r):
    if not r:
        return 0
    s = D[0][r[0]] + D[r[-1]][0]
    for a, b in zip(r, r[1:]):
        s += D[a][b]
    return s


def total_cost(inst, routes):
    return sum(route_len(inst.D, r) for r in routes)


def feas(inst, mode, r):
    """Schneller Zulässigkeitstest einer Tour (für die Suche)."""
    kind, dem, Q = inst.kind, inst.dem, inst.Q
    if mode == "M":
        load = 0
        for c in r:
            if kind[c] == L:
                load += dem[c]
        if load > Q:
            return False
        for c in r:
            if kind[c] == L:
                load -= dem[c]
            else:
                load += dem[c]
                if load > Q:
                    return False
        return True
    sl = sb = nl = nb = 0
    seen_b = False
    for c in r:
        if kind[c] == L:
            if seen_b:
                return False
            sl += dem[c]
            nl += 1
        else:
            seen_b = True
            sb += dem[c]
            nb += 1
    if sl > Q or sb > Q:
        return False
    if mode == "S":
        return not (nl and nb)
    if mode == "S1":
        return not (nl and nb > 1)
    return True  # A


def verify_mode(inst, routes, mode):
    """Unabhängiger Prüfer für alle vier Planungsarten. Rechnet jede Tour mit einem Lastverlauf neu; kennt keinen Löser und nicht feas()."""
    errs = []
    seen = {}
    for ri, r in enumerate(routes):
        if not r:
            errs.append(f"Tour {ri} leer")
            continue
        for c in r:
            if not (1 <= c <= inst.n):
                errs.append(f"Tour {ri}: ungültiger Kunde {c}")
            seen[c] = seen.get(c, 0) + 1
        load = sum(inst.dem[c] for c in r if inst.kind[c] == L)
        loads = [load]
        for c in r:
            load += inst.dem[c] if inst.kind[c] == B else -inst.dem[c]
            loads.append(load)
        if loads[-1] != sum(inst.dem[c] for c in r if inst.kind[c] == B):
            errs.append(f"Tour {ri}: Lastverlauf endet nicht bei der Abholmenge")
        word = "".join("L" if inst.kind[c] == L else "B" for c in r)
        nl, nb = word.count("L"), word.count("B")
        if mode == "M":
            if max(loads) > inst.Q:
                errs.append(f"Tour {ri}: Last {max(loads)} > Q {inst.Q}")
        else:
            if nb and nl and word.find("B") < word.rfind("L"):
                errs.append(f"Tour {ri}: Lieferkunde nach Abholkunde")
            if sum(inst.dem[c] for c in r if inst.kind[c] == L) > inst.Q:
                errs.append(f"Tour {ri}: Lieferungen > Q")
            if sum(inst.dem[c] for c in r if inst.kind[c] == B) > inst.Q:
                errs.append(f"Tour {ri}: Abholungen > Q")
            if mode == "S" and nl and nb:
                errs.append(f"Tour {ri}: im Modus S gemischt")
            if mode == "S1" and nl and nb > 1:
                errs.append(f"Tour {ri}: im Modus S1 mehr als ein Abholkunde bei Lieferkunden")
    for c in range(1, inst.n + 1):
        if seen.get(c, 0) != 1:
            errs.append(f"Kunde {c} kommt {seen.get(c, 0)}-mal vor")
    return errs


def load_profile(inst, r):
    """Last auf den Teilstrecken einer Tour: Liste (von, nach, Entfernung, Last); Last = noch auszuliefernde plus bereits abgeholte Menge."""
    rem = sum(inst.dem[c] for c in r if inst.kind[c] == L)
    picked = 0
    prev = 0
    out = []
    for c in r + [0]:
        out.append((prev, c, inst.D[prev][c], rem + picked))
        if c != 0:
            if inst.kind[c] == L:
                rem -= inst.dem[c]
            else:
                picked += inst.dem[c]
        prev = c
    return out


def metrics(inst, routes):
    """Distanz, Touren, Leerkilometer (Strecke mit Last 0), Lastkilometer-Anteil = Summe(Last mal Strecke) / (Q mal Summe Strecke)."""
    dist = empty = 0
    load_km = 0
    for r in routes:
        for _a, _b, d, load in load_profile(inst, r):
            dist += d
            load_km += load * d
            if load == 0:
                empty += d
    return dict(dist=dist, vehicles=len(routes), empty=empty, load_share=(load_km / (inst.Q * dist)) if dist else 0.0)
