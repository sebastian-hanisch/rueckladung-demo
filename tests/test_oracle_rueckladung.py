"""Orakel-Test rueckladung-demo / Rückladung (VRP mit Rückladungen): unabhängiger Rechenweg für alle vier Planungsarten.

Orakel: Aufzählung. Für jede Teilmenge der Kunden werden ALLE Reihenfolgen durchprobiert und mit einer eigenen, im Test geschriebenen Zulässigkeitsregel
(Lastverlauf Schritt für Schritt, kein Code aus rkl_model.feas oder rkl_search) bewertet; danach setzt eine Teilmengen-Rechnung die beste Zerlegung zusammen.
Geteilt mit der Demo ist nur die Entfernungsmatrix (`inst.D`). Vorher am Handbeispiel (tests/conftest.py) geprüft: auch ein Orakel kann falsch sein.
Geprüft wird: (1) das Orakel gegen die von Hand gerechneten Werte, (2) die eigene Suche gegen das Orakel auf 24 Kleinstinstanzen (nie darunter, fast immer gleich),
(3) die Monotonie S ≥ S1 ≥ A ≥ M im Optimum, (4) CP-SAT gegen das Orakel (S und A), (5) die Kennzahlen der App gegen eine eigene Nachrechnung.
"""

import itertools
import random

import pytest

import rkl_constants as C
import rkl_model as M
import rkl_search as SR
from conftest import HAND_VALUES

L, B = M.L, M.B


# ------------------------------------------------------------------------------------------------ Orakel (eigener Code)

def _order_ok(inst, mode, perm):
    """Zulässigkeit einer Reihenfolge, Last Schritt für Schritt; nutzt nichts aus rkl_model außer den Instanzdaten."""
    kinds = [inst.kind[c] for c in perm]
    n_l, n_b = kinds.count(L), kinds.count(B)
    sum_l = sum(inst.dem[c] for c in perm if inst.kind[c] == L)
    sum_b = sum(inst.dem[c] for c in perm if inst.kind[c] == B)
    if mode in ("S", "S1", "A"):
        if sum_l > inst.Q or sum_b > inst.Q:
            return False
        for i, k in enumerate(kinds):
            if k == B and L in kinds[i + 1:]:
                return False
        if mode == "S" and n_l and n_b:
            return False
        if mode == "S1" and n_l and n_b > 1:
            return False
        return True
    load = sum_l                       # M: Last bei der Abfahrt = alle Lieferungen
    if load > inst.Q:
        return False
    for c in perm:
        load += inst.dem[c] if inst.kind[c] == B else -inst.dem[c]
        if load > inst.Q:
            return False
    return True


def opt(inst, mode):
    n, D = inst.n, inst.D
    full = (1 << n) - 1
    inf = 10 ** 12
    best = {}
    for mask in range(1, full + 1):
        mem = [i + 1 for i in range(n) if mask >> i & 1]
        cheapest = inf
        for perm in itertools.permutations(mem):
            if not _order_ok(inst, mode, perm):
                continue
            cost = D[0][perm[0]] + sum(D[a][b] for a, b in zip(perm, perm[1:])) + D[perm[-1]][0]
            cheapest = min(cheapest, cost)
        if cheapest < inf:
            best[mask] = cheapest
    f = [inf] * (full + 1)
    f[0] = 0
    for mask in range(1, full + 1):
        sub = mask
        while sub:
            if sub in best and f[mask ^ sub] < inf and f[mask ^ sub] + best[sub] < f[mask]:
                f[mask] = f[mask ^ sub] + best[sub]
            sub = (sub - 1) & mask
    return f[full]


def random_instances(count, n, seed):
    rnd = random.Random(seed)
    out = []
    while len(out) < count:
        xy = [(0.0, 0.0)] + [(float(rnd.randint(-20, 20)), float(rnd.randint(-20, 20))) for _ in range(n)]
        kinds = [0] + [rnd.choice((L, B)) for _ in range(n)]
        if L not in kinds or B not in kinds:
            continue
        dem = [0] + [rnd.randint(1, 5) for _ in range(n)]
        q = rnd.randint(max(dem), 12)
        out.append(M.make_custom(xy, kinds, dem, q))
    return out


# ------------------------------------------------------------------------------------------------ Tests

@pytest.mark.parametrize("name", list(HAND_VALUES))
def test_orakel_gleich_handrechnung(name, request):
    inst = request.getfixturevalue(name)
    assert {m: opt(inst, m) for m in C.STAGE_KEYS} == HAND_VALUES[name]


def test_die_gestaffelte_instanz_ist_streng_gestaffelt(strict):
    v = {m: opt(strict, m) for m in C.STAGE_KEYS}
    assert v["S"] > v["S1"] > v["A"] > v["M"]


@pytest.fixture(scope="module")
def kleine():
    return random_instances(24, 6, 11)


@pytest.fixture(scope="module")
def werte(kleine):
    return [{m: opt(inst, m) for m in C.STAGE_KEYS} for inst in kleine]


def test_monotonie_im_optimum(werte):
    for v in werte:
        assert v["S"] >= v["S1"] >= v["A"] >= v["M"], v


def test_jede_stufe_weicht_im_optimum_auf_mindestens_einer_kleininstanz_von_der_vorstufe_ab(werte):
    """Zweig-Test: keine Stufe ist ein toter Zweig (Nullspalten-Falle)."""
    for lo, hi in (("S", "S1"), ("S1", "A"), ("A", "M")):
        assert any(v[hi] < v[lo] for v in werte), (lo, hi)


def test_eigene_suche_nie_unter_dem_optimum_und_fast_immer_gleich(kleine, werte):
    hits = 0
    for i, (inst, v) in enumerate(zip(kleine, werte)):
        ch = SR.chain(inst, 60, i + 1)
        for m in C.STAGE_KEYS:
            c = M.total_cost(inst, ch[m])
            assert c >= v[m], (i, m, c, v[m])          # eine Lösung kann nie billiger sein als das Optimum
            assert M.verify_mode(inst, ch[m], m) == []
            hits += c == v[m]
    assert hits >= int(0.9 * 4 * len(kleine)), hits   # gemessen in der Vormessung bei n = 8: 24 von 24 Instanzen


def test_savings_nie_unter_dem_optimum_von_s_und_a(kleine, werte):
    for inst, v in zip(kleine, werte):
        c = M.total_cost(inst, SR.savings_pure(inst))
        assert c >= v["S"] and c >= v["A"]


def test_cp_sat_gleich_orakel_fuer_s_und_a():
    pytest.importorskip("ortools")
    import rkl_solvers as V
    for inst in random_instances(3, 6, 5):
        hint = SR.savings_pure(inst)
        routes, status, _ = V.solve_exact(inst, "A", 20, 1, hint=hint)
        assert status == "OPTIMAL" and M.total_cost(inst, routes) == opt(inst, "A")
        routes_s, status_s, _ = V.solve_exact_S(inst, 20, 1)
        assert status_s == "OPTIMAL" and M.total_cost(inst, routes_s) == opt(inst, "S")


def _own_metrics(inst, routes):
    """Eigene Nachrechnung der Kennzahlen (Last je Teilstrecke aus den Mengen, kein load_profile)."""
    dist = empty = load_km = 0
    for r in routes:
        pos = [0] + list(r) + [0]
        carried = sum(inst.dem[c] for c in r if inst.kind[c] == L)
        for a, b in zip(pos, pos[1:]):
            d = inst.D[a][b]
            dist += d
            load_km += carried * d
            if carried == 0:
                empty += d
            if b != 0:
                carried += inst.dem[b] if inst.kind[b] == B else -inst.dem[b]
    return dist, empty, load_km / (inst.Q * dist)


def test_kennzahlen_der_app_gleich_eigener_nachrechnung(kleine):
    for i, inst in enumerate(kleine[:8]):
        ch = SR.chain(inst, 20, i + 1)
        for m in C.STAGE_KEYS:
            got = M.metrics(inst, ch[m])
            dist, empty, share = _own_metrics(inst, ch[m])
            assert (got["dist"], got["empty"]) == (dist, empty) and got["load_share"] == pytest.approx(share)
            assert got["dist"] == M.total_cost(inst, ch[m]) and got["vehicles"] == len(ch[m])
