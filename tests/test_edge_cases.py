"""Randfälle: kleinste Instanzen, nur eine Kundenart, Gleichstände, Kunden auf dem Depot, Reglerränder."""

import pytest

import rkl_constants as C
import rkl_evaluation as E
import rkl_model as M
import rkl_search as SR


def _all_modes(inst, iters=20):
    ch = SR.chain(inst, iters, 1)
    return {m: ch[m] for m in C.STAGE_KEYS}


def test_ein_einziger_kunde_je_art():
    xy = [(0.0, 0.0), (10.0, 0.0)]
    for kind, cost in ((M.L, 200), (M.B, 200)):
        inst = M.make_custom(xy, [0, kind], [0, 5], 10)
        for mode, routes in _all_modes(inst).items():
            assert routes == [[1]] and M.total_cost(inst, routes) == cost, mode


def test_nur_lieferkunden_alle_stufen_gleich_und_kein_unterschied():
    xy = [(0.0, 0.0)] + [(float(10 * i), 0.0) for i in range(1, 5)]
    inst = M.make_custom(xy, [0] + [M.L] * 4, [0, 3, 3, 3, 3], 20)
    costs = {m: M.total_cost(inst, r) for m, r in _all_modes(inst).items()}
    assert len(set(costs.values())) == 1 and costs["S"] == 800   # eine Tour 0-10-20-30-40-0


def test_nur_abholkunden_alle_stufen_gleich():
    xy = [(0.0, 0.0)] + [(float(10 * i), 0.0) for i in range(1, 5)]
    inst = M.make_custom(xy, [0] + [M.B] * 4, [0, 3, 3, 3, 3], 20)
    costs = {m: M.total_cost(inst, r) for m, r in _all_modes(inst).items()}
    assert len(set(costs.values())) == 1 and costs["S"] == 800


def test_kapazitaet_gleich_groesster_menge_ein_kunde_je_tour():
    xy = [(0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0)]
    inst = M.make_custom(xy, [0, M.L, M.L, M.B], [0, 5, 5, 5], 5)
    for mode, routes in _all_modes(inst).items():
        assert M.verify_mode(inst, routes, mode) == [], mode   # der Wert selbst wird im Orakel-Test geprüft


def test_gleichstaende_aendern_die_kosten_nicht_und_bleiben_reproduzierbar():
    xy = [(0.0, 0.0), (10.0, 10.0), (10.0, -10.0), (-10.0, 10.0), (-10.0, -10.0)]
    inst = M.make_custom(xy, [0, M.L, M.L, M.B, M.B], [0, 2, 2, 2, 2], 4)
    a = SR.chain(inst, 30, 4)
    b = SR.chain(inst, 30, 4)
    for m in C.STAGE_KEYS:
        assert a[m] == b[m]
        assert M.verify_mode(inst, a[m], m) == []


def test_kunden_auf_dem_depot_und_aufeinander():
    xy = [(0.0, 0.0), (0.0, 0.0), (0.0, 0.0), (10.0, 0.0)]
    inst = M.make_custom(xy, [0, M.L, M.B, M.B], [0, 1, 1, 1], 5)
    for mode, routes in _all_modes(inst).items():
        assert M.verify_mode(inst, routes, mode) == [], mode
        assert M.total_cost(inst, routes) == 200   # Hin- und Rückweg zum entfernten Kunden, die beiden anderen kosten nichts (S: eine Abholtour 0-K3-K2-0 ebenso)


def test_metrics_ohne_strecke_teilt_nicht_durch_null():
    xy = [(0.0, 0.0), (0.0, 0.0)]
    inst = M.make_custom(xy, [0, M.L], [0, 1], 5)
    m = M.metrics(inst, [[1]])
    assert m["dist"] == 0 and m["load_share"] == 0.0 and m["empty"] == 0


def test_ersparnis_und_anteile_mit_nenner_null():
    assert E.saving(0, 0) == 0.0
    assert E.minus_percent(0.0) == "±0,0 %" and E.minus_percent(-0.0) == "±0,0 %"
    assert E.minus_percent(12.34) == "−12,3 %"
    step = E.Step("S", "S", ((1,),), 0, 1, 0, 0.0, 0.0)
    assert E.empty_share(step) == 0.0


def test_regler_raender_der_instanzerzeugung():
    for n in C.N_OPTIONS:
        for beta in C.BETA_OPTIONS:
            for layout in C.LAYOUT_OPTIONS:
                for k in C.K_OPTIONS:
                    inst = M.make_instance(n, beta, layout, k, 1)
                    assert inst.n == n and inst.nB == round(beta * n) and inst.nL == n - round(beta * n)
                    assert inst.Q >= max(inst.dem[1:])


def test_groesster_fall_laeuft_mit_kleinem_budget(monkeypatch):
    settings = E.Settings(40, 0.6, "gemischt", "mitte", 4, 20, 9)
    a = E.analyse(settings)
    assert [s.key for s in a.steps] == list(C.STAGE_KEYS)
    for s in a.steps:
        assert M.verify_mode(a.inst, [list(r) for r in s.routes], s.key) == []
    assert a.steps[0].dist >= a.steps[1].dist >= a.steps[2].dist >= a.steps[3].dist


def test_analyse_ist_reproduzierbar():
    s = E.Settings(20, 0.4, "gemischt", "rand", 2, 20, 3)
    a, b = E.analyse(s), E.analyse(s)
    assert [(x.dist, x.vehicles, x.empty, x.routes) for x in a.steps] == [(x.dist, x.vehicles, x.empty, x.routes) for x in b.steps]


@pytest.mark.parametrize("bad", ["quer", "", None])
def test_depot_mit_unbekanntem_namen_wird_abgelehnt(bad):
    with pytest.raises(KeyError):
        M.DEPOTS[bad]
