"""Vergleichslöser für Planungsart S und A: OR-Tools-Routing (zwei Einstellungen) und CP-SAT (exakt).

Aus tourenplanung-planung/messreihe_backhaul/bh_core.py übernommen. OR-Tools wird erst beim Aufruf importiert; ohne OR-Tools läuft die Demo bis auf diese
Knöpfe (ImportError wird in der App abgefangen). S1 und M haben keinen Vergleichslöser: dort gibt es nur die eigene Suche.
"""
from __future__ import annotations

from rkl_model import B, L, make_cvrp_instance
from rkl_search import savings_pure

SETTINGS = ("standard", "sav")


def solve_ortools(inst, mode, seconds, setting="standard"):
    """OR-Tools-Routing (Guided Local Search). setting 'standard': PATH_CHEAPEST_ARC; 'sav': Erststrategie SAVINGS.
    Zusatzoperatoren und Warmstart machten das Ergebnis in der Abstimmung schlechter und gehören darum nicht dazu.
    Gibt (routes, Zielwert) zurück; Zielwert None, wenn keine Lösung gefunden wurde."""
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2 as e
    if setting not in SETTINGS:
        raise ValueError(setting)
    D, n = inst.D, inst.n
    sav = savings_pure(inst)
    nveh = min(n, len(sav) + 4)
    manager = pywrapcp.RoutingIndexManager(n + 1, nveh, 0)
    routing = pywrapcp.RoutingModel(manager)
    tr = routing.RegisterTransitCallback(lambda i, j: D[manager.IndexToNode(i)][manager.IndexToNode(j)])
    routing.SetArcCostEvaluatorOfAllVehicles(tr)
    dl = [inst.dem[i] if inst.kind[i] == L else 0 for i in range(n + 1)]
    db = [inst.dem[i] if inst.kind[i] == B else 0 for i in range(n + 1)]
    cl = routing.RegisterUnaryTransitCallback(lambda i: dl[manager.IndexToNode(i)])
    cb = routing.RegisterUnaryTransitCallback(lambda i: db[manager.IndexToNode(i)])
    routing.AddDimensionWithVehicleCapacity(cl, 0, [inst.Q] * nveh, True, "L")
    routing.AddDimensionWithVehicleCapacity(cb, 0, [inst.Q] * nveh, True, "B")
    for i in range(1, n + 1):
        for j in range(1, n + 1):
            if i == j:
                continue
            if inst.kind[i] == B and inst.kind[j] == L:
                routing.NextVar(manager.NodeToIndex(i)).RemoveValue(manager.NodeToIndex(j))
            if mode == "S" and inst.kind[i] == L and inst.kind[j] == B:
                routing.NextVar(manager.NodeToIndex(i)).RemoveValue(manager.NodeToIndex(j))
    p = pywrapcp.DefaultRoutingSearchParameters()
    p.time_limit.FromMilliseconds(int(seconds * 1000))
    p.local_search_metaheuristic = e.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    p.first_solution_strategy = e.FirstSolutionStrategy.SAVINGS if setting == "sav" else e.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    routing.CloseModelWithParameters(p)
    sol = routing.SolveWithParameters(p)
    if sol is None:
        return None, None
    routes = []
    for v in range(nveh):
        idx = routing.Start(v)
        r = []
        while not routing.IsEnd(idx):
            node = manager.IndexToNode(idx)
            if node != 0:
                r.append(node)
            idx = sol.Value(routing.NextVar(idx))
        if r:
            routes.append(r)
    return routes, sol.ObjectiveValue()


# ------------------------------------------------------------------------------------------------ exakt (CP-SAT)

def solve_exact(inst, mode, seconds, workers=1, hint=None):
    from ortools.sat.python import cp_model
    D, n = inst.D, inst.n
    m = cp_model.CpModel()
    lit = {}
    arcs = []
    for i in range(n + 1):
        for j in range(n + 1):
            if i == j:
                continue
            if i >= 1 and j >= 1:
                if inst.kind[i] == B and inst.kind[j] == L:
                    continue
                if mode == "S" and inst.kind[i] != inst.kind[j]:
                    continue
            lit[i, j] = m.NewBoolVar(f"a{i}_{j}")
            arcs.append((i, j, lit[i, j]))
    m.AddMultipleCircuit(arcs)
    cl = {i: m.NewIntVar(0, inst.Q, f"cl{i}") for i in range(1, n + 1)}
    cb = {i: m.NewIntVar(0, inst.Q, f"cb{i}") for i in range(1, n + 1)}
    dl = [inst.dem[i] if inst.kind[i] == L else 0 for i in range(n + 1)]
    db = [inst.dem[i] if inst.kind[i] == B else 0 for i in range(n + 1)]
    for (i, j), a in lit.items():
        if j == 0:
            continue
        if i == 0:
            m.Add(cl[j] == dl[j]).OnlyEnforceIf(a)
            m.Add(cb[j] == db[j]).OnlyEnforceIf(a)
        else:
            m.Add(cl[j] == cl[i] + dl[j]).OnlyEnforceIf(a)
            m.Add(cb[j] == cb[i] + db[j]).OnlyEnforceIf(a)
    m.Minimize(sum(D[i][j] * a for (i, j), a in lit.items()))
    if hint:
        used = set()
        for r in hint:
            path = [0] + r + [0]
            used.update(zip(path, path[1:]))
        for (i, j), a in lit.items():
            m.AddHint(a, 1 if (i, j) in used else 0)
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = seconds
    s.parameters.num_workers = workers
    s.parameters.random_seed = 1
    st = s.Solve(m)
    name = s.StatusName(st)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None, name, s.BestObjectiveBound()
    nxt = {}
    starts = []
    for (i, j), a in lit.items():
        if s.Value(a):
            if i == 0:
                starts.append(j)
            else:
                nxt[i] = j
    routes = []
    for c in starts:
        r = [c]
        while nxt.get(r[-1], 0) != 0:
            r.append(nxt[r[-1]])
        routes.append(r)
    return routes, name, s.BestObjectiveBound()


def solve_exact_S(inst, seconds, workers=1, hint=None):
    """Exaktes Optimum für 'S': die getrennte Planung zerfällt in zwei unabhängige CVRP (nur Linehaul, nur Backhaul), die je für sich
    viel schneller bewiesen werden als das gemeinsame Modell. Gibt (routes, Status, Schranke) zurück; Status OPTIMAL nur, wenn beide Teile es sind."""
    routes, status, bound = [], "OPTIMAL", 0.0
    for kind in (L, B):
        ids = [i for i in range(1, inst.n + 1) if inst.kind[i] == kind]
        if not ids:
            continue
        sub = make_cvrp_instance([inst.xy[0]] + [inst.xy[i] for i in ids], [0] + [inst.dem[i] for i in ids], inst.Q)
        h = None
        if hint:
            pos = {c: j + 1 for j, c in enumerate(ids)}
            h = [[pos[c] for c in r] for r in hint if r and inst.kind[r[0]] == kind]
        r, st, bd = solve_exact(sub, "S", seconds / 2, workers, hint=h)
        if r is None:
            return None, st, None
        routes += [[ids[j - 1] for j in rr] for rr in r]
        bound += bd
        if st != "OPTIMAL":
            status = st
    return routes, status, bound
