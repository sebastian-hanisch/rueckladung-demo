"""End-to-end Smoke-Test via Streamlits offiziellem AppTest-Framework: lädt app.py mit den Standardeinstellungen, klickt jedes Preset, fährt jeden Regler
an seine Stufen und prüft, dass kein Python-Fehler auftritt (insbesondere `StreamlitDuplicateElementId` bei Charts mit gleichem Inhalt).

OR-Tools und CP-SAT laufen in den Tests mit kurzen Zeitlimits (die Konstanten werden vor dem Lauf umgesetzt); keine Zeit-Assertions."""

import os
import re

import pytest
from streamlit.testing.v1 import AppTest

import rkl_constants as C
import rkl_results as R

APP_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")
TIMEOUT = int(os.environ.get("APPTEST_TIMEOUT", "300"))  # unter Last (parallele Läufe) reichen 180 s nicht immer; Umgebungsvariable zum Anpassen


@pytest.fixture(autouse=True)
def kurze_loeser(monkeypatch):
    monkeypatch.setattr(C, "ORTOOLS_SECONDS", {20: 1, 40: 1})
    monkeypatch.setattr(C, "EXACT_SECONDS", 4)


def _fresh_app() -> AppTest:
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=TIMEOUT)
    assert not at.exception, [str(e) for e in at.exception]
    return at


def _texts(at):
    return [w.value for w in list(at.info) + list(at.success) + list(at.warning)]


def test_app_loads_without_exception_and_shows_the_three_expanders():
    at = _fresh_app()
    labels = [e.label for e in at.expander]
    assert "🔧 Wie wir das erreichen – vollständiger Methodenvergleich" in labels
    assert "Wie funktioniert diese Demo?" in labels and "📐 Mathematische Formulierung" in labels
    assert any("Rückladung lohnt" in t for t in _texts(at))
    assert [m.label for m in at.metric] == ["Distanz mit Rückladung (A)", "Touren: getrennt → mit Rückladung", "Leerkilometer-Anteil: S → A", "Anteil der A-Ersparnis, den S1 holt"]


@pytest.mark.parametrize("name", list(C.PRESETS))
def test_jedes_preset_laeuft_und_zeigt_die_zelle_des_presets(name):
    at = _fresh_app()
    at.sidebar.button(key=f"preset_{name}").click().run(timeout=TIMEOUT)
    assert not at.exception, [str(e) for e in at.exception]
    p = C.PRESETS[name]
    cell = R.nearest_cell(p["n"], p["beta"], p["layout"], p["k"], p["depot"])[0]
    first = next(t for t in _texts(at) if "Rückladung lohnt" in t)
    assert f"Zelle {cell['ci']}," in first and R.pm(cell["dD_A"]) in first


@pytest.mark.parametrize("key", ["n_slider", "beta_slider", "k_slider", "ils_slider"])
def test_jede_stufe_der_diskreten_regler_laeuft(key):
    at = _fresh_app()
    stufen = {"n_slider": C.N_OPTIONS, "beta_slider": C.BETA_OPTIONS, "k_slider": C.K_OPTIONS, "ils_slider": C.ILS_OPTIONS}[key]
    for value in stufen:
        if key == "ils_slider" and value == 1000:
            continue   # 1 000 Iterationen dauern in der Testumgebung zu lange; die Stufe selbst ist in test_layout und per Permalink geprüft
        if key == "n_slider" and value == 40:
            at.sidebar.select_slider(key="ils_slider").set_value(300)
        widget = at.sidebar.select_slider(key=key)
        widget.set_value(value).run(timeout=TIMEOUT)
        assert not at.exception, (key, value, [str(e) for e in at.exception])


@pytest.mark.parametrize("key,options", [("layout_radio", C.LAYOUT_OPTIONS), ("depot_radio", C.DEPOT_OPTIONS)])
def test_jede_option_der_radios_laeuft(key, options):
    at = _fresh_app()
    for option in options:
        at.sidebar.radio(key=key).set_value(option).run(timeout=TIMEOUT)
        assert not at.exception, (key, option, [str(e) for e in at.exception])
        assert at.sidebar.radio(key=key).value == option


def test_zufalls_seed_an_den_raendern_und_der_zufalls_knopf():
    at = _fresh_app()
    for value in (0, C.SEED_MAX):
        at.sidebar.number_input(key="seed_input").set_value(value).run(timeout=TIMEOUT)
        assert not at.exception, (value, [str(e) for e in at.exception])
    at.sidebar.button[-1].click().run(timeout=TIMEOUT)   # 🎲 Neue Instanz generieren (letztes Element der Seitenleiste)
    assert not at.exception, [str(e) for e in at.exception]
    assert 0 <= at.sidebar.number_input(key="seed_input").value <= C.SEED_MAX


def test_die_drei_meldungszustaende_kommen_vor():
    """'lohnt wenig' nur mit dem Depot in der Mitte (Zelle 20), 'lohnt deutlich' (n = 20, 20 % Abholkunden: Zelle 0) und 'lohnt sehr' (Standard)."""
    at = _fresh_app()
    assert any("lohnt sehr" in w.value for w in at.success)
    at.sidebar.select_slider(key="beta_slider").set_value(0.2).run(timeout=TIMEOUT)
    assert any("lohnt deutlich" in w.value for w in at.info) and not at.success
    at.sidebar.button(key="preset_Wenig Rückladung, Depot Mitte").click().run(timeout=TIMEOUT)
    assert not at.exception, [str(e) for e in at.exception]
    assert any("lohnt hier wenig" in w.value for w in at.warning)


def test_erste_meldung_nennt_depot_und_den_strengen_massstab():
    at = _fresh_app()
    first = next(t for t in _texts(at) if "Rückladung lohnt" in t)
    assert "Depot am Gebietsrand" in first and "strenger Maßstab" in first


def test_ortools_und_exakt_knoepfe_funktionieren_und_werden_je_einstellung_gespeichert():
    pytest.importorskip("ortools")
    at = _fresh_app()
    at.button(key="ortools_start").click().run(timeout=TIMEOUT)
    assert not at.exception, [str(e) for e in at.exception]
    assert any("OR-Tools (Standard)" in i.value for i in at.info)
    at.button(key="exact_A_start").click().run(timeout=TIMEOUT)
    assert not at.exception, [str(e) for e in at.exception]
    assert any("Optimum für A" in w.value for w in list(at.success) + list(at.warning))
    at.button(key="exact_S_start").click().run(timeout=TIMEOUT)
    assert not at.exception, [str(e) for e in at.exception]
    assert any("Optimum für S" in w.value for w in list(at.success) + list(at.warning))
    at.sidebar.radio(key="layout_radio").set_value("getrennt").run(timeout=TIMEOUT)   # andere Einstellung: kein altes Ergebnis mehr
    assert not at.exception
    assert not any("OR-Tools (Standard)" in i.value for i in at.info)
    assert not any("Optimum für" in w.value for w in list(at.success) + list(at.warning))


def test_exakt_wird_bei_40_kunden_nicht_angeboten():
    at = _fresh_app()
    at.sidebar.select_slider(key="n_slider").set_value(40).run(timeout=TIMEOUT)
    assert not at.exception, [str(e) for e in at.exception]
    assert not [b for b in at.button if b.key and b.key.startswith("exact_")]
    assert any("nur für n = 20" in i.value for i in at.info)


def test_jede_ansicht_und_das_pdf_stuerzen_nicht_ab():
    at = _fresh_app()
    options = list(at.selectbox(key="view_select").options)
    assert len(options) == 4
    for option in options:
        at.selectbox(key="view_select").set_value(option).run(timeout=TIMEOUT)
        assert not at.exception, (option, [str(e) for e in at.exception])


def test_permalink_rastet_auf_stufen_und_verwirft_unbekanntes():
    at = AppTest.from_file(APP_PATH)
    at.query_params["beta"] = "0.55"
    at.query_params["lage"] = "oben"
    at.query_params["n"] = "33"
    at.query_params["ils"] = "5"
    at.run(timeout=TIMEOUT)
    assert not at.exception, [str(e) for e in at.exception]
    assert at.sidebar.select_slider(key="beta_slider").value == 0.6 and at.sidebar.radio(key="layout_radio").value == C.DEFAULT_LAYOUT
    assert at.sidebar.select_slider(key="n_slider").value == 40 and at.sidebar.select_slider(key="ils_slider").value == 300


def test_keine_toten_dateilinks_und_keine_umgebungsaussagen_in_der_app():
    text = open(APP_PATH, encoding="utf-8").read()
    assert not re.search(r"\]\([A-Za-z0-9_./-]+\.(py|json|md|txt)\)", text)
    for wort in ("läuft lokal", "Saatwert", " trägt ", " tragen "):
        assert wort not in text, wort
