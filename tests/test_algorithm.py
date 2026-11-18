"""Kern gegen Handrechnung: Handbeispiele, Kennzahlen, Zulässigkeitsprüfer, Instanzerzeugung, Zufallsgenerator."""

import math

import pytest

import rkl_constants as C
import rkl_model as M
import rkl_search as SR
from conftest import HAND_VALUES


def _chain(inst, iters=40, seed=1):
    ch = SR.chain(inst, iters, seed)
    return {k: M.total_cost(inst, ch[k]) for k in C.STAGE_KEYS}, ch


@pytest.mark.parametrize("name", list(HAND_VALUES))
def test_die_suche_findet_die_handrechnung_der_beispiele(name, request):
    inst = request.getfixturevalue(name)
    got, ch = _chain(inst)
    assert got == HAND_VALUES[name]
    for key in C.STAGE_KEYS:
        assert M.verify_mode(inst, ch[key], key) == [], (name, key)


def test_handbeispiel_1_kennzahlen_von_hand(hand1):
    # S: Liefertour 0-K1-K2-0 (Last 10, 5, 0 auf den drei Strecken, dann 0), Abholtour 0-K3-0 (Hinweg Last 0, Rückweg 5)
    routes = [[1, 2], [3]]
    m = M.metrics(hand1, routes)
    assert m["dist"] == 1000 and m["vehicles"] == 2
    # Leerkilometer: Rückweg der Liefertour (K2 -> Depot, 200) nach der letzten Lieferung mit Last 0, Hinweg der Abholtour (300): 500
    assert m["empty"] == 500
    # Lastkilometer: 0-K1: Last 10 * 100; K1-K2: 5 * 100; K2-0: 0; 0-K3: 0; K3-0: 5 * 300 = 1000 + 500 + 1500 = 3000 / (Q 20 * 1000)
    assert m["load_share"] == pytest.approx(3000 / (20 * 1000))
    # eine Tour mit Rückladung: 0-K1-K2-K3-0; leer bleibt nur die Strecke K2 -> K3 (nach der letzten Lieferung, vor der Abholung): 100
    m2 = M.metrics(hand1, [[1, 2, 3]])
    assert m2["dist"] == 600 and m2["empty"] == 100 and m2["vehicles"] == 1


def test_strecke_mit_last_null_und_strecke_mit_last_ergeben_die_gesamtdistanz(strict):
    for routes in ([[1], [2, 3, 4]], [[1, 2], [3], [4]], [[1, 4, 2, 3]]):
        prof = [leg for r in routes for leg in M.load_profile(strict, r)]
        assert sum(d for _a, _b, d, load in prof if load == 0) + sum(d for _a, _b, d, load in prof if load > 0) == M.total_cost(strict, routes)
        assert M.metrics(strict, routes)["empty"] == sum(d for _a, _b, d, load in prof if load == 0)


def test_pruefer_erkennt_jede_art_von_unzulaessigkeit(hand2):
    ok = [[1, 2, 3, 4]]
    assert M.verify_mode(hand2, ok, "A") == []
    assert M.verify_mode(hand2, ok, "S")            # gemischte Tour in S
    assert M.verify_mode(hand2, ok, "S1")           # zwei Abholkunden bei Lieferkunden in S1
    assert M.verify_mode(hand2, [[1, 2, 3]], "A")   # Kunde 4 fehlt
    assert M.verify_mode(hand2, [[1, 2, 3, 4], [4]], "A")   # Kunde 4 doppelt
    assert M.verify_mode(hand2, [[3, 1, 2, 4]], "A")        # Lieferkunde nach Abholkunde
    assert M.verify_mode(hand2, [[3, 1, 2, 4]], "M") == []  # in M erlaubt: größte Last 15 (10 noch auszuliefern plus 5 abgeholt) bei Q = 20
    assert M.verify_mode(hand2, [[1, 2], [3, 4], []], "S")  # leere Tour


def test_kapazitaet_wird_je_art_der_last_geprueft():
    xy = [(0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0)]
    inst = M.make_custom(xy, [0, M.L, M.L, M.B], [0, 6, 6, 5], 10)
    assert M.verify_mode(inst, [[1, 2, 3]], "A")    # Lieferungen 12 > 10
    assert M.verify_mode(inst, [[1], [2], [3]], "S") == []
    assert M.verify_mode(inst, [[1, 3], [2]], "A") == []
    # M: Last bei der Abfahrt = Lieferungen der Tour
    assert M.verify_mode(inst, [[1, 2, 3]], "M")


def test_in_m_zaehlt_die_last_auf_jeder_teilstrecke():
    xy = [(0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0)]
    inst = M.make_custom(xy, [0, M.L, M.B, M.L], [0, 5, 5, 5], 10)
    # 0 -> K1 (Last 10) -> K2 abholen (Last 5 + 5 = 10) -> K3 liefern (Last 10) -> 0 (Last 5): zulässig bei Q = 10
    assert M.verify_mode(inst, [[1, 2, 3]], "M") == []
    assert M.feas(inst, "M", [1, 2, 3])
    inst2 = M.make_custom(xy, [0, M.L, M.B, M.L], [0, 5, 6, 5], 10)
    assert M.verify_mode(inst2, [[1, 2, 3]], "M")   # Last 5 + 6 = 11 + 5 > 10 bei K3: Last nach K2 = 5 (K3) + 6 = 11 > 10
    assert not M.feas(inst2, "M", [1, 2, 3])


def test_feas_und_pruefer_stimmen_ueberein():
    import random
    rnd = random.Random(3)
    for _ in range(300):
        n = rnd.randint(2, 5)
        xy = [(0.0, 0.0)] + [(float(rnd.randint(-9, 9)), float(rnd.randint(-9, 9))) for _ in range(n)]
        kinds = [0] + [rnd.choice((M.L, M.B)) for _ in range(n)]
        dem = [0] + [rnd.randint(1, 5) for _ in range(n)]
        inst = M.make_custom(xy, kinds, dem, rnd.randint(5, 10))
        order = list(range(1, n + 1))
        rnd.shuffle(order)
        for mode in C.STAGE_KEYS:
            assert M.feas(inst, mode, order) == (M.verify_mode(inst, [order], mode) == []), (mode, order, inst.kind, inst.dem, inst.Q)


def test_instanz_ist_deterministisch_und_folgt_den_festlegungen():
    a = M.make_instance(20, 0.4, "gemischt", 2, 100600)
    b = M.make_instance(20, 0.4, "gemischt", 2, 100600)
    assert a.xy == b.xy and a.dem == b.dem and a.kind == b.kind and a.Q == b.Q
    assert a.nB == 8 and a.nL == 12 and a.n == 20
    assert all(C.DEM_RANGE[0] <= d <= C.DEM_RANGE[1] for d in a.dem[1:])
    sum_l = sum(a.dem[i] for i in range(1, 21) if a.kind[i] == M.L)
    assert a.Q == max(math.ceil(C.CAP_FACTOR * sum_l / 2 - 1e-9), max(a.dem[1:]))
    assert a.xy[0] == (50.0, 0.0)
    assert M.make_instance(20, 0.4, "gemischt", 2, 100600, depot=M.DEPOTS["mitte"]).xy[0] == (50.0, 50.0)
    assert a.xy[1:] == M.make_instance(20, 0.4, "gemischt", 2, 100600, depot=M.DEPOTS["mitte"]).xy[1:]   # nur das Depot ändert sich


@pytest.mark.parametrize("layout,lx,bx", [("getrennt", (0, 45), (55, 100)), ("ueberlappend", (0, 70), (30, 100)), ("gemischt", (0, 100), (0, 100))])
def test_zonen_der_lagen(layout, lx, bx):
    for seed in (5, 6, 7):
        inst = M.make_instance(40, 0.4, layout, 2, seed)
        for i in range(1, 41):
            lo, hi = lx if inst.kind[i] == M.L else bx
            assert lo <= inst.xy[i][0] <= hi
            assert 0 <= inst.xy[i][1] <= 100


def test_kapazitaet_waechst_mit_der_knappheit():
    k2 = M.make_instance(20, 0.4, "gemischt", 2, 9)
    k4 = M.make_instance(20, 0.4, "gemischt", 4, 9)
    assert k4.Q < k2.Q and k4.xy == k2.xy and k4.dem == k2.dem


def test_entfernungen_sind_ganzzahlig_symmetrisch_und_erfuellen_die_dreiecksungleichung_naeherungsweise():
    inst = M.make_instance(20, 0.4, "gemischt", 2, 11)
    n = inst.n + 1
    for i in range(n):
        assert inst.D[i][i] == 0
        for j in range(n):
            assert isinstance(inst.D[i][j], int) and inst.D[i][j] == inst.D[j][i]
            for k in range(n):
                assert inst.D[i][j] <= inst.D[i][k] + inst.D[k][j] + 1   # Rundung auf 0,1: höchstens 1 Einheit


def test_ketten_loesungen_sind_monoton_und_zulaessig_auf_zufallsinstanzen():
    for seed in (21, 22, 23):
        inst = M.make_instance(12, 0.4, "gemischt", 2, seed)
        got, ch = _chain(inst, iters=30, seed=seed)
        assert got["S"] >= got["S1"] >= got["A"] >= got["M"], (seed, got)
        for key in C.STAGE_KEYS:
            assert M.verify_mode(inst, ch[key], key) == [], (seed, key)


def test_suche_ist_reproduzierbar_und_mehr_iterationen_sind_nie_schlechter():
    inst = M.make_instance(14, 0.4, "gemischt", 2, 31)
    a = SR.solve_ils(inst, "A", 20, 5)
    b = SR.solve_ils(inst, "A", 20, 5)
    assert a == b
    assert M.total_cost(inst, SR.solve_ils(inst, "A", 60, 5)) <= M.total_cost(inst, a)


def test_savings_ist_zulaessig_in_s_und_a(strict):
    r = SR.savings_pure(strict)
    assert M.verify_mode(strict, r, "S") == [] and M.verify_mode(strict, r, "A") == []
