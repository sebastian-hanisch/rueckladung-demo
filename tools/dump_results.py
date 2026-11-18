"""Erzeugt data/rkl_results.json aus den Rohdaten der Vormessung (Backhaul-Hauptmessreihe) und der Restmessung AP 0.

Rohdaten liegen NICHT im Repo. Quellordner per Umgebungsvariable RKL_RAW_DIR (Standard: ../tourenplanung-planung neben dem Repo); darin:
  messreihe_backhaul/analyse.json, analyse_out.txt, nach_raw.jsonl
  messreihe_backhaul_ap0/sweep_rand.jsonl, sweep_mitte.jsonl, sweep_klein.jsonl, sweep_gross.jsonl, timing_out.txt

Aufruf:  python tools/dump_results.py           (schreibt data/rkl_results.json und gibt Größe und Zählungen aus)
Alle Zahlen der App und der README kommen aus dieser Datei; tests/test_claims.py rechnet sie nach.
"""
import json
import math
import os
import pathlib
import re
import statistics

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
RAW = pathlib.Path(os.environ.get("RKL_RAW_DIR", REPO.parent / "tourenplanung-planung"))
MAIN = RAW / "messreihe_backhaul"
AP0 = RAW / "messreihe_backhaul_ap0"
OUT = REPO / "data" / "rkl_results.json"
STAGES = ("S", "S1", "A", "M")


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def mean(xs):
    return sum(xs) / len(xs)


def mean_se(xs):
    m = mean(xs)
    if len(xs) < 2:
        return [m, 0.0]
    return [m, statistics.stdev(xs) / math.sqrt(len(xs))]


def pct(a, b):
    """Ersparnis (a - b) / a in Prozent; a = 0 -> 0 (nichts zu sparen)."""
    return 0.0 if a <= 0 else 100.0 * (a - b) / a


def cell_stats(rows):
    """Zellenstatistik für Zeilen einer Zelle (gleiche n, beta, layout, K_L, depot)."""
    out = {"m": len(rows)}
    out["dD_S1"] = mean_se([pct(r["cost"]["S"], r["cost"]["S1"]) for r in rows])
    out["dD_A"] = mean_se([pct(r["cost"]["S"], r["cost"]["A"]) for r in rows])
    out["dD_M"] = mean_se([pct(r["cost"]["S"], r["cost"]["M"]) for r in rows])
    out["dD_AM"] = mean_se([pct(r["cost"]["A"], r["cost"]["M"]) for r in rows])
    out["R"] = None if out["dD_A"][0] <= 0 else out["dD_S1"][0] / out["dD_A"][0]
    out["dV_A"] = mean([pct(r["met"]["S"]["vehicles"], r["met"]["A"]["vehicles"]) for r in rows])
    out["dE_A"] = mean([pct(r["met"]["S"]["empty"], r["met"]["A"]["empty"]) for r in rows])
    out["touren"] = {s: mean([r["met"][s]["vehicles"] for r in rows]) for s in STAGES}
    out["leer"] = {s: mean([100.0 * r["met"][s]["empty"] / r["met"][s]["dist"] for r in rows]) for s in STAGES}
    out["last"] = {s: mean([100.0 * r["met"][s]["load_share"] for r in rows]) for s in STAGES}
    out["gleich"] = {"S1_S": sum(r["cost"]["S1"] == r["cost"]["S"] for r in rows), "A_S1": sum(r["cost"]["A"] == r["cost"]["S1"] for r in rows),
                     "M_A": sum(r["cost"]["M"] == r["cost"]["A"] for r in rows)}
    out["minD_A"] = min(pct(r["cost"]["S"], r["cost"]["A"]) for r in rows)
    out["maxD_A"] = max(pct(r["cost"]["S"], r["cost"]["A"]) for r in rows)
    return out


def grid_cells(rows, grid):
    by = {}
    for r in rows:
        by.setdefault(r["ci"], []).append(r)
    cells = []
    for ci in sorted(by):
        rr = by[ci]
        r0 = rr[0]
        c = {"grid": grid, "ci": ci, "n": r0["n"], "beta": r0["beta"], "layout": r0["layout"], "K_L": r0["K_L"], "depot": "mitte" if grid == "mitte" else "rand"}
        c.update(cell_stats(rr))
        cells.append(c)
    return cells


def overall(rows):
    return {"m": len(rows), "dD_S1": mean([pct(r["cost"]["S"], r["cost"]["S1"]) for r in rows]), "dD_A": mean([pct(r["cost"]["S"], r["cost"]["A"]) for r in rows]),
            "dD_M": mean([pct(r["cost"]["S"], r["cost"]["M"]) for r in rows]), "dD_AM": mean([pct(r["cost"]["A"], r["cost"]["M"]) for r in rows])}


def parse_loeser(text):
    """Lösergüte aus analyse_out.txt der Hauptmessreihe (Zeilen 'n=20 Modus A: ils: 0,02 % (am Besten 441/450); ...')."""
    res = {}
    for m in re.finditer(r"n=(\d+) Modus (\w): (.*)", text):
        n, mode, rest = int(m.group(1)), m.group(2), m.group(3)
        d = {}
        for part in rest.split(";"):
            mm = re.match(r"\s*(\w+): ([\d,]+) % \(am Besten (\d+)/(\d+)\)", part)
            if mm:
                d[mm.group(1)] = {"gap": float(mm.group(2).replace(",", ".")), "best": int(mm.group(3)), "of": int(mm.group(4))}
        res[f"n{n}_{mode}"] = d
    ex = {}
    for m in re.finditer(r"Exakt n = 20, Modus (\w): bewiesen (\d+) von (\d+); eigene Suche gegen bewiesenes Optimum: Lücke ([\d,]+) %, optimal in (\d+) von (\d+); "
                         r"OR-Tools Standard ([\d,]+) %, SAVINGS ([\d,]+) %\s*\n\s*nicht bewiesen: (\d+); mittlerer Abstand der besten Lösung zur Schranke ([\d,]+) % \(max ([\d,]+) %\)", text):
        f = lambda s: float(s.replace(",", "."))  # noqa: E731
        ex[m.group(1)] = {"proven": int(m.group(2)), "of": int(m.group(3)), "ils_gap": f(m.group(4)), "ils_opt": int(m.group(5)), "ils_of": int(m.group(6)),
                          "ort_std": f(m.group(7)), "ort_sav": f(m.group(8)), "unproven": int(m.group(9)), "bound_gap": f(m.group(10)), "bound_gap_max": f(m.group(11))}
    res["exakt_n20"] = ex
    return res


def parse_timing(text):
    out = []
    for line in text.splitlines():
        m = re.match(r"n=(\d+) Iterationen=(\d+): (.*)", line)
        if not m:
            continue
        row = {"n": int(m.group(1)), "iters": int(m.group(2))}
        for mm in re.finditer(r"(\w+) ([\d.]+) s \(([\d.]+) bis ([\d.]+)\)", m.group(3)):
            row[mm.group(1)] = {"mean": float(mm.group(2)), "lo": float(mm.group(3)), "hi": float(mm.group(4))}
        out.append(row)
    return out


def main():
    main_a = json.loads((MAIN / "analyse.json").read_text(encoding="utf-8"))
    rand = read_jsonl(AP0 / "sweep_rand.jsonl")
    mitte = read_jsonl(AP0 / "sweep_mitte.jsonl")
    klein = read_jsonl(AP0 / "sweep_klein.jsonl")
    gross = read_jsonl(AP0 / "sweep_gross.jsonl")
    nach = read_jsonl(MAIN / "nach_raw.jsonl")

    cells = grid_cells(rand, "rand") + grid_cells(mitte, "mitte")
    data = {
        "meta": {"quellen": ["messreihe_backhaul", "messreihe_backhaul_ap0"], "instanzen_je_zelle": 25, "zufalls_seeds": "100000 + 100 * Zelle + laufende Nummer",
                 "eigene_suche_iterationen": 1000},
        "cells": cells,
        "overall": {"rand": overall(rand), "mitte": overall(mitte)},
        "main": {
            "cells": [{"ci": int(k), **{x: v[x] for x in ("n", "beta", "layout", "K_L", "m", "dD", "dD_se", "dV", "dE", "VS", "VA", "ES", "EA", "LS", "LA", "less", "equal", "minD", "maxD")}}
                      for k, v in sorted(main_a["stat"].items(), key=lambda kv: int(kv[0]))],
            "dd_all": main_a["dd_all"], "dd_ort": main_a["dd_ort"], "dd_ils": main_a["dd_ils"], "P": main_a["P"],
            "nD": main_a["nD"], "nG": main_a["nG"], "nV": main_a["nV"], "ampel": main_a["ampel"],
        },
        "loeser": parse_loeser((MAIN / "analyse_out.txt").read_text(encoding="utf-8")),
        "timing": parse_timing((AP0 / "timing_out.txt").read_text(encoding="utf-8")),
    }
    # Nachmessung: Zellmittel von dD je (Depot, Lage, beta)
    rows = {}
    for r in nach:
        rows.setdefault((r["depot"], r["layout"], r["beta"]), []).append(100.0 * (r["DS"] - r["DA"]) / r["DS"])
    data["nach"] = [{"depot": d, "layout": lay, "beta": b, "m": len(v), "dD": mean_se(v)} for (d, lay, b), v in sorted(rows.items())]
    # Zusatzraster ungleiche Mengen (n = 20), je Zelle gegen die gleiche Zelle des Hauptrasters mit gleichen Parametern (andere Instanzen)
    rand_cell = {(c["n"], c["beta"], c["layout"], c["K_L"]): c for c in cells if c["grid"] == "rand"}
    zus = {}
    for name, rows_ in (("klein", klein), ("gross", gross)):
        zc = grid_cells(rows_, name)
        for c in zc:
            c["dD_A_rand_haupt"] = rand_cell[(c["n"], c["beta"], c["layout"], c["K_L"])]["dD_A"][0]
        zus[name] = {"overall": overall(rows_), "cells": zc}
    data["zusatz"] = zus
    # Referenzinstanzen für den Neu-Rechnen-Test (n = 20, je eine am Rand und in der Mitte)
    ref = []
    for grid, rows_ in (("rand", rand), ("mitte", mitte)):
        r = next(x for x in rows_ if x["n"] == 20 and x["ci"] == 6 and x["k"] == 0)
        ref.append({"grid": grid, "n": r["n"], "beta": r["beta"], "layout": r["layout"], "K_L": r["K_L"], "seed": r["seed"], "iters": 1000,
                    "cost": {s: r["cost"][s] for s in STAGES}})
    data["referenz"] = ref
    # Wie oft gewinnt der Start von S bei M (M = bessere von M_fromA und M_fromS)? Zählung je Depot über die 900 Instanzen
    data["m_start"] = {g: {"von_s_besser": sum(1 for r in rows_ if r["cost"]["M_fromS"] < r["cost"]["M_fromA"]), "m": len(rows_)} for g, rows_ in (("rand", rand), ("mitte", mitte))}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(OUT, OUT.stat().st_size, "Bytes;", len(cells), "Zellen")


if __name__ == "__main__":
    main()
