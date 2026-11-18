"""Presets: Vollständigkeit, gültige Werte, Standard-Preset = Standardeinstellungen, gemessene Zelle je Preset, Geschichte auf der angezeigten Instanz."""

import pytest

import rkl_constants as C
import rkl_evaluation as ev
import rkl_presets as P
import rkl_results as R
import rkl_stories as S


def _settings(name):
    p = C.PRESETS[name]
    return ev.Settings(p["n"], p["beta"], p["layout"], p["depot"], p["k"], p["ils"], p["seed"])


def test_every_preset_has_help_story_and_all_keys():
    assert set(C.PRESETS) == set(C.PRESET_HELP) == set(S.STORIES)
    for name, preset in C.PRESETS.items():
        assert set(preset) == set(P.PRESET_KEYS), name
        assert C.PRESET_HELP[name]


def test_preset_values_are_stages_of_the_sliders():
    for name, p in C.PRESETS.items():
        assert p["n"] in C.N_OPTIONS and p["beta"] in C.BETA_OPTIONS and p["layout"] in C.LAYOUT_OPTIONS and p["depot"] in C.DEPOT_OPTIONS and p["k"] in C.K_OPTIONS and p["ils"] in C.ILS_OPTIONS, name
        assert 0 <= p["seed"] <= C.SEED_MAX


def test_preset_seeds_liegen_ausserhalb_aller_messbereiche():
    for p in C.PRESETS.values():
        assert p["seed"] >= 500000          # Messreihen: 1000-1011, 100000-103599, 200000+, 300000+
    assert C.DEFAULT_SEED >= 500000


def test_default_preset_equals_the_default_settings():
    assert _settings("Standard") == ev.Settings()
    assert next(iter(C.PRESETS)) == "Standard"


def test_setting_specs_cover_every_preset_key_and_option_stages_match_constants():
    assert set(P.PRESET_KEYS.values()) == set(P.SETTING_SPECS)
    assert P.options("n_slider") == C.N_OPTIONS and P.options("beta_slider") == C.BETA_OPTIONS and P.options("k_slider") == C.K_OPTIONS
    assert P.options("layout_radio") == C.LAYOUT_OPTIONS and P.options("depot_radio") == C.DEPOT_OPTIONS and P.options("ils_slider") == C.ILS_OPTIONS


def test_clamp_rastet_auf_die_naechste_stufe_und_verwirft_unbekanntes():
    spec = P.SETTING_SPECS
    assert P.clamp_value(spec["beta_slider"], 0.35) in (0.2, 0.4) and P.clamp_value(spec["beta_slider"], 0.9) == 0.6
    assert P.clamp_value(spec["n_slider"], 33) == 40 and P.clamp_value(spec["n_slider"], 29) == 20
    assert P.clamp_value(spec["layout_radio"], "oben") is None and P.clamp_value(spec["layout_radio"], "getrennt") == "getrennt"
    assert P.clamp_value(spec["seed_input"], -5) == 0 and P.clamp_value(spec["seed_input"], 10 ** 9) == C.SEED_MAX


@pytest.mark.parametrize("name", list(C.PRESETS))
def test_jedes_preset_liegt_auf_einer_gemessenen_zelle(name):
    p = C.PRESETS[name]
    cell, dist, exact = R.nearest_cell(p["n"], p["beta"], p["layout"], p["k"], p["depot"])
    assert dist == 0 and exact and cell["depot"] == p["depot"]


def test_zellen_der_presets_stimmen_mit_der_geschichte_ueberein():
    cells = {name: R.nearest_cell(p["n"], p["beta"], p["layout"], p["k"], p["depot"])[0] for name, p in C.PRESETS.items()}
    assert (cells["Standard"]["ci"], cells["Standard"]["depot"]) == (6, "rand")
    maxcell = R.max_cell("rand")
    assert cells["Viel Rückladung, knapper Laderaum"]["ci"] == maxcell["ci"] == 13          # größte Ersparnis des Hauptrasters (eigene Suche)
    assert cells["Wenig Rückladung, getrennte Zonen"]["ci"] == R.min_cell("rand")["ci"] == 21   # kleinste Ersparnis, Depot am Rand
    assert cells["Wenig Rückladung, Depot Mitte"]["ci"] == R.min_cell("mitte")["ci"] == 20       # kleinste überhaupt
    assert cells["Große Leerkilometer-Wirkung"]["ci"] == R.max_cell("rand", "dE_A")["ci"] == 31                      # größter Rückgang der Leerkilometer
    assert R.level(cells["Wenig Rückladung, Depot Mitte"]["dD_A"][0]) == "wenig"
    assert R.level(cells["Standard"]["dD_A"][0]) == "sehr"


@pytest.mark.parametrize("name", list(C.PRESETS))
def test_die_instanz_jedes_presets_zeigt_ihre_geschichte(name):
    """Das Kriterium prüft die angezeigte Instanz (grob); die Aussage der Demo steht in der Messreihe. Live mit dem Rechenbudget des Presets."""
    a = ev.analyse(_settings(name))
    assert S.STORIES[name](a), name


def test_geschichte_kippt_an_ihren_schwellen_mit_kuenstlichen_werten():
    def analysis(dists, vehicles=(4, 3, 3, 2), empties=(100, 60, 30, 0)):
        steps = tuple(ev.Step(k, k, ((1,),), d, v, e, 0.3, 0.1) for k, d, v, e in zip(("S", "S1", "A", "M"), dists, vehicles, empties))
        return ev.Analysis(None, steps)

    assert S.story_standard(analysis((1000, 900, 850, 800))) and not S.story_standard(analysis((1000, 900, 860, 800)))       # A-Ersparnis 15 %
    assert not S.story_standard(analysis((1000, 780, 850, 800)))                                                              # S1 holt mehr als 0,8 von A (22 von 15)
    assert S.story_viel(analysis((1000, 900, 750, 700))) and not S.story_viel(analysis((1000, 900, 751, 700)))
    assert S.story_wenig_getrennt(analysis((1000, 995, 860, 860))) and not S.story_wenig_getrennt(analysis((1000, 995, 860, 850)))   # M muss gleich A sein
    assert S.story_wenig_getrennt(analysis((1000, 995, 920, 920))) and not S.story_wenig_getrennt(analysis((1000, 995, 930, 930)))   # untere Grenze 8 %
    assert S.story_wenig_getrennt(analysis((1000, 995, 780, 780))) and not S.story_wenig_getrennt(analysis((1000, 995, 770, 770)))   # obere Grenze 22 %
    assert S.story_leerkm(analysis((1000, 900, 790, 700), empties=(100, 60, 39, 0))) and not S.story_leerkm(analysis((1000, 900, 790, 700), empties=(100, 60, 40, 0)))   # halber Anteil
    assert not S.story_leerkm(analysis((1000, 900, 810, 700), empties=(100, 60, 39, 0)))                                         # Ersparnis unter 20 %
    assert S.story_mitte(analysis((1000, 995, 900, 900))) and not S.story_mitte(analysis((1000, 995, 960, 960)))
    assert S.story_wenig_mitte(analysis((1000, 995, 880, 880))) and not S.story_wenig_mitte(analysis((1000, 980, 880, 880)))
