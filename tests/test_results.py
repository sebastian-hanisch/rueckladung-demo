"""Ergebnisdatei data/rkl_results.json: Aufbau, innere Konsistenz, Zellen-Zuordnung, Zustände und Zählungen (Ampel-Regeln der Restmessung AP 0)."""

import json
from pathlib import Path

import pytest

import rkl_constants as C
import rkl_results as R

DATA = Path(__file__).resolve().parent.parent / "data" / "rkl_results.json"


def test_datei_ist_klein_genug_und_hat_72_zellen_mit_je_25_instanzen():
    assert DATA.stat().st_size < 150_000
    cs = R.cells()
    assert len(cs) == 72 and {c["m"] for c in cs} == {25}
    assert len(R.cells("rand")) == 36 and len(R.cells("mitte")) == 36
    assert len(R.main_cells()) == 36 and {c["m"] for c in R.main_cells()} == {25}


def test_jede_gemessene_kombination_kommt_genau_einmal_vor():
    keys = [(c["n"], c["beta"], c["layout"], c["K_L"], c["depot"]) for c in R.cells()]
    assert len(set(keys)) == 72
    want = {(n, b, la, k, d) for n in C.N_OPTIONS for b in C.BETA_OPTIONS for la in C.LAYOUT_OPTIONS for k in C.K_OPTIONS for d in C.DEPOT_OPTIONS}
    assert set(keys) == want


def test_gesamtmittel_sind_das_mittel_der_zellmittel():
    for depot in C.DEPOT_OPTIONS:
        cs = R.cells(depot)
        o = R.stage_means(depot)
        assert o["m"] == 900
        for key, ckey in (("dD_S1", "dD_S1"), ("dD_A", "dD_A"), ("dD_M", "dD_M"), ("dD_AM", "dD_AM")):
            assert o[key] == pytest.approx(sum(c[ckey][0] for c in cs) / len(cs), abs=1e-9)


def test_zellwerte_sind_in_sich_stimmig():
    for c in R.cells():
        assert c["dD_S1"][0] >= -1e-9                                        # S ⊂ S1 ⊂ A ⊂ M: die Ersparnisse wachsen mit der Stufe
        assert c["dD_A"][0] >= c["dD_S1"][0] - 1e-9
        assert c["dD_M"][0] >= c["dD_A"][0] - 1e-9
        assert c["dD_AM"][0] >= -1e-9
        assert c["touren"]["S"] >= c["touren"]["A"] - 1e-9                    # mit Rückladung nie mehr Touren als getrennt (Mittel)
        assert c["R"] == pytest.approx(c["dD_S1"][0] / c["dD_A"][0])
        for s in C.STAGE_KEYS:
            assert 0 <= c["leer"][s] <= 100 and 0 <= c["last"][s] <= 100


def test_hauptraster_a_billiger_als_s_in_allen_900_instanzen():
    assert sum(c["less"] for c in R.main_cells()) == 900 and sum(c["equal"] for c in R.main_cells()) == 0


def test_nearest_cell_selbsttest_der_zuordnung():
    for c in R.cells():
        got, dist, exact = R.nearest_cell(c["n"], c["beta"], c["layout"], c["K_L"], c["depot"])
        assert got is c or got == c
        assert dist == 0 and exact
    got, dist, exact = R.nearest_cell(20, 0.3, "gemischt", 2, "rand")   # zwischen zwei Stufen: die kleinere
    assert got["beta"] == 0.2 and not exact
    got, dist, exact = R.nearest_cell(20, 0.9, "getrennt", 2, "mitte")  # außerhalb des Rasters: nächste Stufe
    assert got["beta"] == 0.6 and not exact


def test_zustaende_an_den_schwellen():
    assert R.level(9.99) == "wenig" and R.level(10.0) == "deutlich" and R.level(24.99) == "deutlich" and R.level(25.0) == "sehr"


def test_zustandszaehlung_und_urteile():
    assert R.level_counts("rand") == {"wenig": 0, "deutlich": 20, "sehr": 16}
    assert R.level_counts("mitte") == {"wenig": 3, "deutlich": 28, "sehr": 5}
    assert R.urteil_s1("rand") == "S1 deutlich zurück" and R.urteil_s1("mitte") == "S1 deutlich zurück"
    assert R.urteil_m("rand") == "M bringt etwas" and R.urteil_m("mitte") == "M bringt etwas"
    rc = R.r_counts("rand")
    assert (rc["deutlich_zurueck"], rc["fast_alles"], rc["zellen"]) == (29, 0, 36)
    assert R.r_counts("mitte")["deutlich_zurueck"] == 28 and R.r_counts("mitte")["fast_alles"] == 1


def test_urteile_folgen_den_schwellen_an_kuenstlichen_zaehlungen(monkeypatch):
    monkeypatch.setattr(R, "r_counts", lambda depot: {"deutlich_zurueck": 5, "fast_alles": 24, "zellen": 36, "median": 0.9, "max": 1.0})
    assert R.urteil_s1() == "S1 holt fast alles"
    monkeypatch.setattr(R, "r_counts", lambda depot: {"deutlich_zurueck": 23, "fast_alles": 0, "zellen": 36, "median": 0.4, "max": 0.7})
    assert R.urteil_s1() == "gemischt, regimeabhängig"
    monkeypatch.setattr(R, "m_counts", lambda depot: {"ab_2": 11, "unter_1": 24, "zellen": 36})
    assert R.urteil_m() == "M bringt fast nichts"
    monkeypatch.setattr(R, "m_counts", lambda depot: {"ab_2": 11, "unter_1": 23, "zellen": 36})
    assert R.urteil_m() == "gemischt"


def test_depot_vergleich_und_kleinste_zelle():
    d = R.depot_diff()
    assert d["zellen"] == 36 and d["mitte_hoeher"] == 0 and 6.4 < d["mittel"] < 6.6
    mc = R.min_cell("mitte")
    assert (mc["ci"], mc["n"], mc["beta"], mc["layout"], mc["K_L"]) == (20, 40, 0.2, "getrennt", 2)
    assert R.num(mc["dD_A"][0]) == "6,9"
    assert R.num(R.nach_min()["dD"][0]) == "4,9"


def test_parameter_spreizung_der_hauptmessreihe_gleich_gespeicherter_spreizung():
    pm = R.main_param_means()
    stored = R.load()["main"]["P"]
    for key in ("beta", "layout", "K_L", "n"):
        assert pm[key]["spread"] == pytest.approx(stored[key], abs=1e-9)
    assert max(pm, key=lambda k: pm[k]["spread"]) == "beta"


def test_loeser_und_zeitzahlen_sind_geparst():
    lo = R.load()["loeser"]
    assert set(lo) == {"n20_A", "n20_S", "n40_A", "n40_S", "exakt_n20"}
    assert lo["exakt_n20"]["A"]["proven"] == 258 and lo["exakt_n20"]["S"]["proven"] == 153
    tm = R.load()["timing"]
    assert [(t["n"], t["iters"]) for t in tm] == [(20, 300), (20, 1000), (40, 300), (40, 1000)]
    assert all(set(t) >= {"S", "S1", "A", "M"} for t in tm)


def test_json_ist_gueltig_und_ohne_nan():
    text = DATA.read_text(encoding="utf-8")
    assert "NaN" not in text and "Infinity" not in text
    json.loads(text)


def test_formatierung_mit_dezimalkomma():
    assert R.num(3.14159) == "3,1" and R.num(3.14159, 2) == "3,14" and R.num(2.0, 1, True) == "+2,0" and R.num(-2.0, 1, True) == "-2,0"
    assert R.pm([27.2167, 0.8669]) == "27,2 ± 0,9"
