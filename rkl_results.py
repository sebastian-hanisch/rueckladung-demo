"""Laden und Auswerten der vorgerechneten Messreihe (data/rkl_results.json, erzeugt von tools/dump_results.py).

Alle Zahlen der App stammen aus dieser Datei (`tests/test_claims.py` rechnet sie nach):
  cells    72 Zellen der Restmessung AP 0 (36 je Depot, je 25 Instanzen, nur eigene Suche, Stufen S, S1, A, M)
  main     36 Zellen der Hauptmessreihe (Depot am Rand, beste bekannte Lösung aller Verfahren, S und A)
  nach     Nachmessung der Extremwerte von beta (n = 20, K_L = 2, nur eigene Suche)
  loeser, timing, zusatz, referenz
"""

import json
import pathlib
from functools import lru_cache

import rkl_constants as C

DATA = pathlib.Path(__file__).resolve().parent / "data"
ORDER = ("n", "beta", "layout", "K_L", "depot")
AXES = {"n": C.N_OPTIONS, "beta": C.BETA_OPTIONS, "layout": C.LAYOUT_OPTIONS, "K_L": C.K_OPTIONS, "depot": C.DEPOT_OPTIONS}


@lru_cache(maxsize=1)
def load():
    return json.loads((DATA / "rkl_results.json").read_text(encoding="utf-8"))


def cells(depot=None):
    cs = load()["cells"]
    return cs if depot is None else [c for c in cs if c["depot"] == depot]


# ------------------------------------------------------------------------------------------------ Zellen-Zuordnung

def _nearest_index(axis, value):
    if value in axis:
        return axis.index(value)
    if all(isinstance(x, (int, float)) for x in axis):
        return min((abs(x - value), i) for i, x in enumerate(axis))[1]
    raise ValueError(f"unbekannter Wert {value!r}")


def nearest_cell(n, beta, layout, K_L, depot):
    """Nächstliegende gemessene Zelle (Abstand = Summe der Stufenabstände, Gleichstand: kleinerer Index in der Reihenfolge n, beta, Lage, K_L, Depot).
    Gibt (Zelle, Abstand, genau) zurück; genau = True, wenn die Einstellung selbst gemessen ist. Alle Regler der App stehen auf Stufen: dann ist es immer genau."""
    want = dict(n=n, beta=beta, layout=layout, K_L=K_L, depot=depot)
    idx = {k: _nearest_index(AXES[k], want[k]) for k in ORDER}
    snapped_exact = all(want[k] in AXES[k] for k in ORDER)
    best = None
    for cell in cells():
        ci = {k: AXES[k].index(cell[k]) for k in ORDER}
        dist = sum(abs(ci[k] - idx[k]) for k in ORDER)
        key = (dist, tuple(ci[k] for k in ORDER))
        if best is None or key < best[0]:
            best = (key, cell, dist)
    return best[1], best[2], (best[2] == 0 and snapped_exact)


# ------------------------------------------------------------------------------------------------ Zustände, Zählungen

def level(d_a):
    """'wenig' (unter 10 %), 'deutlich' (10 bis unter 25 %), 'sehr' (ab 25 %) aus dem Zellmittel der Distanzersparnis S -> A in Prozent."""
    if d_a < C.LEVEL_WENIG:
        return "wenig"
    if d_a < C.LEVEL_SEHR:
        return "deutlich"
    return "sehr"


def level_counts(depot):
    out = {"wenig": 0, "deutlich": 0, "sehr": 0}
    for c in cells(depot):
        out[level(c["dD_A"][0])] += 1
    return out


def r_of(cell):
    """Anteil R der A-Ersparnis, den S1 schon holt (Verhältnis der Zellmittel); None, wenn A in der Zelle nichts spart."""
    return cell["R"]


def r_counts(depot):
    rs = sorted(c["R"] for c in cells(depot) if c["R"] is not None)
    mid = len(rs) // 2
    median = rs[mid] if len(rs) % 2 else (rs[mid - 1] + rs[mid]) / 2
    return {"deutlich_zurueck": sum(1 for r in rs if r <= C.R_DEUTLICH_ZURUECK), "fast_alles": sum(1 for r in rs if r >= C.R_FAST_ALLES), "zellen": len(rs),
            "median": median, "max": rs[-1]}


def m_counts(depot):
    cs = cells(depot)
    return {"ab_2": sum(1 for c in cs if c["dD_AM"][0] >= 2.0), "unter_1": sum(1 for c in cs if c["dD_AM"][0] < 1.0), "zellen": len(cs)}


def getrennt_m(depot):
    """Bei getrennten Zonen: Zahl der Instanzen mit M gleich A, Zahl der Instanzen und Mittel von ΔD(A->M) über die Zellen (Prozent)."""
    cs = [c for c in cells(depot) if c["layout"] == "getrennt"]
    return {"gleich": sum(c["gleich"]["M_A"] for c in cs), "instanzen": sum(c["m"] for c in cs), "zellen": len(cs), "mittel": sum(c["dD_AM"][0] for c in cs) / len(cs)}


def zusatz_vergleich(key):
    """Zusatzraster ungleicher Mengen ('klein' oder 'gross') gegen dieselben 12 Zellen des Hauptrasters (AP 0, Depot am Rand): Mittel von S1 und A, Anteil R und Differenzen in Prozentpunkten."""
    z = load()["zusatz"][key]
    haupt = {(c["n"], c["beta"], c["layout"], c["K_L"]): c for c in cells("rand")}
    ref = [haupt[(c["n"], c["beta"], c["layout"], c["K_L"])] for c in z["cells"]]
    s1_h = sum(c["dD_S1"][0] for c in ref) / len(ref)
    a_h = sum(c["dD_A"][0] for c in ref) / len(ref)
    return {"s1_haupt": s1_h, "a_haupt": a_h, "r_haupt": s1_h / a_h, "r": z["overall"]["dD_S1"] / z["overall"]["dD_A"],
            "d_s1": z["overall"]["dD_S1"] - s1_h, "d_a": z["overall"]["dD_A"] - a_h}


def nach_instanzen():
    """Zahl der Instanzen der Nachmessung (Zellen mal Instanzen je Zelle)."""
    return sum(r["m"] for r in load()["nach"])


def urteil_s1(depot="rand"):
    n = r_counts(depot)
    if n["fast_alles"] >= 24:
        return "S1 holt fast alles"
    if n["deutlich_zurueck"] >= 24:
        return "S1 deutlich zurück"
    return "gemischt, regimeabhängig"


def urteil_m(depot="rand"):
    n = m_counts(depot)
    if n["ab_2"] >= 12:
        return "M bringt etwas"
    if n["unter_1"] >= 24:
        return "M bringt fast nichts"
    return "gemischt"


def stage_means(depot):
    return load()["overall"][depot]


def depot_diff():
    """Rand gegen Mitte je Zelle (gleiche Instanzen): ΔD(S->A), Mittel der Differenz Rand minus Mitte, Spanne und Zahl der Zellen, in denen die Mitte höher liegt."""
    rand = {(c["n"], c["beta"], c["layout"], c["K_L"]): c for c in cells("rand")}
    diffs = []
    for c in cells("mitte"):
        diffs.append(rand[(c["n"], c["beta"], c["layout"], c["K_L"])]["dD_A"][0] - c["dD_A"][0])
    return {"mittel": sum(diffs) / len(diffs), "min": min(diffs), "max": max(diffs), "mitte_hoeher": sum(1 for d in diffs if d < 0), "zellen": len(diffs)}


def _val(cell, key):
    x = cell[key]
    return x[0] if isinstance(x, (list, tuple)) else x


def min_cell(depot, key="dD_A"):
    return min(cells(depot), key=lambda c: _val(c, key))


def max_cell(depot, key="dD_A"):
    return max(cells(depot), key=lambda c: _val(c, key))


def main_cells():
    return load()["main"]["cells"]


def main_param_means():
    """Mittel von ΔD (Hauptmessreihe, beste bekannte Lösung) je Parameterwert über die Zellen und die Spreizung je Parameter in Prozentpunkten."""
    out = {}
    for param in ("beta", "layout", "K_L", "n"):
        vals = sorted({c[param] for c in main_cells()}, key=lambda v: (str(type(v)), v))
        means = {v: sum(c["dD"] for c in main_cells() if c[param] == v) / sum(1 for c in main_cells() if c[param] == v) for v in vals}
        out[param] = {"means": means, "spread": max(means.values()) - min(means.values())}
    return out


def nach_rows(depot=None, layout=None):
    rows = load()["nach"]
    if depot is not None:
        rows = [r for r in rows if r["depot"] == depot]
    if layout is not None:
        rows = [r for r in rows if r["layout"] == layout]
    return sorted(rows, key=lambda r: (r["depot"], r["layout"], r["beta"]))


def nach_min():
    return min(load()["nach"], key=lambda r: r["dD"][0])


def other_depot(cell):
    """Dieselbe Zelle mit dem anderen Depot."""
    other = "mitte" if cell["depot"] == "rand" else "rand"
    return next(c for c in cells(other) if (c["n"], c["beta"], c["layout"], c["K_L"]) == (cell["n"], cell["beta"], cell["layout"], cell["K_L"]))


def cell_number(cell):
    """Zellennummer 0 bis 35 (wie in der Messreihe und in der README)."""
    return cell["ci"]


# ------------------------------------------------------------------------------------------------ Formatierung

def num(x, digits=1, sign=False):
    return (f"{x:+.{digits}f}" if sign else f"{x:.{digits}f}").replace(".", ",")


def pm(pair, digits=1, sign=False):
    """[Mittel, Standardfehler] als Text 'Mittel ± SE' mit Dezimalkomma."""
    mean, se = pair
    text = f"{mean:+.{digits}f}" if sign else f"{mean:.{digits}f}"
    return f"{text} ± {se:.{digits}f}".replace(".", ",")
