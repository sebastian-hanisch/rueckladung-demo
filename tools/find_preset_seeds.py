"""Sucht je Preset einen Zufalls-Seed außerhalb aller Messbereiche, dessen Instanz die Geschichte des Presets zeigt (rkl_stories.py).

Aufruf:  python tools/find_preset_seeds.py [Anzahl Seeds je Preset, Standard 24] [Prozesse, Standard 6]
Ausgabe: je Preset die passenden Seeds (erste Treffer) mit Ersparnis A, S1, M gegen S; das Zellmittel steht daneben (Wahl: Seed nahe am Zellmittel).
Die Messbereiche der Zufalls-Seeds: 1000-1011 (Abstimmung), 100000-103599 (Hauptraster), 200000+ (Nachmessung), 300000+ (Mengen-Raster); gesucht wird ab 500000.
"""
import multiprocessing as mp
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import rkl_constants as C  # noqa: E402
import rkl_evaluation as E  # noqa: E402
import rkl_results as R  # noqa: E402
import rkl_stories as S  # noqa: E402

START = 500000


def _job(args):
    name, seed = args
    p = C.PRESETS[name]
    st = E.Settings(p["n"], p["beta"], p["layout"], p["depot"], p["k"], p["ils"], seed)
    a = E.analyse(st)
    s = E.step_of(a, "S").dist
    gains = {k: E.saving(s, E.step_of(a, k).dist) for k in ("S1", "A", "M")}
    return name, seed, S.STORIES[name](a), gains


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    procs = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    jobs = [(name, START + i) for name in C.PRESETS for i in range(count)]
    res = {}
    with mp.Pool(procs) as pool:
        for name, seed, ok, gains in pool.imap_unordered(_job, jobs):
            res.setdefault(name, []).append((seed, ok, gains))
    for name in C.PRESETS:
        p = C.PRESETS[name]
        cell, _d, _e = R.nearest_cell(p["n"], p["beta"], p["layout"], p["k"], p["depot"])
        print(f"== {name}  (Zellmittel A {cell['dD_A'][0]:.1f} %, S1 {cell['dD_S1'][0]:.1f} %, M {cell['dD_M'][0]:.1f} %)")
        rows = sorted(res[name])
        passing = [r for r in rows if r[1]]
        print(f"   {len(passing)} von {len(rows)} Seeds erfüllen die Geschichte")
        for seed, ok, g in sorted(passing, key=lambda r: abs(r[2]["A"] - cell["dD_A"][0]))[:5]:
            print(f"   Seed {seed}: S1 {g['S1']:.1f} %, A {g['A']:.1f} %, M {g['M']:.1f} %")


if __name__ == "__main__":
    mp.freeze_support()
    main()
