"""Verdikte (reine Funktionen in rkl_evaluation.py) an handgesetzten Werten: Schwellen, jede Zahl im Text, Nenner-0-Zweige."""

import copy

import pytest

import rkl_constants as C
import rkl_evaluation as E
import rkl_results as R


def _analysis(dists, vehicles=(4, 3, 3, 2), empties=(100, 60, 30, 0)):
    steps = tuple(E.Step(k, C.STAGE_LABELS[k], ((1,),), d, v, e, 0.3, 0.1) for k, d, v, e in zip(C.STAGE_KEYS, dists, vehicles, empties))
    return E.Analysis(None, steps)


def _cell(mean_a, depot="rand"):
    c = copy.deepcopy(next(c for c in R.cells(depot) if c["ci"] == 6))
    c["dD_A"] = [mean_a, 0.5]
    return c


def test_meldung_in_drei_zustaenden_an_den_schwellen():
    # die Zelle liefert Zahlen für den Text; für die Zustände zählt nur das Zellmittel
    for mean_a, kind, head in ((9.9, "warning", "lohnt hier wenig"), (10.0, "info", "lohnt deutlich"), (24.9, "info", "lohnt deutlich"), (25.0, "success", "lohnt sehr")):
        got_kind, text = E.verdict_level(_cell(mean_a))
        assert got_kind == kind and head in text, (mean_a, got_kind)


def test_erste_meldung_nennt_depotlage_massstab_s1_und_zahlen():
    cell = next(c for c in R.cells("rand") if c["ci"] == 6)
    kind, text = E.verdict_level(cell)
    other = R.other_depot(cell)
    assert "am Gebietsrand (50, 0)" in text and "in der Mitte" in text
    assert "strenger Maßstab" in text
    assert R.pm(cell["dD_A"]) in text and R.num(other["dD_A"][0]) in text
    assert R.num(cell["dD_S1"][0]) in text and R.num(cell["touren"]["S"]) in text and R.num(cell["touren"]["A"]) in text
    assert R.num(cell["leer"]["S"]) in text and R.num(cell["leer"]["A"]) in text
    assert "Zelle 6" in text and "25 Instanzen" in text and "10 %" in text and "25 %" in text
    cell_m = next(c for c in R.cells("mitte") if c["ci"] == 6)
    _, text_m = E.verdict_level(cell_m)
    assert "in der Mitte des Gebiets (50, 50)" in text_m and "am Rand" in text_m


def test_depot_text_und_zellentext():
    assert E.depot_text("rand") == "am Gebietsrand (50, 0)" and E.depot_text("mitte") == "in der Mitte des Gebiets (50, 50)"
    cell = next(c for c in R.cells("rand") if c["ci"] == 6)
    assert E.cell_text(cell).startswith("Zelle 6, Depot am Gebietsrand")


def test_treppe_live_zahlen_und_nenner_null():
    kind, text = E.verdict_stairs(_analysis((1000, 800, 600, 500)))
    assert kind == "info" and "eine Instanz" in text
    assert "S 100,0" in text and "S1 80,0 (−20,0 % gegen S)" in text and "A 60,0 (−40,0 %)" in text and "M 50,0 (−50,0 %)" in text
    assert "Touren 4 → 3 → 3 → 2" in text and "Leerkilometer-Anteil 10,0 → 7,5 → 5,0 → 0,0 %" in text
    _, zero = E.verdict_stairs(_analysis((0, 0, 0, 0), empties=(0, 0, 0, 0)))
    assert "±0,0 %" in zero and "−" not in zero.replace("→", "")


def test_s1_verdikt_nennt_anteil_zaehlung_und_urteil():
    cell = next(c for c in R.cells("rand") if c["ci"] == 1)
    kind, text = E.verdict_s1(cell, "rand")
    assert kind == "info" and "S1 deutlich zurück" in text and f"R = {R.num(cell['R'], 2)}" in text
    assert "7,4 % von 23,9 %" in text and "29 Zellen" in text and "0 bei mindestens 0,8" in text and "Median 0,26" in text
    cell0 = copy.deepcopy(cell)
    cell0["R"] = None
    assert "nicht bestimmbar" in E.verdict_s1(cell0, "rand")[1]
    _, text_m = E.verdict_s1(cell, "mitte")
    assert "in der Mitte des Gebiets" in text_m and "6,3 % von 17,4 %" in text_m and "28 Zellen" in text_m and "1 bei mindestens 0,8" in text_m


def test_m_verdikt():
    cell = next(c for c in R.cells("rand") if c["ci"] == 24)
    _, text = E.verdict_m(cell, "rand")
    assert "4,2 %" in text and R.pm(cell["dD_AM"]) in text and "19 Zellen mindestens 2 %" in text and "14 Zellen unter 1 %" in text and "M bringt etwas" in text and "19,3" in text
    assert "M fast immer gleich A (in 282 von 300 Instanzen gleich, Mittel von A gegen M 0,03 %)" in text and "Bei getrennten Zonen ist M gleich A," not in text


def test_hebel_und_depot_verdikt():
    _, hebel = E.verdict_hebel()
    assert "18,2 / 25,6 / 27,9 %" in hebel and "9,7 Prozentpunkte" in hebel and "14,1" in hebel and "33,5" in hebel
    for pair in ("4,8 Pp", "3,3 Pp", "3,0 Pp"):
        assert pair in hebel
    _, dep = E.verdict_depot()
    assert "23,9 % auf 17,4 %" in dep and "6,5 Prozentpunkte" in dep and "0 von 36" in dep and "4,2 → 5,5 %" in dep


def test_ortools_verdikt_rechnet_die_luecke_zur_eigenen_suche():
    _, text = E.verdict_ortools(None, 1000, 800, {"S": 1010, "A": 808}, {"S": 1000, "A": 816})
    assert "S +1,00 %" in text and "A +1,00 %" in text      # Standard: 10 / 1000 und 8 / 800
    assert "S +0,00 %" in text and "A +2,00 %" in text      # SAVINGS
    _, zero = E.verdict_ortools(None, 0, 0, {"S": 0, "A": 0}, {"S": 0, "A": 0})
    assert "+0,00 %" in zero


def test_exact_verdikt_bewiesen_nicht_bewiesen_und_ohne_loesung():
    kind, text = E.verdict_exact("A", "OPTIMAL", 8000.0, 8000.0, 8040)
    assert kind == "success" and "Optimum für A bewiesen: 800,0" in text and "+0,50 %" in text and "258 von 450" in text
    kind, text = E.verdict_exact("S", "FEASIBLE", 9000.0, 6000.0, 9000)
    assert kind == "warning" and "nicht bewiesen" in text and "Optimum für S" in text and "900,0" in text and "600,0" in text and "34,39 %" in text and "55,90 %" in text
    assert "unter der besten Lösung (bezogen auf die beste Lösung" in text and "über der Schranke" not in text
    kind, text = E.verdict_exact("A", "UNKNOWN", None, None, 8000)
    assert kind == "warning" and "keine Lösung" in text
    _, zero = E.verdict_exact("A", "OPTIMAL", 0.0, 0.0, 0)
    assert "+0,00 %" in zero


def test_exact_nicht_angeboten_nennt_n_und_grund():
    text = E.exact_unavailable_text(40)
    assert "n = 20" in text and "n = 40" in text and "nicht gemessen" in text and "40 s" in text
    assert "erwartet" in text and "nicht nachgerechnet" in text


def test_zustaende_sind_in_den_konstanten_gesetzt_nicht_hergeleitet():
    assert (C.LEVEL_WENIG, C.LEVEL_SEHR, C.R_DEUTLICH_ZURUECK, C.R_FAST_ALLES) == (10.0, 25.0, 0.5, 0.8)


@pytest.mark.parametrize("kind", ["warning", "info", "success"])
def test_alle_drei_zustaende_kommen_in_den_zellen_vor_oder_sind_synthetisch_pruefbar(kind):
    seen = {E.LEVEL_KIND[R.level(c["dD_A"][0])] for c in R.cells()}
    assert kind in seen   # Zustand wird mit echten Zellen erreicht (warning nur mit dem Depot in der Mitte)
