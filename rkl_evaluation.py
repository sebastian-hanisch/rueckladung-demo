"""Live-Analyse einer Instanz (die vier Planungsarten S, S1, A, M), Kennzahlen und Verdikte als reine Funktionen: verdict_*(...) -> (Art, Text)."""

from dataclasses import dataclass

import rkl_constants as C
import rkl_model as M
import rkl_results as R
import rkl_search as SR


@dataclass(frozen=True)
class Settings:
    n: int = C.DEFAULT_N
    beta: float = C.DEFAULT_BETA
    layout: str = C.DEFAULT_LAYOUT
    depot: str = C.DEFAULT_DEPOT
    k: int = C.DEFAULT_K
    ils: int = C.DEFAULT_ILS
    seed: int = C.DEFAULT_SEED


@dataclass(frozen=True)
class Step:
    key: str
    label: str
    routes: tuple      # Tuple von Tuples (hashbar für den Cache)
    dist: int
    vehicles: int
    empty: int         # Leerkilometer in Entfernungseinheiten (1 Einheit = 0,1 Längeneinheit)
    load_share: float  # Lastkilometer-Anteil
    seconds: float     # Rechenzeit der Teilläufe dieser Stufe auf diesem Rechner


@dataclass(frozen=True)
class Analysis:
    inst: M.Instance
    steps: tuple


def make_inst(settings: Settings) -> M.Instance:
    return M.make_instance(settings.n, settings.beta, settings.layout, settings.k, settings.seed, depot=M.DEPOTS[settings.depot])


def _freeze(routes):
    return tuple(tuple(r) for r in routes)


def analyse(settings: Settings) -> Analysis:
    """Alle vier Stufen auf einer Instanz mit der eigenen Suche (Kette der Messreihe); deterministisch bei gleichem Zufalls-Seed und gleicher Iterationszahl."""
    inst = make_inst(settings)
    ch = SR.chain(inst, settings.ils, settings.seed)
    t = ch["_seconds"]
    secs = {"S": t["S"], "S1": t["S1"], "A": t["A_ctl"] + t["A_chain"], "M": t["M_fromA"] + t.get("M_fromS", 0.0)}
    steps = []
    for key in C.STAGE_KEYS:
        m = M.metrics(inst, ch[key])
        steps.append(Step(key, C.STAGE_LABELS[key], _freeze(ch[key]), m["dist"], m["vehicles"], m["empty"], m["load_share"], secs[key]))
    return Analysis(inst, tuple(steps))


def step_of(a: Analysis, key: str) -> Step:
    return next(s for s in a.steps if s.key == key)


def saving(base: int, value: int) -> float:
    """Ersparnis gegenüber der Referenz in Prozent; Referenz 0 (nichts zu fahren) gibt 0."""
    return 0.0 if base <= 0 else 100.0 * (base - value) / base


def empty_share(step: Step) -> float:
    """Leerkilometer-Anteil an der Distanz in Prozent."""
    return 0.0 if step.dist <= 0 else 100.0 * step.empty / step.dist


def km(units: int) -> str:
    """Entfernung in Längeneinheiten des 100 x 100-Gebiets (1 Einheit der Rechnung = 0,1) mit Dezimalkomma."""
    return R.num(units / M.SCALE, 1)


def minus_percent(saved: float) -> str:
    """Eingesparter Anteil als Text mit echtem Minuszeichen ('−1,9 %'); ohne Ersparnis '±0,0 %'."""
    return f"−{R.num(saved)} %" if saved > 0 else "±0,0 %"


def depot_text(depot: str) -> str:
    return "am Gebietsrand (50, 0)" if depot == "rand" else "in der Mitte des Gebiets (50, 50)"


def cell_text(cell) -> str:
    return (f"Zelle {cell['ci']}, Depot {depot_text(cell['depot'])}, {cell['n']} Kunden, {R.num(100 * cell['beta'], 0)} % Abholkunden, "
            f"Lage {C.LAYOUT_LABELS[cell['layout']].lower()}, K_L = {cell['K_L']}, {cell['m']} Instanzen")


# --- Verdikte (rein: die App ruft st.<Art>(Text), der Test prüft jede Zahl im Text) ------------------------------------------------------------

LEVEL_KIND = {"wenig": "warning", "deutlich": "info", "sehr": "success"}
LEVEL_HEAD = {"wenig": "Rückladung lohnt hier wenig", "deutlich": "Rückladung lohnt deutlich", "sehr": "Rückladung lohnt sehr"}


def verdict_level(cell) -> tuple[str, str]:
    """Erste Meldung (drei Zustände) aus der gemessenen Zelle, nicht aus der einen Instanz; nennt Depotlage, Maßstab S und den Anteil von S1."""
    lvl = R.level(cell["dD_A"][0])
    other = R.other_depot(cell)
    other_text = "in der Mitte" if cell["depot"] == "rand" else "am Rand"
    t = cell["touren"]
    lk = cell["leer"]
    s1 = cell["dD_S1"][0]
    text = (
        f"**{LEVEL_HEAD[lvl]}.** In der gemessenen Zelle ({cell_text(cell)}) spart die Planung mit Rückladung (A) im Mittel **{R.pm(cell['dD_A'])} %** Distanz gegenüber der "
        f"getrennten Planung (S); die Touren sinken von {R.num(t['S'])} auf {R.num(t['A'])}, der Leerkilometer-Anteil von {R.num(lk['S'])} auf {R.num(lk['A'])} %. "
        f"Das Depot liegt {depot_text(cell['depot'])}; mit dem Depot {other_text} liegt dasselbe Zellmittel bei {R.num(other['dD_A'][0])} %. "
        f"S ist ein strenger Maßstab (Abholkunden fahren in S nie auf einer Liefertour mit, sondern nur in reinen Abholtouren): die einfachste Zulassung S1 (ein Abholkunde je Lieferstour) holt davon {R.num(s1)} von {R.num(cell['dD_A'][0])} % Distanz. "
        f"(Zustand nach dem Zellmittel: unter {R.num(C.LEVEL_WENIG, 0)} % wenig, bis unter {R.num(C.LEVEL_SEHR, 0)} % deutlich, ab {R.num(C.LEVEL_SEHR, 0)} % sehr; Schwellen gesetzt, nicht hergeleitet.)"
    )
    return LEVEL_KIND[lvl], text


def verdict_stairs(a: Analysis) -> tuple[str, str]:
    """Kernabschnitt ① live: der Zuwachs je Stufe auf dieser einen Instanz (Zahlen ohne Urteilswort)."""
    s, s1, aa, m = (step_of(a, k) for k in C.STAGE_KEYS)
    text = (
        f"Auf dieser Instanz (eine Instanz, kein Beleg): Distanz S {km(s.dist)}, S1 {km(s1.dist)} ({minus_percent(saving(s.dist, s1.dist))} gegen S), "
        f"A {km(aa.dist)} ({minus_percent(saving(s.dist, aa.dist))}), M {km(m.dist)} ({minus_percent(saving(s.dist, m.dist))}). "
        f"Touren {s.vehicles} → {s1.vehicles} → {aa.vehicles} → {m.vehicles}; Leerkilometer-Anteil {R.num(empty_share(s))} → {R.num(empty_share(s1))} → {R.num(empty_share(aa))} → {R.num(empty_share(m))} %."
    )
    return "info", text


def verdict_s1(cell, depot: str) -> tuple[str, str]:
    """Kernabschnitt ①: wie viel der A-Ersparnis die einfachste Zulassung S1 schon holt, in dieser Zelle und über alle 36 Zellen des Depots."""
    rc = R.r_counts(depot)
    urteil = R.urteil_s1(depot)
    stg = R.stage_means(depot)
    r = cell["R"]
    r_text = "in dieser Zelle nicht bestimmbar (A spart hier nichts)" if r is None else f"in dieser Zelle R = {R.num(r, 2)}"
    text = (
        f"**S1 holt im Mittel über alle Instanzen {R.num(stg['dD_S1'])} % von {R.num(stg['dD_A'])} %** (Depot {depot_text(depot)}): {r_text} (R = Anteil der A-Ersparnis, den S1 holt). "
        f"Über die {rc['zellen']} Zellen liegt R in {rc['deutlich_zurueck']} Zellen bei höchstens {R.num(C.R_DEUTLICH_ZURUECK, 1)} und in {rc['fast_alles']} bei mindestens {R.num(C.R_FAST_ALLES, 1)} "
        f"(Median {R.num(rc['median'], 2)}). Urteil nach den vorab festgelegten Schwellen (mindestens 24 von 36 Zellen): **{urteil}**."
    )
    return "info", text


def verdict_m(cell, depot: str) -> tuple[str, str]:
    mc = R.m_counts(depot)
    stg = R.stage_means(depot)
    gm = R.getrennt_m(depot)
    text = (
        f"**Die gemischte Variante M bringt gegenüber A im Mittel {R.num(stg['dD_AM'])} %** (Depot {depot_text(depot)}); in dieser Zelle {R.pm(cell['dD_AM'])} %. "
        f"Über die {mc['zellen']} Zellen sind es in {mc['ab_2']} Zellen mindestens 2 % und in {mc['unter_1']} Zellen unter 1 %: Urteil **{R.urteil_m(depot)}**. "
        f"Bei getrennten Zonen ist M fast immer gleich A (in {gm['gleich']} von {gm['instanzen']} Instanzen gleich, Mittel von A gegen M {R.num(gm['mittel'], 2)} %), "
        f"in gemischter Lage steigt der Gewinn bis {R.num(max(c['dD_AM'][0] for c in R.cells(depot)))} %."
    )
    return "info", text


def verdict_hebel() -> tuple[str, str]:
    """Kernabschnitt ②: wovon hängt die Höhe ab (Hauptmessreihe, Depot am Rand, beste bekannte Lösung)."""
    pm_ = R.main_param_means()
    b = pm_["beta"]["means"]
    text = (
        f"**Am stärksten wirkt der Anteil der Abholkunden β:** Mittel von ΔD bei 0,2 / 0,4 / 0,6 = {R.num(b[0.2])} / {R.num(b[0.4])} / {R.num(b[0.6])} % (Spreizung {R.num(pm_['beta']['spread'])} Prozentpunkte). "
        f"Danach die Lage der Zonen ({R.num(pm_['layout']['spread'])} Pp), die Knappheit K_L ({R.num(pm_['K_L']['spread'])} Pp) und n ({R.num(pm_['n']['spread'])} Pp). "
        f"Es gibt keine Zelle ohne Ersparnis: kleinstes Zellmittel {R.num(min(c['dD'] for c in R.main_cells()))} %, größtes {R.num(max(c['dD'] for c in R.main_cells()))} % (Hauptraster, Depot am Rand, 36 Zellen)."
    )
    return "info", text


def verdict_depot() -> tuple[str, str]:
    d = R.depot_diff()
    st_r, st_m = R.stage_means("rand"), R.stage_means("mitte")
    text = (
        f"**Das Depot zählt:** mit dem Depot in der Mitte sinkt die A-Ersparnis von {R.num(st_r['dD_A'])} % auf {R.num(st_m['dD_A'])} % (im Mittel {R.num(d['mittel'])} Prozentpunkte; die Mitte liegt in "
        f"{d['mitte_hoeher']} von {d['zellen']} Zellen höher, die Differenz reicht von {R.num(d['min'])} bis {R.num(d['max'])} Pp). Die gemischte Variante M gewinnt dagegen in der Mitte hinzu "
        f"({R.num(st_r['dD_AM'])} → {R.num(st_m['dD_AM'])} % gegenüber A)."
    )
    return "info", text


def verdict_ortools(a: Analysis, own_s: int, own_a: int, std: dict, sav: dict) -> tuple[str, str]:
    """OR-Tools in zwei Einstellungen gegen die eigene Suche (nur S und A); Lücke = (OR-Tools − eigene Suche) / eigene Suche."""
    def gap(x, own):
        return 0.0 if own <= 0 else 100.0 * (x - own) / own
    text = (
        f"OR-Tools (Standard): S {km(std['S'])}, A {km(std['A'])}; OR-Tools (SAVINGS): S {km(sav['S'])}, A {km(sav['A'])}; eigene Suche: S {km(own_s)}, A {km(own_a)} "
        f"(Lücke OR-Tools Standard zur eigenen Suche: S {R.num(gap(std['S'], own_s), 2, True)} %, A {R.num(gap(std['A'], own_a), 2, True)} %; SAVINGS: S {R.num(gap(sav['S'], own_s), 2, True)} %, A {R.num(gap(sav['A'], own_a), 2, True)} %). "
        "Eine Instanz, kein Beleg; die Messreihe nennt die mittleren Lücken im Tab Messreihe."
    )
    return "info", text


def verdict_exact(mode: str, status: str, obj, bound, own: int) -> tuple[str, str]:
    """CP-SAT (n = 20): Status 'OPTIMAL' = bewiesen. Nie 'Optimum' für eine nicht bewiesene Zahl."""
    if obj is None:
        return "warning", f"CP-SAT fand für Planungsart {mode} in der Zeit keine Lösung (Status {status})."
    ex = R.load()["loeser"]["exakt_n20"][mode]
    if status == "OPTIMAL":
        gap = 0.0 if obj <= 0 else 100.0 * (own - obj) / obj
        return "success", (f"Optimum für {mode} bewiesen: {km(int(round(obj)))}. Die eigene Suche liegt bei {km(own)} ({R.num(gap, 2, True)} % gegenüber dem Optimum). "
                           f"In der Messreihe bewies CP-SAT bei n = 20 (40 s, ein Worker) {ex['proven']} von {ex['of']} Instanzen.")
    return "warning", (f"Optimum für {mode} **nicht bewiesen** (Status {status}): beste Lösung von CP-SAT {km(int(round(obj)))}, untere Schranke {km(int(bound))}, eigene Suche {km(own)}. "
                       f"Wo nicht bewiesen, liegt die Schranke in der Messreihe im Mittel {R.num(ex['bound_gap'], 2)} % unter der besten Lösung (bezogen auf die beste Lösung; höchstens {R.num(ex['bound_gap_max'], 2)} %); die Schranke sagt dann über die Güte wenig.")


def exact_unavailable_text(n: int) -> str:
    return (f"Der exakte Löser wird nur für n = {C.EXACT_N_MAX} Kunden angeboten; bei n = {n} wurde er nicht gemessen; erwartet wird, dass ein Beweis in {C.EXACT_SECONDS} s nicht gelingt (Erwartung aus n = {C.EXACT_N_MAX}, nicht nachgerechnet). "
            "Die Güte der eigenen Suche gegen bewiesene Optima steht im Tab Messreihe (n = 20).")
