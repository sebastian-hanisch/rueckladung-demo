"""Aussagen gegen Zählungen (DEMO-PLAYBOOK §11a): JEDE Zahl der README und der App wird hier aus `data/rkl_results.json` nachgerechnet und steht zugleich als Text in der README.

Aufbau je Test: (1) die Zahl aus den Zellen der Ergebnisdatei rechnen (Zählung über das ganze Raster, nicht eine Zelle), (2) denselben Wortlaut in der README suchen. Wer die README ändert,
ohne die Messung zu ändern, bricht (2); wer die Messung ändert, bricht (1). Die Rohdaten selbst liegen nicht im Repo (`tools/dump_results.py`); ihre Verdichtung ist an den Handwerten geprüft
(`tests/test_results.py`). Die Zeile `Testname` der Befunde-Tabelle der README nennt den Test, der die Zeile belegt."""

import re
from pathlib import Path

import pytest

import rkl_constants as C
import rkl_model as M
import rkl_results as R
import rkl_search as SR

README = (Path(__file__).resolve().parent.parent / "README.md").read_text(encoding="utf-8")
n = R.num


def has(*texts):
    for t in texts:
        assert t in README, t


def test_jeder_testname_der_befundetabelle_existiert():
    names = set(re.findall(r"`(test_claim_[a-z0-9_]+)`", README))
    assert len(names) >= 14
    defined = set(re.findall(r"^def (test_claim_[a-z0-9_]+)\(", Path(__file__).read_text(encoding="utf-8"), re.M))
    assert names <= defined, names - defined


def test_claim_a_spart_in_allen_900_instanzen():
    mc = R.main_cells()
    assert len(mc) == 36 and sum(c["m"] for c in mc) == 900
    assert sum(c["less"] for c in mc) == 900 and sum(c["equal"] for c in mc) == 0
    lo, hi = min(mc, key=lambda c: c["dD"]), max(mc, key=lambda c: c["dD"])
    assert (lo["ci"], n(lo["dD"]), hi["ci"], n(hi["dD"])) == (21, "14,1", 13, "33,5")
    assert (lo["n"], lo["beta"], lo["layout"], lo["K_L"]) == (40, 0.2, "getrennt", 4) and (hi["n"], hi["beta"], hi["layout"], hi["K_L"]) == (20, 0.6, "gemischt", 4)
    assert n(R.load()["main"]["dd_all"]) == "23,9"
    has("In allen 900 Instanzen", "A gleich S in keiner", "von 14,1 % (Zelle 21: n = 40, β = 20 %, getrennt, K_L = 4) bis 33,5 % (Zelle 13: n = 20, β = 60 %, gemischt, K_L = 4)", "Mittel über alle Instanzen 23,9 %")


def test_claim_touren_und_leerkilometer():
    mc = R.main_cells()
    assert (n(min(c["dV"] for c in mc)), n(max(c["dV"] for c in mc))) == ("21,6", "48,0")
    assert (n(min(c["dE"] for c in mc)), n(max(c["dE"] for c in mc))) == ("35,4", "84,0")
    assert all(c["dV"] >= 15.0 for c in mc) and R.load()["main"]["nV"] == 36
    has("an Touren 21,6 bis 48,0 %", "an Leerkilometern 35,4 bis 84,0 %", "in allen 36 Zellen mindestens 15 % Touren", "kaum Kilometer")


def test_claim_keine_zelle_ohne_ersparnis():
    mc = R.main_cells()
    assert sum(1 for c in mc if c["dD"] < 2.0) == 0 and sum(1 for c in mc if c["dD"] >= 5.0) == 36
    assert R.load()["main"]["nG"] == 0 and R.load()["main"]["nD"] == 36 and R.load()["main"]["ampel"] == "GELB"
    assert n(min(c["dD"] for c in mc), 1) == "14,1"
    has("0 von 36 Zellen", "36 von 36", "gelb", "Im gemessenen Raster nein", "kleinstes Zellenmittel 14,1 %")


def test_claim_hebel():
    pm = R.main_param_means()
    b = pm["beta"]["means"]
    assert (n(b[0.2]), n(b[0.4]), n(b[0.6]), n(pm["beta"]["spread"])) == ("18,2", "25,6", "27,9", "9,7")
    lay = pm["layout"]["means"]
    assert (n(lay["gemischt"]), n(lay["ueberlappend"]), n(lay["getrennt"]), n(pm["layout"]["spread"])) == ("25,8", "25,0", "21,0", "4,8")
    k = pm["K_L"]["means"]
    assert (n(k[2]), n(k[4]), n(pm["K_L"]["spread"])) == ("22,2", "25,6", "3,3")
    nn = pm["n"]["means"]
    assert (n(nn[20]), n(nn[40]), n(pm["n"]["spread"])) == ("25,4", "22,4", "3,0")
    assert max(pm, key=lambda x: pm[x]["spread"]) == "beta"
    has("β 18,2 / 25,6 / 27,9 % bei 20 / 40 / 60 %", "Spreizung 9,7 Prozentpunkte, die größte", "Lage gemischt 25,8, überlappend 25,0, getrennt 21,0 % (4,8 Pp)", "K_L 22,2 gegen 25,6 % (3,3 Pp)", "n 25,4 gegen 22,4 % (3,0 Pp)")


def test_claim_loeser_unabhaengig():
    m = R.load()["main"]
    assert (n(m["dd_all"], 2), n(m["dd_ort"], 2), n(m["dd_ils"], 2)) == ("23,90", "23,82", "23,89")
    assert abs(m["dd_ort"] - m["dd_all"]) <= 2.0         # Prüfung der Vormessung: höchstens 2 Prozentpunkte
    assert n(abs(m["dd_ort"] - m["dd_all"]), 1) == "0,1"
    has("23,90 % aus der besten Lösung, 23,82 % nur aus den OR-Tools-Läufen, 23,89 % nur aus der eigenen Suche", "Abweichung der OR-Tools-Läufe 0,1 Prozentpunkte im Mittel")


def test_claim_loeserguete():
    lo = R.load()["loeser"]
    ex = lo["exakt_n20"]
    assert (ex["S"]["ils_gap"], ex["S"]["ils_opt"], ex["S"]["ils_of"], ex["A"]["ils_gap"], ex["A"]["ils_opt"], ex["A"]["ils_of"]) == (0.026, 151, 153, 0.03, 251, 258)
    assert (ex["S"]["ort_std"], ex["S"]["ort_sav"], ex["A"]["ort_std"], ex["A"]["ort_sav"]) == (0.52, 0.36, 0.35, 0.37)
    assert (lo["n40_S"]["ils"]["gap"], lo["n40_A"]["ils"]["gap"]) == (0.01, 0.04)
    ort40 = [lo[k][s]["gap"] for k in ("n40_S", "n40_A") for s in ("ort_standard", "ort_tuned")]
    assert (min(ort40), max(ort40)) == (1.19, 1.68)
    has("Lücke 0,026 % in S (optimal in 151 von 153 bewiesenen Instanzen) und 0,030 % in A (251 von 258)", "in S 0,52 % (Standard) und 0,36 % (SAVINGS), in A 0,35 % (Standard) und 0,37 % (SAVINGS)",
        "eigene Suche 0,01 % (S) und 0,04 % (A), OR-Tools 1,19 bis 1,68 %")


def test_claim_cp_sat():
    ex = R.load()["loeser"]["exakt_n20"]
    assert (ex["S"]["proven"], ex["A"]["proven"], ex["S"]["of"], ex["A"]["of"]) == (153, 258, 450, 450)
    assert (ex["S"]["unproven"], ex["A"]["unproven"]) == (297, 192)
    assert (n(ex["S"]["bound_gap"], 2), n(ex["A"]["bound_gap"], 2), n(ex["S"]["bound_gap_max"], 2), n(ex["A"]["bound_gap_max"], 2)) == ("34,39", "42,55", "55,90", "62,65")
    has("S in 153, A in 258", "liegt die Schranke im Mittel 34,39 % (S) und 42,55 % (A) unter der besten Lösung (bezogen auf die beste Lösung; höchstens 55,90 % und 62,65 %)",
        "S in zwei CVRP zerlegt mit je 20 s", "bei 20 Kunden in 153 von 450 Instanzen für S und 258 von 450 für A")


def test_claim_s1():
    st = R.stage_means("rand")
    assert (n(st["dD_S1"]), n(st["dD_A"]), n(st["dD_S1"] / st["dD_A"], 2)) == ("7,4", "23,9", "0,31")
    rc = R.r_counts("rand")
    assert (rc["deutlich_zurueck"], rc["fast_alles"], rc["zellen"], n(rc["median"], 2)) == (29, 0, 36, "0,26")
    c1 = R.cells("rand")[1]
    assert (c1["ci"], c1["n"], c1["beta"], c1["layout"], c1["K_L"], n(c1["R"], 2)) == (1, 20, 0.2, "gemischt", 4, "0,80") and R.max_cell("rand", "R")["ci"] == 1
    assert n(c1["R"], 3) == "0,799" and c1["R"] < C.R_FAST_ALLES      # knapp unter der Schwelle 0,8
    assert R.urteil_s1("rand") == "S1 deutlich zurück"
    has("Im Mittel 7,4 % von 23,9 %", "(R = 0,31)", "R ≤ 0,5 in 29 von 36 Zellen, R ≥ 0,8 in 0, Median 0,26", "größte Zelle 1 (n = 20, β = 20 %, gemischt, K_L = 4) mit 0,799 (knapp unter der Schwelle 0,8)", "**S1 deutlich zurück**")


def test_claim_s1_mitte_und_treiber():
    st = R.stage_means("mitte")
    assert (n(st["dD_S1"]), n(st["dD_A"])) == ("6,3", "17,4")
    rc = R.r_counts("mitte")
    assert (rc["deutlich_zurueck"], rc["fast_alles"]) == (28, 1) and R.urteil_s1("mitte") == "S1 deutlich zurück"
    cs = R.cells("rand")

    def mean_r(key, value):
        sub = [c for c in cs if c[key] == value]
        return sum(c["R"] for c in sub) / len(sub)
    assert (n(mean_r("n", 20), 2), n(mean_r("n", 40), 2), n(mean_r("K_L", 2), 2), n(mean_r("K_L", 4), 2)) == ("0,40", "0,17", "0,18", "0,39")
    assert (n(mean_r("layout", "getrennt"), 2), n(mean_r("layout", "gemischt"), 2)) == ("0,19", "0,35")
    has("S1 6,3 % von 17,4 %", "R ≤ 0,5 in 28 von 36 Zellen, R ≥ 0,8 in 1", "n = 20: 0,40, n = 40: 0,17; K_L = 2: 0,18, K_L = 4: 0,39; Depot am Rand", "0,19 gegen 0,35 gemischt")


def test_claim_m():
    r, m = R.stage_means("rand"), R.stage_means("mitte")
    assert (n(r["dD_AM"]), n(m["dD_AM"])) == ("4,2", "5,5")
    assert (R.m_counts("rand")["ab_2"], R.m_counts("rand")["unter_1"], R.m_counts("mitte")["ab_2"], R.m_counts("mitte")["unter_1"]) == (19, 14, 23, 13)
    assert R.urteil_m("rand") == "M bringt etwas"

    def lay_mean(depot, layout):
        sub = [c for c in R.cells(depot) if c["layout"] == layout]
        return sum(c["dD_AM"][0] for c in sub) / len(sub)
    assert [n(lay_mean("rand", x)) for x in ("gemischt", "ueberlappend", "getrennt")] == ["8,5", "4,0", "0,0"]
    assert [n(lay_mean("mitte", x)) for x in ("gemischt", "ueberlappend", "getrennt")] == ["10,7", "5,7", "0,0"]
    full = [c["ci"] for c in R.cells("rand") if c["gleich"]["M_A"] == 25]
    assert full == [2, 8, 14, 15, 27] and all(R.cells("rand")[i]["layout"] == "getrennt" for i in full)
    for depot in ("rand", "mitte"):
        gm = R.getrennt_m(depot)
        assert (gm["gleich"], gm["instanzen"], n(gm["mittel"], 2)) == (282, 300, "0,03"), depot
    top = R.max_cell("rand", "dD_AM")
    assert (top["ci"], top["n"], top["beta"], top["layout"], top["K_L"], n(top["dD_AM"][0])) == (24, 40, 0.4, "gemischt", 2, "19,3")
    has("A gegen M im Mittel 4,2 % (Mitte 5,5 %)", "in 19 von 36 Zellen mindestens 2 % (Mitte 23), in 14 unter 1 % (Mitte 13)", "gemischt 8,5 %, überlappend 4,0 %, getrennt 0,0 % (Mitte 10,7 / 5,7 / 0,0 %)",
        "bei getrennten Zonen ist M fast immer gleich A (Depot am Rand und in der Mitte je 282 von 300 Instanzen gleich, Mittel von A gegen M 0,03 %)",
        "in den Zellen 2, 8, 14, 15 und 27 ist es in allen 25 Instanzen gleich A", "Größte Zelle 24 (n = 40, β = 40 %, gemischt, K_L = 2) mit 19,3 %")


def test_claim_m_start():
    ms = R.load()["m_start"]
    assert (ms["rand"]["von_s_besser"], ms["mitte"]["von_s_besser"], ms["rand"]["m"], ms["mitte"]["m"]) == (31, 29, 900, 900)
    has("in 31 von 900 Instanzen (Depot am Rand) und 29 von 900 (Depot in der Mitte)")


def test_claim_depot():
    d = R.depot_diff()
    st_r, st_m = R.stage_means("rand"), R.stage_means("mitte")
    assert (n(st_r["dD_A"]), n(st_m["dD_A"]), n(d["mittel"]), d["mitte_hoeher"], d["zellen"], n(d["min"]), n(d["max"])) == ("23,9", "17,4", "6,5", 0, 36, "1,5", "11,2")
    mc = R.min_cell("mitte")
    assert (mc["ci"], mc["n"], mc["beta"], mc["layout"], mc["K_L"], n(mc["dD_A"][0])) == (20, 40, 0.2, "getrennt", 2, "6,9")
    has("von 23,9 % auf 17,4 %", "im Mittel 6,5 Prozentpunkte", "0 von 36 Zellen höher", "von 1,5 bis 11,2 Pp", "kleinster Zellenmittelwert 6,9 % (Zelle 20: n = 40, β = 20 %, getrennt, K_L = 2)")


def test_claim_nachmessung():
    rows = R.load()["nach"]
    series = {}
    for r in rows:
        series.setdefault((r["depot"], r["layout"]), []).append(r)
    assert len(series) == 6 and {r["m"] for r in rows} == {15} and len(rows) == 30
    for key, v in series.items():
        assert sorted(r["beta"] for r in v) == [0.05, 0.1, 0.4, 0.8, 0.9], key            # die Nachmessung hat keinen Punkt bei 0,6
        assert max(v, key=lambda r: r["dD"][0])["beta"] == 0.4, key                          # höchster unter diesen fünf Punkten
        assert min(r["dD"][0] for r in v) > 4.0
    assert R.nach_instanzen() == 450
    # Die Hauptmessreihe zeigt bei β = 0,6 höhere Werte als bei 0,4 (n = 20, K_L = 2, alle drei Lagen), also liegt das Maximum zwischen 0,4 und 0,8.
    mc = {(c["n"], c["K_L"], c["layout"], c["beta"]): c["dD"] for c in R.main_cells()}
    for layout in ("gemischt", "ueberlappend", "getrennt"):
        assert mc[(20, 2, layout, 0.6)] > mc[(20, 2, layout, 0.4)], layout
    pmeans = R.main_param_means()["beta"]["means"]
    assert pmeans[0.6] > pmeans[0.4] > pmeans[0.2]
    low = R.nach_min()
    assert (low["depot"], low["layout"], low["beta"], n(low["dD"][0])) == ("mitte", "getrennt", 0.9, "4,9")
    has("Unter den fünf gemessenen Punkten (β = 0,05; 0,1; 0,4; 0,8; 0,9) ist 0,4 in allen 6 Reihen (Depot Rand und Mitte, drei Lagen) der höchste",
        "die Hauptmessreihe zeigt bei β = 0,6 noch höhere Werte, das Maximum liegt also zwischen 0,4 und 0,8", "kleinster Zellenmittelwert 4,9 % (Depot Mitte, getrennt, β = 0,9)",
        "30 Zellen mit je 15 Instanzen, 450 Instanzen", "nicht vorab festgelegt")


def test_claim_ungleiche_mengen():
    zs = R.load()["zusatz"]
    k, g = zs["klein"], zs["gross"]
    assert (len(k["cells"]), len(g["cells"]), {c["m"] for c in k["cells"] + g["cells"]}) == (12, 12, {25})
    assert (n(k["overall"]["dD_S1"]), n(k["overall"]["dD_A"]), n(k["overall"]["dD_AM"])) == ("5,6", "21,8", "3,8")
    assert (n(g["overall"]["dD_S1"]), n(g["overall"]["dD_A"]), n(g["overall"]["dD_AM"]), n(g["overall"]["dD_S1"] / g["overall"]["dD_A"], 2)) == ("14,9", "24,8", "1,8", "0,60")
    assert (sum(1 for c in g["cells"] if c["R"] >= 0.8), sum(1 for c in g["cells"] if c["R"] <= 0.5)) == (3, 6)

    def diff(z):
        return sum(c["dD_A"][0] - c["dD_A_rand_haupt"] for c in z["cells"]) / len(z["cells"])
    assert (n(diff(k), 1, True), n(diff(g), 2, True)) == ("-3,1", "-0,05")
    zk, zg = R.zusatz_vergleich("klein"), R.zusatz_vergleich("gross")
    assert (n(zg["s1_haupt"]), n(zg["a_haupt"]), n(zg["r_haupt"], 2), n(zg["r"], 2)) == ("9,9", "24,9", "0,40", "0,60")
    assert (n(zg["d_s1"], 1, True), n(zg["d_a"], 2, True), n(zk["d_s1"], 1, True), n(zk["d_a"], 1, True)) == ("+5,0", "-0,05", "-4,3", "-3,1")
    has("S1 5,6 % von 21,8 %", "A gegen M 3,8 %", "S1 14,9 % von 24,8 %, R = 0,60 (R ≥ 0,8 in 3 von 12 Zellen, R ≤ 0,5 in 6), A gegen M 1,8 %",
        "(AP 0, Depot am Rand: S1 9,9 %, A 24,9 %, R 0,40)", "heben große Abholmengen vor allem den S1-Anteil (R 0,40 auf 0,60, S1 +5,0 Pp, A 0,0 Pp (−0,05))", "kleine senken S1 und A ähnlich stark (S1 −4,3, A −3,1 Pp)")


def test_formulierungen_nach_der_aussagenpruefung():
    """Wortlaut, den der unabhängige Aussagenprüfer verlangt hat (Gültigkeit, Maßstab, Deutung): bleibt in der README stehen."""
    has("Abholkunden fahren in S nie auf einer Liefertour mit, sondern nur in reinen Abholtouren; mehrere Abholkunden je Abholtour möglich",
        "**höchstens einen** Abholkunden", "widerlegt für β = 0,05 bis 0,9, n = 20, K_L = 2", "bei β = 0 und β = 1 gibt es nichts zu mischen",
        "holt im Mittel rund ein Drittel der A-Ersparnis (eher untere Grenze)", "Das gilt streng nur für S1",
        "vermutlich in einer Nachbarschaft hängen (Deutung aus Funktionstests und diesen Zählungen, nicht gesondert geprüft)", "bei n = 40 und 6 s (12 Instanzen)",
        "Bei n = 8 trifft die Suche (150 Iterationen) in der Restmessung in 24 von 24 Instanzen das Optimum", "bei n = 20 und 40 ist die Güte für S1 und M unbekannt",
        "die absolute Ersparnis wachsen", "mindestens 90 % der Fälle (Testschwelle)", "die zum Teil aus der eigenen Suche stammt")
    assert "jeder Abholkunde braucht eine eigene Rundtour" not in README and "genau **einen**" not in README and "über der Schranke" not in README


def test_claim_zustaende():
    assert R.level_counts("rand") == {"wenig": 0, "deutlich": 20, "sehr": 16} and R.level_counts("mitte") == {"wenig": 3, "deutlich": 28, "sehr": 5}
    has("Depot am Rand 0 / 20 / 16 von 36 Zellen, Depot in der Mitte 3 / 28 / 5")
    cell6 = R.cells("rand")[6]
    mc6 = next(c for c in R.main_cells() if c["ci"] == 6)
    assert (n(mc6["minD"]), n(mc6["maxD"])) == ("18,5", "34,8") and cell6["ci"] == 6
    has("Zelle 6: Einzelinstanzen von 18,5 bis 34,8 %")


def test_claim_zeiten():
    tm = {(t["n"], t["iters"]): t for t in R.load()["timing"]}
    def span(key):
        vals = [tm[key][s]["mean"] for s in ("S", "S1", "A", "M")]
        return n(min(vals), 2), n(max(vals), 2)
    assert span((20, 300)) == ("0,15", "0,17") and span((20, 1000)) == ("0,49", "0,56") and span((40, 300)) == ("0,41", "0,47") and span((40, 1000)) == ("1,36", "1,51")
    has("n = 20: 0,15 bis 0,17 s bei 300, 0,49 bis 0,56 s bei 1 000 Iterationen; n = 40: 0,41 bis 0,47 s und 1,36 bis 1,51 s")


def test_claim_neu_rechnen_als_band():
    """Die Kette der App rechnet die Referenzinstanzen der Messreihe neu: Band von 1 % je Stufe (Plattformunterschiede der letzten Bits der Entfernungen)."""
    for ref in R.load()["referenz"]:
        inst = M.make_instance(ref["n"], ref["beta"], ref["layout"], ref["K_L"], ref["seed"], depot=M.DEPOTS[ref["grid"]])
        ch = SR.chain(inst, ref["iters"], ref["seed"])
        for stage in C.STAGE_KEYS:
            got = M.total_cost(inst, ch[stage])
            assert got == pytest.approx(ref["cost"][stage], rel=0.01), (ref["grid"], stage, got, ref["cost"][stage])
            assert M.verify_mode(inst, ch[stage], stage) == []


def test_readme_nennt_keine_ungeprueften_umgebungsaussagen_und_hat_alle_pflichtabschnitte():
    for wort in ("läuft lokal", "Saatwert", " trägt ", " tragen "):
        assert wort not in README, wort
    for heading in ("## Warum dieses Problem", "## Modell", "## Methodik", "## Befunde (gemessen, keine Behauptungen)", "## Befunde und Korrekturen gegenüber dem Plan", "## Ehrliche Grenzen", "## Tests",
                    "## Dateistruktur", "## Bewusst nicht umgesetzt", "## Verwandte Demos mit demselben mathematischen Modell", "## Lokal ausführen"):
        assert heading in README, heading
    assert "Zufalls-Seed" in README


def test_jeder_dateiname_der_dateistruktur_existiert():
    root = Path(__file__).resolve().parent.parent
    for name in re.findall(r"^\| `([^`]+)` \|", README.split("## Dateistruktur")[1].split("## Bewusst")[0], re.M):
        for part in name.split(", "):
            part = part.strip("` ")
            if part.endswith("/"):
                assert (root / part).is_dir(), part
            else:
                assert (root / part).exists(), part
