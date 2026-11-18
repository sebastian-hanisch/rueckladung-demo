"""Rückladung: wie viel Leerfahrt verschwindet? - interaktive Fall-Demo
Sebastian Hanisch - Operations Research und Machine Learning

VRP mit Rückladungen (Backhauls): Lieferkunden zuerst, danach Abholkunden auf dem Rückweg. Live auf einer Instanz: die vier Planungsarten S (getrennt),
S1 (ein Abholkunde je Tour), A (VRPB) und M (gemischt) mit der eigenen Suche; OR-Tools und das exakte Verfahren (CP-SAT, n = 20) auf Knopfdruck.
Die Aussagen stützen sich auf die vorgerechnete Messreihe (data/rkl_results.json). Aufbau und Regeln: DEMO-PLAYBOOK.md (§2).

Lauffähig mit: streamlit run app.py
"""

import pandas as pd
import streamlit as st

import rkl_constants as C
import rkl_evaluation as E
import rkl_model as M
import rkl_results as R
import rkl_search as SR
import rkl_solvers as V
import rkl_visualization as VIZ
from rkl_layout import dunkles_design, kopf_css
from rkl_pdf_export import build_pdf
from rkl_presets import (
    bounds,
    init_session_state_defaults,
    load_permalink_settings,
    options,
    randomize_seed,
    sidebar_presets,
    sync_query_params,
)

st.set_page_config(page_title="Rückladung – Sebastian Hanisch", layout="wide")


@st.cache_data(show_spinner=False)
def _analysis(settings):
    return E.analyse(settings)


@st.cache_data(show_spinner=False)
def _ortools(settings):
    """OR-Tools in zwei Einstellungen (Standard, SAVINGS) für S und A auf derselben Instanz."""
    inst = E.make_inst(settings)
    secs = C.ORTOOLS_SECONDS[settings.n]
    out = {}
    for setting in V.SETTINGS:
        out[setting] = {}
        for mode in ("S", "A"):
            routes, _obj = V.solve_ortools(inst, mode, secs, setting)
            if routes is None or M.verify_mode(inst, routes, mode):
                raise RuntimeError(f"OR-Tools ({setting}, {mode}) lieferte keine zulässige Lösung")
            out[setting][mode] = M.total_cost(inst, routes)
    return out


@st.cache_data(show_spinner=False)
def _exact(settings, mode):
    """CP-SAT mit Warmstart aus der eigenen Suche (wie in der Messreihe); liefert Status, Zielwert, Schranke und Rechenzeit."""
    import time
    a = _analysis(settings)
    hint = [list(r) for r in E.step_of(a, mode).routes]
    t0 = time.perf_counter()
    if mode == "S":
        routes, status, bound = V.solve_exact_S(a.inst, C.EXACT_SECONDS, 1, hint=hint)
    else:
        routes, status, bound = V.solve_exact(a.inst, "A", C.EXACT_SECONDS, 1, hint=hint)
    obj = None if routes is None else M.total_cost(a.inst, routes)
    return {"status": status, "obj": obj, "bound": bound, "sec": time.perf_counter() - t0}


def _fmt_beta(value):
    return f"{round(100 * value)} %"


# Fester Kopf: nur der Titel bleibt beim Scrollen oben (Stylesheet in rkl_layout.py).
st.html(kopf_css(dunkles_design()))
with st.container(key="kopf"):
    st.title("↩️ Rückladung: wie viel Leerfahrt verschwindet?")
st.markdown(
    """
Lkw liefern aus und fahren **leer zurück**. Liegen **Abholkunden** (Rückladung, Leergut, Retouren) auf dem Rückweg, befördert dieselbe Fahrt Last in beide Richtungen: erst alle Lieferkunden, danach Abholkunden
(**VRP mit Rückladungen**, Backhauls). Die Demo zeigt live auf **einer Instanz** vier Planungsarten, von der getrennten Planung **S** über **S1** (ein Abholkunde je Tour) und **A** (Rückladung)
bis zur gemischten Variante **M**, und fragt: **wovon hängt die Höhe der Ersparnis ab, und wie viel steckt nur im strengen Vergleichsmaßstab?** Die Aussagen stützen sich auf eine vorgerechnete Messreihe mit 25 Instanzen je Zelle.

Weiter unten: die **Kernfragen** und die Expander **🔧 Wie wir das erreichen – vollständiger Methodenvergleich**, **Wie funktioniert diese Demo?** und **📐 Mathematische Formulierung**.
"""
)

st.caption("🔗 Die Adresszeile oben spiegelt Ihre aktuelle Konfiguration wider – einfach kopieren, um ein Szenario zu teilen.")

load_permalink_settings()
init_session_state_defaults()

with st.sidebar:
    sidebar_presets()  # Schnellstart oben, das aktive Preset ist hervorgehoben
    st.header("⚙️ Einstellungen")
    st.markdown("**Instanz**")
    n = st.select_slider("Kunden", options=options("n_slider"), key="n_slider", help="Wie viele Kunden bedient werden (die gemessenen Größen). Bei 20 Kunden gibt es den exakten Löser.")
    beta = st.select_slider("Anteil Abholkunden", options=options("beta_slider"), key="beta_slider", format_func=_fmt_beta,
                            help="Anteil der Kunden, bei denen etwas abgeholt wird (Rückladung). Der Rest sind Lieferkunden.")
    layout = st.radio("Lage der Zonen", options("layout_radio"), key="layout_radio", format_func=lambda v: C.LAYOUT_LABELS[v],
                      help="Gemischt: alle Kunden durcheinander. Überlappend: Lieferkunden eher links, Abholkunden eher rechts. Getrennt: zwei Zonen.")
    depot = st.radio("Depot", options("depot_radio"), key="depot_radio", format_func=lambda v: C.DEPOT_LABELS[v],
                     help="Die Hauptmessreihe der Vormessung lag mit dem Depot am Rand; mit dem Depot in der Mitte ist die Ersparnis im Mittel kleiner.")
    k = st.select_slider("Knappheit der Lieferlast", options=options("k_slider"), key="k_slider",
                         help="Der Laderaum ist so bemessen, dass die getrennte Planung etwa so viele Lieferfahrten braucht: 2 heißt großzügiger Laderaum, 4 knapper (Kapazität = 1,1 mal Summe der Lieferungen durch diese Zahl).")
    st.markdown("**Rechnen**")
    ils = st.select_slider("Rechenbudget eigene Suche", options=options("ils_slider"), key="ils_slider", format_func=lambda v: C.ILS_LABELS[v],
                           help="Iterationen der eigenen Suche. Die vorgerechnete Messreihe nutzt 1 000; bei 300 geht die Live-Rechnung schneller, die Lösungen können etwas schlechter sein.")
    seed = st.number_input("Zufalls-Seed der Instanz", *bounds("seed_input"), key="seed_input", step=1)
    st.button("🎲 Neue Instanz generieren", width="stretch", on_click=randomize_seed)

sync_query_params({"n_slider": int(n), "beta_slider": float(beta), "layout_radio": layout, "depot_radio": depot, "k_slider": int(k), "ils_slider": int(ils), "seed_input": int(seed)})

settings = E.Settings(int(n), float(beta), layout, depot, int(k), int(ils), int(seed))
cell, _dist, exact_cell = R.nearest_cell(settings.n, settings.beta, settings.layout, settings.k, settings.depot)

# --- Erste Meldung: aus der gemessenen Zelle --------------------------------------------------------------------------------------------------

st.markdown("## ↩️ Wie viel lohnt Rückladung hier?")
kind, text = E.verdict_level(cell)
getattr(st, kind)(text)
if not exact_cell:
    st.caption("Für diese Einstellung gibt es keine eigene Zelle; gezeigt wird die nächstliegende gemessene Zelle.")

with st.spinner(f"Rechne die vier Planungsarten auf einer Instanz mit {settings.n} Kunden ({settings.ils} Iterationen je Lauf) ..."):
    a = _analysis(settings)
s_step, s1_step, a_step, m_step = (E.step_of(a, key) for key in C.STAGE_KEYS)

st.markdown("## 🗺️ Eine Instanz")
st.info("Das ist **eine Instanz**. Sie zeigt, wie die Planungsarten arbeiten; die Aussagen darüber, wie viel Rückladung bringt und wovon es abhängt, stützen sich auf die Messreihe weiter unten (25 Instanzen je Zelle).")

r1c1, r1c2 = st.columns(2)
# Delta immer als „mein Wert minus Referenz“; die Farbe regelt delta_color="inverse" (Vorzeichen-Falle, DEMO-PLAYBOOK §2).
r1c1.metric("Distanz mit Rückladung (A)", E.km(a_step.dist), delta=f"{R.num((a_step.dist - s_step.dist) / M.SCALE, 1, True)} gegen getrennt (S)", delta_color="inverse")
r1c2.metric("Touren: getrennt → mit Rückladung", f"{s_step.vehicles} → {a_step.vehicles}", delta=f"{a_step.vehicles - s_step.vehicles:+d} gegen getrennt (S)", delta_color="inverse")
r2c1, r2c2 = st.columns(2)
r2c1.metric("Leerkilometer-Anteil: S → A", f"{R.num(E.empty_share(s_step))} → {R.num(E.empty_share(a_step))} %",
            delta=f"{R.num(E.empty_share(a_step) - E.empty_share(s_step), 1, True)} Prozentpunkte", delta_color="inverse")
gain_a = s_step.dist - a_step.dist
gain_s1 = s_step.dist - s1_step.dist
r2c2.metric("Anteil der A-Ersparnis, den S1 holt", "–" if gain_a <= 0 else f"{R.num(100.0 * gain_s1 / gain_a)} %",
            delta=("A spart auf dieser Instanz nichts" if gain_a <= 0 else f"{E.km(gain_s1)} von {E.km(gain_a)} Längeneinheiten"), delta_color="off")

labels = {s.key: s.label for s in a.steps}
view_key = st.selectbox("Plan anzeigen für", list(labels), index=list(labels).index("A"), format_func=lambda key: labels[key], key="view_select",
                        help="Reine Anzeigewahl: ändert nichts an der Rechnung.")
view = E.step_of(a, view_key)
st.plotly_chart(VIZ.build_map(a.inst, view.routes), width="stretch", key="map_chart")
st.caption(f"{view.label}: Distanz {E.km(view.dist)}, {view.vehicles} Tour(en), Leerkilometer-Anteil {R.num(E.empty_share(view))} %, Kapazität {a.inst.Q}. "
           "Kreis = Lieferkunde, Quadrat = Abholkunde (Größe = Menge), Stern = Depot; gestrichelt grau: Leerstrecke (Last 0).")
st.download_button("📄 Tourenplan als PDF", data=build_pdf(settings, a, view_key), file_name="rueckladung.pdf", mime="application/pdf", key="pdf_download")

st.markdown("---")

# --- Kernfrage 1: Wie viel steckt nur im Maßstab? ---------------------------------------------------------------------------------------------

st.markdown("## ❓ Kernfrage 1: Wie viel steckt nur im strengen Maßstab?")
st.markdown(
    "S verbietet jede Mischung: Abholkunden fahren in S nie auf einer Liefertour mit, sondern nur in reinen Abholtouren (mehrere Abholkunden je Abholtour möglich). Das ist ein **strenger Maßstab**. Die **Treppe der Zulassung** zeigt, wie viel schon die einfachste Zulassung "
    "**S1** (ein Abholkunde je Lieferstour) holt, was die volle Rückladungsplanung **A** (Lieferkunden zuerst, dann beliebig viele Abholkunden) bringt und was die Reihenfolgepflicht kostet (**M**, gemischt)."
)
kind, text = E.verdict_stairs(a)
getattr(st, kind)(text)
st.plotly_chart(VIZ.build_stairs(a.steps), width="stretch", key="stairs_chart")
kind, text = E.verdict_s1(cell, settings.depot)
getattr(st, kind)(text)
c1, c2 = st.columns(2)
with c1:
    st.plotly_chart(VIZ.build_r_cells(settings.depot), width="stretch", key="r_chart")
    st.caption("Anteil R der A-Ersparnis, den S1 holt, je Zelle des gewählten Depots (grau gestrichelt 0,5, rot gestrichelt 0,8).")
with c2:
    st.plotly_chart(VIZ.build_stage_means(), width="stretch", key="stage_chart")
    st.caption(f"Mittel der Distanzersparnis gegen S je Planungsart, über alle {R.stage_means('rand')['m']} Instanzen je Depot (eigene Suche).")
kind, text = E.verdict_m(cell, settings.depot)
getattr(st, kind)(text)
st.caption("M gewinnt aus zwei Quellen (freie Reihenfolge und Wiederverwendung des Laderaums nach einer Auslieferung); beides ist nicht getrennt gemessen. Für S1 und M gibt es bei 20 und 40 Kunden keinen bewiesenen Wert, "
           "die Zuwächse sind eher Untergrenzen.")

st.markdown("---")

# --- Kernfrage 2: Wovon hängt die Höhe ab? ----------------------------------------------------------------------------------------------------

st.markdown("## ❓ Kernfrage 2: Wovon hängt die Höhe der Ersparnis ab?")
kind, text = E.verdict_hebel()
getattr(st, kind)(text)
c1, c2 = st.columns(2)
with c1:
    st.plotly_chart(VIZ.build_spread(), width="stretch", key="spread_chart")
    st.caption("Mittel der Distanzersparnis je Parameterwert über die 36 Zellen des Hauptrasters (Depot am Rand, beste bekannte Lösung aller Verfahren).")
with c2:
    st.plotly_chart(VIZ.build_beta_curve(R.load()["nach"]), width="stretch", key="beta_chart")
    st.caption("Nachmessung (nicht vorab festgelegt): Ersparnis über β für n = 20, K_L = 2, eigene Suche, 15 Instanzen je Punkt; Balken: Standardfehler. Unter den fünf gemessenen Punkten (β = 0,05 bis 0,9) ist 0,4 der höchste; die Hauptmessreihe zeigt bei β = 0,6 noch höhere Werte, das Maximum liegt also zwischen 0,4 und 0,8. Nach beiden Seiten fällt die Ersparnis, geht aber nirgends auf null.")
kind, text = E.verdict_depot()
getattr(st, kind)(text)
nm = R.nach_min()
st.caption(f"Kleinster Zellenmittelwert der Nachmessung: {R.num(nm['dD'][0])} % (Depot {E.depot_text(nm['depot'])}, Lage {C.LAYOUT_LABELS[nm['layout']].lower()}, β = {R.num(nm['beta'], 2)}). In keiner der {R.nach_instanzen()} Instanzen der Nachmessung ({len(R.load()['nach'])} Zellen mit je {R.load()['nach'][0]['m']} Instanzen) ist A gleich S.")

st.markdown("---")

# --- Kernfrage 3: Wie gut sind die Verfahren? --------------------------------------------------------------------------------------------------

st.markdown("## ❓ Kernfrage 3: Wie gut ist die eigene Suche, wie weit ist das Optimum?")
lo = R.load()["loeser"]
ex = lo["exakt_n20"]
st.markdown(
    f"**Bewiesene Optima bei 20 Kunden (CP-SAT, 40 s, ein Worker, S in zwei CVRP zerlegt mit je 20 s, je 450 Instanzen):** S in {ex['S']['proven']}, A in {ex['A']['proven']} Instanzen. Dort liegt die eigene Suche im Mittel {R.num(ex['S']['ils_gap'], 3)} % (S, optimal in {ex['S']['ils_opt']} von {ex['S']['ils_of']}) "
    f"und {R.num(ex['A']['ils_gap'], 3)} % (A, optimal in {ex['A']['ils_opt']} von {ex['A']['ils_of']}) über dem Optimum; OR-Tools {R.num(ex['S']['ort_sav'], 2)} bis {R.num(ex['S']['ort_std'], 2)} % (S) und {R.num(ex['A']['ort_std'], 2)} bis {R.num(ex['A']['ort_sav'], 2)} % (A)."
)
rows = []
for key, label in (("n20_S", "n = 20, S"), ("n20_A", "n = 20, A"), ("n40_S", "n = 40, S"), ("n40_A", "n = 40, A")):
    d = lo[key]
    rows.append({"Fall": label, "Greedy (Savings) Lücke %": d.get("greedy", {}).get("gap"), "eigene Suche Lücke %": d["ils"]["gap"], "eigene Suche am Besten": f"{d['ils']['best']} von {d['ils']['of']}",
                 "OR-Tools Standard Lücke %": d["ort_standard"]["gap"], "OR-Tools abgestimmt Lücke %": d["ort_tuned"]["gap"]})
st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch",
             column_config={c_: st.column_config.NumberColumn(format="%.2f") for c_ in ("Greedy (Savings) Lücke %", "eigene Suche Lücke %", "OR-Tools Standard Lücke %", "OR-Tools abgestimmt Lücke %")})
st.caption("Mittlere Lücke zur besten bekannten Lösung je Instanz (Hauptmessreihe, 450 Instanzen je n (900 insgesamt), Depot am Rand); „abgestimmt“ heißt hier nur Erststrategie SAVINGS: Zusatzoperatoren und Warmstart machten OR-Tools in der Abstimmung (n = 40, 6 s, 12 Instanzen) schlechter. "
           f"Wo CP-SAT bei n = 20 nicht beweist, liegt die Schranke im Mittel {R.num(ex['S']['bound_gap'], 2)} % (S) und {R.num(ex['A']['bound_gap'], 2)} % (A) unter der besten Lösung (bezogen auf die beste Lösung; höchstens {R.num(ex['S']['bound_gap_max'], 2)} % und {R.num(ex['A']['bound_gap_max'], 2)} %): Die Schranke sagt dann wenig; "
           "die Aussage „eigene Suche praktisch optimal“ gilt für die bewiesenen Fälle.")

st.markdown("---")

# --- Methodenvergleich ---------------------------------------------------------------------------------------------------------------------

with st.expander("🔧 Wie wir das erreichen – vollständiger Methodenvergleich"):
    tab_plan, tab_methods, tab_stairs, tab_or, tab_exact, tab_series = st.tabs(
        ["🗺️ Tourenplan", "📊 Verfahren", "🪜 Treppe der Zulassung", "🧰 OR-Tools", "🧮 Exakt (CP-SAT)", "📈 Messreihe"])
    with tab_plan:
        st.markdown(f"Halteliste für **{view.label}** (Last nach jedem Halt; Kapazität {a.inst.Q}).")
        for ri, route in enumerate(view.routes):
            prof = M.load_profile(a.inst, list(route))
            df = pd.DataFrame([{"Halt": i + 1, "Kunde": c_, "Art": "Lieferung" if a.inst.kind[c_] == M.L else "Abholung", "Menge": a.inst.dem[c_], "Last danach": prof[i + 1][3]}
                               for i, c_ in enumerate(route)])
            st.caption(f"Tour {ri + 1}: Länge {E.km(M.route_len(a.inst.D, list(route)))}, größte Last {max(p[3] for p in prof)} von {a.inst.Q}; Last bei der Abfahrt {prof[0][3]}")
            st.dataframe(df, hide_index=True, width="stretch")
    with tab_methods:
        rows = [{"Planungsart": s.label, "Distanz": s.dist / M.SCALE, "Ersparnis gegen S (%)": E.saving(s_step.dist, s.dist), "Touren": s.vehicles,
                 "Leerkilometer-Anteil (%)": E.empty_share(s), "Lastkilometer-Anteil (%)": 100.0 * s.load_share, "Rechenzeit (s)": s.seconds} for s in a.steps]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch",
                     column_config={"Distanz": st.column_config.NumberColumn(format="%.1f"), "Ersparnis gegen S (%)": st.column_config.NumberColumn(format="%.1f"),
                                    "Leerkilometer-Anteil (%)": st.column_config.NumberColumn(format="%.1f"), "Lastkilometer-Anteil (%)": st.column_config.NumberColumn(format="%.1f"),
                                    "Rechenzeit (s)": st.column_config.NumberColumn(format="%.2f")})
        st.caption("Die Rechenzeit gilt für diesen Rechner und diese Sitzung (Summe der Teilläufe der Stufe: S1 und M rechnen mit der Lösung der engeren Stufe als Start, A und M zusätzlich mit zwei Starten, die bessere zählt). "
                   "Distanz in Längeneinheiten des 100 × 100-Gebiets.")
        st.markdown(
            "- **S, A:** eigene Suche (Ruin-and-Recreate mit Relocate, Swap, 2-opt, 2-opt\\*), Start Clarke-Wright je Art; A startet bei der S-Lösung und bei der S1-Lösung, die bessere zählt.\n"
            "- **S1, M:** dieselbe Suche, allgemein gefasst; Start jeweils mit der Lösung der engeren Stufe (M zusätzlich von S aus), also Distanz(S) ≥ Distanz(S1) ≥ Distanz(A) ≥ Distanz(M) auf jeder Instanz.\n"
            "- **OR-Tools und CP-SAT** gibt es für S und A (eigene Tabs); für S1 und M gibt es keinen Vergleichslöser."
        )
    with tab_stairs:
        st.markdown(
            "Die vier Zulassungsstufen von eng nach weit: **S** getrennt, **S1** ein Abholkunde je Lieferstour, **A** Lieferkunden zuerst und dann beliebig viele Abholkunden, **M** gemischt "
            "(Abholkunden dürfen zwischen Lieferkunden liegen; die Last auf jeder Teilstrecke darf die Kapazität nicht überschreiten). Jede Stufe enthält die engere: im Optimum gilt Distanz(S) ≥ Distanz(S1) ≥ Distanz(A) ≥ Distanz(M)."
        )
        st.plotly_chart(VIZ.build_stairs(a.steps), width="stretch", key="stairs_chart_tab")
        stg = R.stage_means(settings.depot)
        st.caption(f"Vorgerechnet (Depot {E.depot_text(settings.depot)}, alle {stg['m']} Instanzen): S1 {R.num(stg['dD_S1'])} %, A {R.num(stg['dD_A'])} %, M {R.num(stg['dD_M'])} % Ersparnis gegen S.")
    with tab_or:
        secs = C.ORTOOLS_SECONDS[settings.n]
        st.markdown(
            f"OR-Tools (Routing, Guided Local Search) für S und A in zwei Einstellungen, je {R.num(secs, 0)} s: **Standard** (Erststrategie PATH_CHEAPEST_ARC) und **SAVINGS** (Erststrategie Savings). "
            "Zusatzoperatoren und Warmstart machten OR-Tools in der Abstimmung (n = 40, 6 s, 12 Instanzen) schlechter und sind nicht Teil der Demo."
        )
        if st.button(f"OR-Tools rechnen (4 × {R.num(secs, 0)} s)", key="ortools_start"):
            st.session_state["ortools_done"] = settings
            st.rerun()
        if st.session_state.get("ortools_done") == settings:
            with st.spinner(f"OR-Tools rechnet (4 Läufe à {R.num(secs, 0)} s) ..."):
                try:
                    res = _ortools(settings)
                except ImportError:
                    res = None
                    st.warning("OR-Tools ist in dieser Umgebung nicht installiert.")
            if res is not None:
                kind, text = E.verdict_ortools(a, s_step.dist, a_step.dist, res["standard"], res["sav"])
                getattr(st, kind)(text)
    with tab_exact:
        # Der Tab ist selbstständig: eigener Button, Spinner und Ergebnis, gegen das aktuelle Szenario geprüft (DEMO-PLAYBOOK §2).
        if settings.n > C.EXACT_N_MAX:
            st.info(E.exact_unavailable_text(settings.n))
        else:
            ex_ = R.load()["loeser"]["exakt_n20"]
            st.markdown(
                f"CP-SAT (Mehrfach-Kreis, ein Worker, höchstens {R.num(C.EXACT_SECONDS, 0)} s je Planungsart, Warmstart aus der eigenen Suche). In der Messreihe bewies es bei 20 Kunden S in {ex_['S']['proven']} und A in {ex_['A']['proven']} "
                f"von je {ex_['S']['of']} Instanzen (S in zwei CVRP zerlegt mit je 20 s; Warmstart aus der besten bis dahin bekannten Lösung). S1 und M haben keinen exakten Löser."
            )
            for mode in ("S", "A"):
                key = f"exact_{mode}"
                if st.button(f"Optimum für {mode} berechnen (bis {R.num(C.EXACT_SECONDS, 0)} s)", key=f"{key}_start"):
                    st.session_state[f"{key}_done"] = settings
                    st.rerun()
                if st.session_state.get(f"{key}_done") == settings:
                    with st.spinner(f"CP-SAT rechnet für {mode} ..."):
                        try:
                            res = _exact(settings, mode)
                        except ImportError:
                            res = None
                            st.warning("OR-Tools (CP-SAT) ist in dieser Umgebung nicht installiert.")
                    if res is not None:
                        own = (s_step if mode == "S" else a_step).dist
                        kind, text = E.verdict_exact(mode, res["status"], res["obj"], res["bound"], own)
                        getattr(st, kind)(text)
                        st.caption(f"Rechenzeit {res['sec']:.1f} s, Status {res['status']}.")
    with tab_series:
        st.markdown(f"Alle gemessenen Zellen für das Depot {E.depot_text(settings.depot)} (je 25 Instanzen, Zufalls-Seeds ab 100000, eigene Suche mit 1 000 Iterationen, Mittel ± Standardfehler in Prozentpunkten von S).")
        rows = []
        for c_ in sorted(R.cells(settings.depot), key=lambda c_: c_["ci"]):
            rows.append({"Zelle": c_["ci"], "n": c_["n"], "β (%)": round(100 * c_["beta"]), "Lage": C.LAYOUT_LABELS[c_["layout"]], "K_L": c_["K_L"],
                         "ΔD S1 (%)": c_["dD_S1"][0], "ΔD A (%)": c_["dD_A"][0], "± SE A": c_["dD_A"][1], "ΔD M (%)": c_["dD_M"][0], "A → M (%)": c_["dD_AM"][0],
                         "R": c_["R"], "Touren S": c_["touren"]["S"], "Touren A": c_["touren"]["A"], "Leerkm S (%)": c_["leer"]["S"], "Leerkm A (%)": c_["leer"]["A"]})
        fmt = {col: st.column_config.NumberColumn(format="%.1f") for col in ("ΔD S1 (%)", "ΔD A (%)", "± SE A", "ΔD M (%)", "A → M (%)", "Touren S", "Touren A", "Leerkm S (%)", "Leerkm A (%)")}
        fmt["R"] = st.column_config.NumberColumn(format="%.2f")
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", column_config=fmt)
        st.caption(f"Zeilen sortiert nach Zellennummer; kleinste Ersparnis A: Zelle {R.min_cell(settings.depot)['ci']} ({R.num(R.min_cell(settings.depot)['dD_A'][0])} %), größte: Zelle {R.max_cell(settings.depot)['ci']} ({R.num(R.max_cell(settings.depot)['dD_A'][0])} %).")
        zs = R.load()["zusatz"]
        st.markdown(
            f"**Ungleiche Mengen** (Zusatzraster, nur Bericht, n = 20, 12 Zellen, je 25 Instanzen): bei kleinen Abholmengen (2 bis 10) holt S1 {R.num(zs['klein']['overall']['dD_S1'])} % von {R.num(zs['klein']['overall']['dD_A'])} %, "
            f"bei großen (15 bis 40) {R.num(zs['gross']['overall']['dD_S1'])} % von {R.num(zs['gross']['overall']['dD_A'])} % (A → M: {R.num(zs['klein']['overall']['dD_AM'])} bzw. {R.num(zs['gross']['overall']['dD_AM'])} %). "
            "Die Instanzen sind andere als im Hauptraster."
        )
        tm = R.load()["timing"]
        st.markdown("**Rechenzeit je Stufe** (lokal, ein Prozess, 5 Instanzen: n, β = 0,4, gemischt, K_L = 2; Mittel in Sekunden): " + "; ".join(
            f"n = {t['n']}, {t['iters']} Iterationen: S {R.num(t['S']['mean'], 2)}, S1 {R.num(t['S1']['mean'], 2)}, A {R.num(t['A']['mean'], 2)}, M {R.num(t['M']['mean'], 2)}" for t in tm) +
            ". Die Zeit auf anderen Rechnern ist anders; auf Streamlit Cloud ist sie nicht gemessen.")

with st.expander("Wie funktioniert diese Demo?"):
    stg_r, stg_m = R.stage_means("rand"), R.stage_means("mitte")
    zv_k, zv_g = R.zusatz_vergleich("klein"), R.zusatz_vergleich("gross")
    st.markdown(
        f"""
**Die Aufgabe.** Ein Depot, {settings.n} Kunden: {a.inst.nL} Lieferkunden (Lieferung nimmt die Last ab) und {a.inst.nB} Abholkunden (Abholung nimmt Last auf), Kapazität {a.inst.Q}, Entfernungen euklidisch im 100 × 100-Gebiet.
Gesucht sind Touren mit möglichst kleiner Gesamtdistanz. Lieferung und Abholung belegen getrennte Last: je Tour Summe der Lieferungen ≤ Kapazität und Summe der Abholungen ≤ Kapazität (bei M: die Last auf jeder Teilstrecke).

**Die vier Planungsarten.**
- *S, getrennt:* Touren sind rein Lieferung oder rein Abholung. Abholkunden fahren in S nie auf einer Liefertour mit, sondern nur in reinen Abholtouren (mehrere Abholkunden je Abholtour möglich).
- *S1, eine Rückladung je Tour:* eine Lieferstour darf auf dem Rückweg höchstens einen Abholkunden bedienen; weitere Abholkunden nur in reinen Abholtouren.
- *A, VRPB:* auf jeder Tour zuerst alle Lieferkunden, dann beliebig viele Abholkunden.
- *M, gemischt:* Abholkunden dürfen zwischen Lieferkunden liegen; die Last auf jeder Teilstrecke (noch auszuliefernde plus bereits abgeholte Menge) darf die Kapazität nicht überschreiten.

**Kennzahlen.** Distanz, Touren, **Leerkilometer** (Strecke mit Last 0: Rückweg nach der letzten Lieferung ohne Abholung, Hinweg einer reinen Abholtour) und Lastkilometer-Anteil (Summe Last mal Strecke durch Kapazität mal Gesamtstrecke).
Die Strecken mit Last 0 und die Strecken mit Last ergeben zusammen die Gesamtdistanz (getestet).

**Was die Live-Zahlen bedeuten.** Sie gelten für diese eine Instanz. Die Aussagen der Kernfragen stammen aus einer vorgerechneten Messreihe (36 Zellen je Depot, je 25 Instanzen, Zufalls-Seeds ab 100000, eigene Suche mit 1 000 Iterationen);
alle Regler stehen auf gemessenen Stufen, zu jeder Einstellung gehört also eine Zelle. Im Hauptraster ist A in allen {sum(c_['m'] for c_ in R.main_cells())} Instanzen (Depot am Rand) billiger als S; Mittel {R.num(R.load()['main']['dd_all'])} % (beste bekannte Lösung aller Verfahren).

**Mit dem Depot in der Mitte** sinkt das Mittel der A-Ersparnis in der Restmessung von {R.num(stg_r['dD_A'])} auf {R.num(stg_m['dD_A'])} %.

**🚧 Wo die Annahmen enden**

| Annahme | Was passiert, wenn sie verletzt ist | Wer setzt an |
|---|---|---|
| Depot am Rand oder in der Mitte | Das Depot färbt die Höhe: mit dem Depot in der Mitte ist die Ersparnis im Mittel {R.num(R.depot_diff()['mittel'])} Prozentpunkte kleiner | Regler „Depot“ |
| S verbietet jede Mischung | S ist ein strenger Maßstab; S1 holt nur einen Teil ({R.num(stg_r['dD_S1'])} von {R.num(stg_r['dD_A'])} %, Depot am Rand) | Treppe der Zulassung |
| Mengen gleichverteilt 5 bis 25 | Große Abholmengen heben vor allem den S1-Anteil (R {R.num(zv_g['r_haupt'], 2)} auf {R.num(zv_g['r'], 2)} in denselben 12 Zellen); kleine senken S1 und A ähnlich stark (S1 {R.num(zv_k['d_s1'], 1, True).replace('-', '−')}, A {R.num(zv_k['d_a'], 1, True).replace('-', '−')} Pp); nur n = 20, nur Bericht | Zusatzraster im Tab Messreihe |
| Unbegrenzte Flotte, nur Distanz | Mit Fixkosten je Fahrzeug würde die absolute Ersparnis wachsen (die Touren sinken stark); mit begrenzter Flotte kann S unzulässig werden; nicht gemessen | Ausbau |
| Zufallsinstanzen, euklidisch, keine Zeitfenster, keine Servicezeit | Zeitfenster können die Mischung einschränken; echte Straßennetze nicht gemessen | Ausbau |
| Nur n = 20 und 40 | Für größere Instanzen keine Aussage; die Güte der eigenen Suche ist nur bei n = 20 gegen bewiesene Werte geprüft | Kernfrage 3 |
| Kein bewiesenes Optimum für S1 und M | Bei n = 8 trifft die Suche (150 Iterationen) in 24 von 24 Instanzen das Optimum; bei n = 20 und 40 ist die Güte für S1 und M unbekannt, die Zuwächse sind eher Untergrenzen | Tab Exakt |
| M gewinnt aus zwei Quellen | Freie Reihenfolge und Wiederverwendung des Laderaums nach einer Auslieferung sind nicht getrennt gemessen | nicht gemessen |
| Rechenzeiten | Auf anderen Rechnern anders; OR-Tools und CP-SAT sind zeitlimitiert und nicht bitgleich reproduzierbar; Zeit auf Streamlit Cloud nicht gemessen | Tab Verfahren |
"""
    )

with st.expander("📐 Mathematische Formulierung"):
    st.markdown(
        r"""
**Lesehilfe.** Gegeben sind ein Depot $0$, Lieferkunden $L$ mit Lieferung $d_i$, Abholkunden $B$ mit Abholung $q_j$, eine Kapazität $Q$ und Entfernungen $t_{ij}$. Gesucht sind Touren, die jeden Kunden genau einmal bedienen und die Gesamtdistanz minimieren;
auf jeder Tour kommen erst alle Lieferkunden, dann alle Abholkunden (Planungsart A).

| Symbol | Bedeutung |
|---|---|
| $L$, $B$ | Lieferkunden und Abholkunden, $N = L \cup B$ |
| $d_i$, $q_j$ | Menge der Lieferung an $i \in L$, der Abholung bei $j \in B$ |
| $Q$ | Kapazität; Lieferung und Abholung belegen getrennte Last |
| $t_{ij}$ | ganzzahlige Entfernung von $i$ nach $j$ (euklidisch, Depot $= 0$) |
| $x_{ij}$ | 1, wenn ein Fahrzeug direkt von $i$ nach $j$ fährt |
| $u_i$, $v_i$ | bis einschließlich $i$ ausgelieferte Menge, bis einschließlich $i$ abgeholte Menge |
        """
    )
    st.markdown(
        """
$$\\min \\sum_{i,j \\in N \\cup \\{0\\}} t_{ij}\\, x_{ij}$$

$$\\sum_{j} x_{ij} = 1 \\quad \\text{und} \\quad \\sum_{j} x_{ji} = 1 \\quad (i \\in N)$$

$$x_{ij} = 0 \\quad (i \\in B,\\; j \\in L)$$

$$u_j = u_i + d_j \\quad \\text{und} \\quad v_j = v_i + q_j \\quad \\text{falls } x_{ij} = 1 \\;(i, j \\in N), \\qquad u_j = d_j,\\; v_j = q_j \\quad \\text{falls } x_{0j} = 1, \\qquad u_i,\\, v_i \\le Q$$

Dabei ist $d_j = 0$ für $j \\in B$ und $q_j = 0$ für $j \\in L$. Dazu gehören Binärbedingungen für $x$, beliebig viele Abgänge und Rückkehren am Depot (unbegrenzte Flotte) und ein Teiltourverbot (jeder Kreis enthält das Depot);
in CP-SAT wird das als Mehrfach-Kreis abgebildet. $u_i \\le Q$ heißt: die Summe der Lieferungen einer Tour passt in die Kapazität, ebenso die Summe der Abholungen ($v_i \\le Q$).

**Die anderen Planungsarten.** **S:** zusätzlich $x_{ij} = 0$ für $i \\in L,\\, j \\in B$ und $i \\in B,\\, j \\in L$ (keine Mischung; das Depot verbindet beide Arten). **S1:** wie A, aber auf einer Tour mit Lieferkunden höchstens ein Abholkunde.
**M:** beliebige Reihenfolge; die Last auf der Teilstrecke nach Halt $i$ ist (noch auszuliefernde Menge) plus (bereits abgeholte Menge) und darf $Q$ nicht überschreiten. S1 und M werden nur mit der eigenen Suche gerechnet; ein exaktes Modell gibt es für S und A (CP-SAT, n = 20).
Dieser Block ist das vollständige Modell für A und S; S1 und M sind in Worten beschrieben, nicht als eigenes Programm formuliert.

**Kennzahlen.** Leerkilometer $=$ Summe der $t_{ij}$ über alle gefahrenen Bögen, nach denen die Last $0$ ist; Lastkilometer-Anteil $= \\sum (\\text{Last} \\cdot t_{ij}) \\,/\\, (Q \\cdot \\sum t_{ij})$; Ersparnis $\\Delta D = (D_S - D_X) / D_S$.
"""
    )

st.markdown("---")
st.caption(
    "Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – "
    "Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). "
    "Mehr zum Thema: [Tourenplanung optimieren](https://sebastianhanisch.net/tourenplanung-optimierung.html)."
)
