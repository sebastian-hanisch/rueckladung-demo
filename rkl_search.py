"""Eigene Suche für die vier Planungsarten S, S1, A, M (Rechenkern der Demo).

Mechanisch aus tourenplanung-planung/messreihe_backhaul/bh_core.py (Savings, Ruin-and-Recreate mit Lokalsuche für S und A) und
messreihe_backhaul_ap0/ap0_core.py (allgemeine Suche für S1 und M, Kette S -> S1 -> A -> M) übernommen; die Logik ist unverändert,
nur Namen angepasst (ap0 `_recreate` heißt hier `_recreate_gen`). Die Kette `chain` ist genau die der Messreihe AP 0; Zusatz der Demo: sie misst die
Rechenzeit je Teillauf (`out["_seconds"]`), die Lösungen ändert das nicht.
"""
from __future__ import annotations

import time

from rkl_model import B, L, feas, route_len, total_cost
from rkl_rng import SplitMix64

# ------------------------------------------------------------------------------------------------ Greedy: Clarke-Wright je Typ
def savings_pure(inst):
    D = inst.D
    cust = list(range(1, inst.n + 1))
    rid = {c: c for c in cust}
    rt = {c: [c] for c in cust}
    ld = {c: inst.dem[c] for c in cust}
    pairs = []
    for i in cust:
        for j in cust:
            if i < j and inst.kind[i] == inst.kind[j]:
                pairs.append((-(D[0][i] + D[0][j] - D[i][j]), i, j))
    pairs.sort()
    for _, i, j in pairs:
        ri, rj = rid[i], rid[j]
        if ri == rj or ld[ri] + ld[rj] > inst.Q:
            continue
        a, b = rt[ri], rt[rj]
        if a[-1] == i and b[0] == j:
            new = a + b
        elif a[0] == i and b[-1] == j:
            new = b + a
        elif a[-1] == i and b[-1] == j:
            new = a + b[::-1]
        elif a[0] == i and b[0] == j:
            new = a[::-1] + b
        else:
            continue
        rt[ri] = new
        ld[ri] += ld[rj]
        del rt[rj], ld[rj]
        for c in b:
            rid[c] = ri
    return [r[:] for r in rt.values()]


# ------------------------------------------------------------------------------------------------ eigene Suche

class _St:
    """Lösung mit Zwischenspeicher je Route (Lieferlast, Abholmenge, Zahl Linehaul/Backhaul) und Ort je Kunde."""

    def __init__(self, inst, routes, mode):
        self.inst, self.mode = inst, mode
        self.routes = [r[:] for r in routes]
        self.sL, self.sB, self.nL, self.nB = [], [], [], []
        self.where = {}
        for ri in range(len(self.routes)):
            self.sL.append(0), self.sB.append(0), self.nL.append(0), self.nB.append(0)
            self.refresh(ri)

    def refresh(self, ri):
        inst = self.inst
        r = self.routes[ri]
        sl = sb = nl = nb = 0
        for idx, c in enumerate(r):
            self.where[c] = (ri, idx)
            if inst.kind[c] == L:
                sl += inst.dem[c]
                nl += 1
            else:
                sb += inst.dem[c]
                nb += 1
        self.sL[ri], self.sB[ri], self.nL[ri], self.nB[ri] = sl, sb, nl, nb

    def add_route(self):
        self.routes.append([])
        self.sL.append(0), self.sB.append(0), self.nL.append(0), self.nB.append(0)
        return len(self.routes) - 1

    def compact(self):
        keep = [r for r in self.routes if r]
        self.__init__(self.inst, keep, self.mode)

    def cost(self):
        return total_cost(self.inst, self.routes)


def _ins_ok(st, c, rj, q, same_route_removed=False):
    """Darf Kunde c an Position q in Route rj eingefügt werden? (Ist c schon aus rj entfernt gedacht: same_route_removed.)"""
    inst = st.inst
    sl, sb, nl, nb = st.sL[rj], st.sB[rj], st.nL[rj], st.nB[rj]
    if same_route_removed:
        if inst.kind[c] == L:
            sl -= inst.dem[c]
            nl -= 1
        else:
            sb -= inst.dem[c]
            nb -= 1
    if inst.kind[c] == L:
        if sl + inst.dem[c] > inst.Q or q > nl:
            return False
        if st.mode == "S" and nb > 0:
            return False
    else:
        if sb + inst.dem[c] > inst.Q or q < nl:
            return False
        if st.mode == "S" and nl > 0:
            return False
    return True


def _insert_cost(D, r, q, c):
    p = r[q - 1] if q > 0 else 0
    nx = r[q] if q < len(r) else 0
    return D[p][c] + D[c][nx] - D[p][nx]


def _remove_gain(D, r, idx):
    c = r[idx]
    p = r[idx - 1] if idx > 0 else 0
    nx = r[idx + 1] if idx + 1 < len(r) else 0
    return D[p][c] + D[c][nx] - D[p][nx]


def _local_search(st, order_rng=None):
    inst, D = st.inst, st.inst.D
    nbr = inst.neighbors(10)
    custs = list(range(1, inst.n + 1))
    if order_rng is not None:
        for i in range(len(custs) - 1, 0, -1):
            j = order_rng.below(i + 1)
            custs[i], custs[j] = custs[j], custs[i]
    improved = True
    guard = 0
    while improved and guard < 200:
        guard += 1
        improved = False
        if not st.routes or st.routes[-1]:
            st.add_route()
        # --- Relocate
        for c in custs:
            ri, idx = st.where[c]
            r = st.routes[ri]
            gain = _remove_gain(D, r, idx)
            best = None
            for v in nbr[c]:
                rj, jdx = st.where[v]
                if rj == ri:
                    tmp = r[:idx] + r[idx + 1:]
                    pv = jdx if jdx < idx else jdx - 1
                    for q in (pv, pv + 1):
                        if q == idx or not _ins_ok(st, c, rj, q, True):
                            continue
                        delta = _insert_cost(D, tmp, q, c) - gain
                        if delta < 0 and (best is None or delta < best[0]):
                            best = (delta, rj, q)
                else:
                    rv = st.routes[rj]
                    for q in (jdx, jdx + 1):
                        if not _ins_ok(st, c, rj, q):
                            continue
                        delta = _insert_cost(D, rv, q, c) - gain
                        if delta < 0 and (best is None or delta < best[0]):
                            best = (delta, rj, q)
            if len(r) > 1:
                rn = len(st.routes) - 1
                if not st.routes[rn]:
                    delta = 2 * D[0][c] - gain
                    if delta < 0 and (best is None or delta < best[0]):
                        best = (delta, rn, 0)
            if best is not None:
                _, rj, q = best
                del r[idx]
                if rj == ri:
                    st.routes[ri].insert(q, c)
                else:
                    st.routes[rj].insert(q, c)
                st.refresh(ri)
                if rj != ri:
                    st.refresh(rj)
                if st.routes[-1]:
                    st.add_route()
                improved = True
        # --- Swap (gleiche Art, verschiedene Routen)
        for c in custs:
            ri, idx = st.where[c]
            for v in nbr[c]:
                rj, jdx = st.where[v]
                if rj == ri or inst.kind[v] != inst.kind[c]:
                    continue
                ri, idx = st.where[c]
                r, rv = st.routes[ri], st.routes[rj]
                if inst.kind[c] == L:
                    if st.sL[ri] - inst.dem[c] + inst.dem[v] > inst.Q or st.sL[rj] - inst.dem[v] + inst.dem[c] > inst.Q:
                        continue
                else:
                    if st.sB[ri] - inst.dem[c] + inst.dem[v] > inst.Q or st.sB[rj] - inst.dem[v] + inst.dem[c] > inst.Q:
                        continue
                p1 = r[idx - 1] if idx > 0 else 0
                n1 = r[idx + 1] if idx + 1 < len(r) else 0
                p2 = rv[jdx - 1] if jdx > 0 else 0
                n2 = rv[jdx + 1] if jdx + 1 < len(rv) else 0
                delta = D[p1][v] + D[v][n1] + D[p2][c] + D[c][n2] - D[p1][c] - D[c][n1] - D[p2][v] - D[v][n2]
                if delta < 0:
                    r[idx], rv[jdx] = v, c
                    st.refresh(ri)
                    st.refresh(rj)
                    improved = True
                    break
        # --- 2-opt innerhalb eines Blocks
        for ri in range(len(st.routes)):
            r = st.routes[ri]
            if len(r) < 2:
                continue
            nl = st.nL[ri]
            blocks = [(0, nl), (nl, len(r))]
            changed = True
            while changed:
                changed = False
                for lo, hi in blocks:
                    for i in range(lo, hi - 1):
                        a = r[i - 1] if i > 0 else 0
                        for j in range(i + 1, hi):
                            b = r[j + 1] if j + 1 < len(r) else 0
                            delta = D[a][r[j]] + D[r[i]][b] - D[a][r[i]] - D[r[j]][b]
                            if delta < 0:
                                r[i:j + 1] = r[i:j + 1][::-1]
                                changed = improved = True
                                break
                        if changed:
                            break
                    if changed:
                        break
            st.refresh(ri)
        # --- 2-opt* (Endstücke tauschen)
        for c in custs:
            for v in nbr[c]:
                ri, idx = st.where[c]
                rj, jdx = st.where[v]
                if ri == rj:
                    continue
                r1, r2 = st.routes[ri], st.routes[rj]
                a, b = idx + 1, jdx
                p1 = r1[:a]
                s1 = r1[a:]
                p2 = r2[:b]
                s2 = r2[b:]
                nx1 = s1[0] if s1 else 0
                pv2 = p2[-1] if p2 else 0
                delta = D[c][v] + D[pv2][nx1] - D[c][nx1] - D[pv2][v]
                if delta >= 0:
                    continue
                if not (_route_ok(inst, p1 + s2, st.mode) and _route_ok(inst, p2 + s1, st.mode)):
                    continue
                st.routes[ri], st.routes[rj] = p1 + s2, p2 + s1
                st.refresh(ri)
                st.refresh(rj)
                improved = True
                break
    st.compact()
    return st


def _route_ok(inst, r, mode):
    sl = sb = 0
    seen_b = False
    seen_l = False
    for c in r:
        if inst.kind[c] == L:
            if seen_b:
                return False
            seen_l = True
            sl += inst.dem[c]
        else:
            seen_b = True
            sb += inst.dem[c]
    if sl > inst.Q or sb > inst.Q:
        return False
    if mode == "S" and seen_l and seen_b:
        return False
    return True


def _recreate(st, removed, rng, noise):
    inst, D = st.inst, st.inst.D
    for c in removed:
        best = None
        for ri, r in enumerate(st.routes):
            for q in range(len(r) + 1):
                if not _ins_ok(st, c, ri, q):
                    continue
                delta = _insert_cost(D, r, q, c)
                key = delta * (1.0 + noise * (rng.uniform() - 0.5))
                if best is None or key < best[0]:
                    best = (key, ri, q)
        new_key = 2 * D[0][c] * (1.0 + noise * (rng.uniform() - 0.5))
        if best is None or new_key < best[0]:
            ri = st.add_route()
            st.routes[ri].insert(0, c)
            st.refresh(ri)
        else:
            _, ri, q = best
            st.routes[ri].insert(q, c)
            st.refresh(ri)


def solve_ils(inst, mode, iters, seed, start=None):
    """Ruin-and-Recreate mit Lokalsuche (Relocate, Swap, 2-opt, 2-opt*), Annahme nach Record-to-Record (0,4 % über dem Besten).
    Das Beste wird mitgeführt; mehr Iterationen sind bei gleichem Zufalls-Seed nie schlechter."""
    rng = SplitMix64(seed * 1000003 + 17)
    if start is None:
        start = savings_pure(inst)
    st = _local_search(_St(inst, start, mode))
    best = [r[:] for r in st.routes]
    best_c = st.cost()
    cur = [r[:] for r in st.routes]
    cur_c = best_c
    stale = 0
    n = inst.n
    for _ in range(iters):
        s2 = _St(inst, cur, mode)
        kmax = max(4, n // 3)
        k = min(n, 2 + rng.below(kmax - 1))
        u = rng.uniform()
        if u < 0.34:
            removed = []
            pool = [c for c in range(1, n + 1)]
            for _j in range(k):
                c = pool.pop(rng.below(len(pool)))
                removed.append(c)
        elif u < 0.67:
            seed_c = 1 + rng.below(n)
            removed = [seed_c] + inst.neighbors(10)[seed_c][:k - 1]
        else:
            # ganze Route entfernen (bei Backhaul: Voraussetzung, um Touren zusammenzulegen), bei zwei Routen der Nachbarroute des Kerns
            ri0 = rng.below(len(s2.routes))
            removed = s2.routes[ri0][:]
            if rng.uniform() < 0.5 and len(s2.routes) > 1:
                c0 = removed[rng.below(len(removed))]
                for v in inst.neighbors(10)[c0]:
                    if s2.where[v][0] != ri0:
                        removed += s2.routes[s2.where[v][0]]
                        break
        for c in removed:
            ri, idx = s2.where[c]
            s2.routes[ri].remove(c)
            s2.refresh(ri)
        s2.compact()
        order = removed[:]
        for i in range(len(order) - 1, 0, -1):
            j = rng.below(i + 1)
            order[i], order[j] = order[j], order[i]
        _recreate(s2, order, rng, 0.3)
        s2.compact()
        _local_search(s2)
        c2 = s2.cost()
        if c2 < best_c:
            best_c = c2
            best = [r[:] for r in s2.routes]
            stale = 0
        else:
            stale += 1
        if c2 <= best_c * 1.004:
            cur, cur_c = [r[:] for r in s2.routes], c2
        if stale >= 80:
            cur, cur_c = [r[:] for r in best], best_c
            stale = 0
    return best


def solve_cvrp(inst, iters, seed):
    return solve_ils(inst, "S", iters, seed)



# ------------------------------------------------------------------------------------------------ allgemeine Suche (S1, M)

def _ins_cost(D, r, q, c):
    p = r[q - 1] if q > 0 else 0
    nx = r[q] if q < len(r) else 0
    return D[p][c] + D[c][nx] - D[p][nx]


def _build_where(routes):
    where = {}
    for ri, r in enumerate(routes):
        for idx, c in enumerate(r):
            where[c] = (ri, idx)
    return where


def _cost(inst, routes):
    return total_cost(inst, routes)


def local_search(inst, mode, routes):
    """Relocate, Swap (beliebige Arten), 2-opt innerhalb einer Tour, 2-opt*; Zulässigkeit nur für verbessernde Kandidaten geprüft."""
    D = inst.D
    nbr = inst.neighbors(10)
    n = inst.n
    routes = [r[:] for r in routes if r]
    where = _build_where(routes)
    custs = list(range(1, n + 1))
    improved = True
    guard = 0
    while improved and guard < 200:
        guard += 1
        improved = False
        # --- Relocate
        for c in custs:
            ri, idx = where[c]
            r = routes[ri]
            p = r[idx - 1] if idx > 0 else 0
            nx = r[idx + 1] if idx + 1 < len(r) else 0
            gain = D[p][c] + D[c][nx] - D[p][nx]
            base = r[:idx] + r[idx + 1:]
            cands = []
            for v in nbr[c]:
                rj, jdx = where[v]
                if rj == ri:
                    pv = jdx if jdx < idx else jdx - 1
                    for q in (pv, pv + 1):
                        if q == idx:
                            continue
                        delta = _ins_cost(D, base, q, c) - gain
                        if delta < 0:
                            cands.append((delta, rj, q))
                else:
                    rv = routes[rj]
                    for q in (jdx, jdx + 1):
                        delta = _ins_cost(D, rv, q, c) - gain
                        if delta < 0:
                            cands.append((delta, rj, q))
            if len(r) > 1:
                delta = 2 * D[0][c] - gain
                if delta < 0:
                    cands.append((delta, -1, 0))
            if not cands:
                continue
            cands.sort()
            for delta, rj, q in cands:
                if rj == -1:
                    routes[ri] = base
                    routes.append([c])
                elif rj == ri:
                    new = base[:q] + [c] + base[q:]
                    if not feas(inst, mode, new):
                        continue
                    routes[ri] = new
                else:
                    new = routes[rj][:q] + [c] + routes[rj][q:]
                    if not feas(inst, mode, new):
                        continue
                    routes[rj] = new
                    routes[ri] = base
                routes = [x for x in routes if x]
                where = _build_where(routes)
                improved = True
                break
        # --- Swap
        for c in custs:
            for v in nbr[c]:
                ri, idx = where[c]
                rj, jdx = where[v]
                if ri == rj:
                    continue
                r, rv = routes[ri], routes[rj]
                p1 = r[idx - 1] if idx > 0 else 0
                n1 = r[idx + 1] if idx + 1 < len(r) else 0
                p2 = rv[jdx - 1] if jdx > 0 else 0
                n2 = rv[jdx + 1] if jdx + 1 < len(rv) else 0
                delta = D[p1][v] + D[v][n1] + D[p2][c] + D[c][n2] - D[p1][c] - D[c][n1] - D[p2][v] - D[v][n2]
                if delta >= 0:
                    continue
                a = r[:idx] + [v] + r[idx + 1:]
                bb = rv[:jdx] + [c] + rv[jdx + 1:]
                if feas(inst, mode, a) and feas(inst, mode, bb):
                    routes[ri], routes[rj] = a, bb
                    where = _build_where(routes)
                    improved = True
                    break
        # --- 2-opt innerhalb einer Tour (ganze Tour; Zulässigkeit nur bei Gewinn)
        for ri in range(len(routes)):
            r = routes[ri]
            changed = True
            while changed:
                changed = False
                m = len(r)
                for i in range(m - 1):
                    a = r[i - 1] if i > 0 else 0
                    for j in range(i + 1, m):
                        b2 = r[j + 1] if j + 1 < m else 0
                        delta = D[a][r[j]] + D[r[i]][b2] - D[a][r[i]] - D[r[j]][b2]
                        if delta < 0:
                            new = r[:i] + r[i:j + 1][::-1] + r[j + 1:]
                            if feas(inst, mode, new):
                                r = new
                                changed = improved = True
                                break
                    if changed:
                        break
            routes[ri] = r
        where = _build_where(routes)
        # --- 2-opt* (Endstücke tauschen)
        for c in custs:
            for v in nbr[c]:
                ri, idx = where[c]
                rj, jdx = where[v]
                if ri == rj:
                    continue
                r1, r2 = routes[ri], routes[rj]
                p1, s1 = r1[:idx + 1], r1[idx + 1:]
                p2, s2 = r2[:jdx], r2[jdx:]
                nx1 = s1[0] if s1 else 0
                pv2 = p2[-1] if p2 else 0
                delta = D[c][v] + D[pv2][nx1] - D[c][nx1] - D[pv2][v]
                if delta >= 0:
                    continue
                if feas(inst, mode, p1 + s2) and (not (p2 + s1) or feas(inst, mode, p2 + s1)):
                    routes[ri], routes[rj] = p1 + s2, p2 + s1
                    routes = [x for x in routes if x]
                    where = _build_where(routes)
                    improved = True
                    break
    return [r for r in routes if r]


def _recreate_gen(inst, mode, routes, removed, rng, noise):
    D = inst.D
    for c in removed:
        cands = []
        for ri, r in enumerate(routes):
            for q in range(len(r) + 1):
                cands.append((_ins_cost(D, r, q, c) * (1.0 + noise * (rng.uniform() - 0.5)), ri, q))
        cands.append((2 * D[0][c] * (1.0 + noise * (rng.uniform() - 0.5)), -1, 0))
        cands.sort()
        for _key, ri, q in cands:
            if ri == -1:
                routes.append([c])
                break
            new = routes[ri][:q] + [c] + routes[ri][q:]
            if feas(inst, mode, new):
                routes[ri] = new
                break
    return routes


def solve_gen(inst, mode, iters, seed, start):
    """Eigene Suche (Ruin-and-Recreate mit Lokalsuche, Annahme nach Record-to-Record 0,4 %) für jeden Modus; die Startlösung muss zulässig
    sein (Kette S -> S1 -> A -> M). Das Beste wird mitgeführt; Ergebnis nie schlechter als die lokal verbesserte Startlösung."""
    for r in start:
        assert feas(inst, mode, r), ("Startlösung unzulässig", mode, r)
    rng = SplitMix64(seed * 1000003 + 17)
    n = inst.n
    cur = local_search(inst, mode, start)
    best = [r[:] for r in cur]
    best_c = _cost(inst, best)
    cur_c = best_c
    stale = 0
    for _ in range(iters):
        routes = [r[:] for r in cur]
        where = _build_where(routes)
        kmax = max(4, n // 3)
        k = min(n, 2 + rng.below(kmax - 1))
        u = rng.uniform()
        if u < 0.34:
            pool = list(range(1, n + 1))
            removed = []
            for _j in range(k):
                removed.append(pool.pop(rng.below(len(pool))))
        elif u < 0.67:
            seed_c = 1 + rng.below(n)
            removed = [seed_c] + inst.neighbors(10)[seed_c][:k - 1]
        else:
            ri0 = rng.below(len(routes))
            removed = routes[ri0][:]
            if rng.uniform() < 0.5 and len(routes) > 1:
                c0 = removed[rng.below(len(removed))]
                for v in inst.neighbors(10)[c0]:
                    if where[v][0] != ri0:
                        removed += routes[where[v][0]]
                        break
        rem = set(removed)
        routes = [[c for c in r if c not in rem] for r in routes]
        routes = [r for r in routes if r]
        order = removed[:]
        for i in range(len(order) - 1, 0, -1):
            j = rng.below(i + 1)
            order[i], order[j] = order[j], order[i]
        routes = _recreate_gen(inst, mode, routes, order, rng, 0.3)
        routes = local_search(inst, mode, routes)
        c2 = _cost(inst, routes)
        if c2 < best_c:
            best_c, best, stale = c2, [r[:] for r in routes], 0
        else:
            stale += 1
        if c2 <= best_c * 1.004:
            cur, cur_c = [r[:] for r in routes], c2
        if stale >= 80:
            cur, cur_c = [r[:] for r in best], best_c
            stale = 0
    return best


# ------------------------------------------------------------------------------------------------ Kette je Instanz

def chain(inst, iters, seed, with_m_from_s=True):
    """S -> S1 -> A -> M mit eigener Suche. S und A_ctl sind genau die Läufe der Hauptmessreihe (bh_core, Start S), A_chain startet bei S1,
    A = bessere von beiden. M = bessere von M_fromA (Start A) und M_fromS (Start S): die gemischte Suche kann aus der A-Lösung in einer
    Nachbarschaft steckenbleiben (Smoke-Test: M_fromS in 1 von 3 Instanzen besser), beide Starts sind zulässig. Gibt Lösungen je Stufe zurück."""
    t = {}
    _t0 = time.perf_counter()
    S = solve_ils(inst, "S", iters, seed)
    t["S"] = time.perf_counter() - _t0
    _t0 = time.perf_counter()
    A_ctl = solve_ils(inst, "A", iters, seed, start=S)
    t["A_ctl"] = time.perf_counter() - _t0
    _t0 = time.perf_counter()
    S1 = solve_gen(inst, "S1", iters, seed, start=S)
    t["S1"] = time.perf_counter() - _t0
    _t0 = time.perf_counter()
    A_chain = solve_ils(inst, "A", iters, seed, start=S1)
    t["A_chain"] = time.perf_counter() - _t0
    cA_ctl, cA_chain = total_cost(inst, A_ctl), total_cost(inst, A_chain)
    A = A_ctl if cA_ctl <= cA_chain else A_chain
    _t0 = time.perf_counter()
    M_fromA = solve_gen(inst, "M", iters, seed, start=A)
    t["M_fromA"] = time.perf_counter() - _t0
    out = dict(S=S, S1=S1, A=A, A_ctl=A_ctl, A_chain=A_chain, M_fromA=M_fromA)
    M = M_fromA
    if with_m_from_s:
        _t0 = time.perf_counter()
        out["M_fromS"] = solve_gen(inst, "M", iters, seed, start=S)
        t["M_fromS"] = time.perf_counter() - _t0
        if total_cost(inst, out["M_fromS"]) < total_cost(inst, M_fromA):
            M = out["M_fromS"]
    out["M"] = M
    out["_seconds"] = t   # Rechenzeit je Teillauf auf diesem Rechner (Zusatz der Demo; ändert nichts an den Lösungen)
    return out
