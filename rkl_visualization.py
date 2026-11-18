"""Plotly-Abbildungen. Alle Achsen sind gesperrt (fixedrange), damit Touch-Geräte beim Scrollen nicht am Diagramm hängen bleiben."""

import plotly.graph_objects as go

import rkl_constants as C
import rkl_model as M
import rkl_results as R

BETA_SERIES = (("rand", "gemischt", "Rand, gemischt", "#2a6fb0"), ("rand", "getrennt", "Rand, getrennt", "#7fb0dc"),
               ("mitte", "gemischt", "Mitte, gemischt", "#c77700"), ("mitte", "getrennt", "Mitte, getrennt", "#e2a85a"))


def lock_axes(fig):
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


def _base(fig, height=360):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=-0.25), plot_bgcolor="rgba(0,0,0,0)")
    return lock_axes(fig)


def build_map(inst, routes):
    """Depot, Lieferkunden (Kreis) und Abholkunden (Quadrat, Größe = Menge), Touren. Strecken mit Last durchgezogen, Leerstrecken (Last 0) grau gestrichelt.
    Gleiches Seitenverhältnis über `scaleanchor` mit automatischem Bereich (zwei unsichtbare Eckmarker erzwingen den Rand)."""
    fig = go.Figure()
    for ri, r in enumerate(routes):
        if not r:
            continue
        color = C.COLOR_ROUTES[ri % len(C.COLOR_ROUTES)]
        loaded_x, loaded_y, empty_x, empty_y = [], [], [], []
        for a, b, _d, load in M.load_profile(inst, list(r)):
            xs, ys = [inst.xy[a][0], inst.xy[b][0], None], [inst.xy[a][1], inst.xy[b][1], None]
            if load > 0:
                loaded_x += xs
                loaded_y += ys
            else:
                empty_x += xs
                empty_y += ys
        if loaded_x:
            fig.add_trace(go.Scatter(x=loaded_x, y=loaded_y, mode="lines", line=dict(color=color, width=2.5), name=f"Tour {ri + 1}", hoverinfo="skip"))
        if empty_x:
            fig.add_trace(go.Scatter(x=empty_x, y=empty_y, mode="lines", line=dict(color=C.COLOR_EMPTY, width=2, dash="dash"), name="Leerstrecke (Last 0)" if ri == 0 else None,
                                     showlegend=ri == 0, legendgroup="leer", hoverinfo="skip"))
    max_dem = max(inst.dem[1:]) if inst.n else 1
    for kind, name, color, symbol in ((M.L, "Lieferkunde", C.COLOR_LIEFER, "circle"), (M.B, "Abholkunde", C.COLOR_ABHOL, "square")):
        ids = [c for c in range(1, inst.n + 1) if inst.kind[c] == kind]
        if ids:
            fig.add_trace(go.Scatter(
                x=[inst.xy[c][0] for c in ids], y=[inst.xy[c][1] for c in ids], mode="markers", name=name,
                marker=dict(color=color, symbol=symbol, size=[7 + 11 * inst.dem[c] / max_dem for c in ids], line=dict(color="white", width=1)),
                text=[f"Kunde {c}: {'Lieferung' if kind == M.L else 'Abholung'} {inst.dem[c]}" for c in ids], hovertemplate="%{text}<extra></extra>"))
    fig.add_trace(go.Scatter(x=[inst.xy[0][0]], y=[inst.xy[0][1]], mode="markers", name="Depot", marker=dict(color=C.COLOR_DEPOT, size=14, symbol="star"),
                             hovertemplate="Depot<extra></extra>"))
    fig.add_trace(go.Scatter(x=[-2, 102], y=[-2, 102], mode="markers", marker=dict(opacity=0, size=1), showlegend=False, hoverinfo="skip"))
    fig.update_xaxes(showgrid=False, zeroline=False, showticklabels=False)
    fig.update_yaxes(showgrid=False, zeroline=False, showticklabels=False, scaleanchor="x", scaleratio=1)
    return _base(fig, 440)


def build_stairs(steps):
    """Distanz je Stufe auf der Instanz (Balken, Beschriftung als Text)."""
    labels = [C.STAGE_SHORT[s.key] for s in steps]
    fig = go.Figure(go.Bar(x=labels, y=[s.dist / M.SCALE for s in steps], marker_color=[C.STAGE_COLORS[s.key] for s in steps],
                           text=[f"{s.dist / M.SCALE:.1f}".replace(".", ",") for s in steps], textposition="outside", hovertemplate="%{x}: %{y:.1f}<extra></extra>"))
    top = max(s.dist for s in steps) / M.SCALE
    fig.update_yaxes(title_text="Gesamtdistanz (Längeneinheiten)", range=[0, max(1.0, top * 1.12)])
    fig.update_xaxes(title_text="Planungsart")
    return _base(fig, 330)


def build_stage_means():
    """Mittel der Distanzersparnis gegen S je Stufe, Depot Rand und Mitte (alle 900 Instanzen des Hauptrasters je Depot, eigene Suche)."""
    fig = go.Figure()
    for depot, color in (("rand", "#2a6fb0"), ("mitte", "#c77700")):
        st = R.stage_means(depot)
        ys = [st["dD_S1"], st["dD_A"], st["dD_M"]]
        fig.add_trace(go.Bar(x=["S1", "A", "M"], y=ys, name=f"Depot {'am Rand' if depot == 'rand' else 'in der Mitte'}", marker_color=color,
                             text=[f"{y:.1f}".replace(".", ",") for y in ys], textposition="outside", hovertemplate="%{x}: %{y:.1f} %<extra></extra>"))
    fig.update_layout(barmode="group")
    fig.update_yaxes(title_text="Ersparnis gegen S (%)", range=[0, 35])
    fig.update_xaxes(title_text="Planungsart")
    return _base(fig, 330)


def build_beta_curve(nach_rows):
    """Umgekehrtes U über β (Nachmessung, n = 20, K_L = 2, eigene Suche): Zellmittel von ΔD je Depot und Lage."""
    fig = go.Figure()
    for depot, layout, label, color in BETA_SERIES:
        rows = sorted((r for r in nach_rows if r["depot"] == depot and r["layout"] == layout), key=lambda r: r["beta"])
        if not rows:
            continue
        fig.add_trace(go.Scatter(x=[r["beta"] for r in rows], y=[r["dD"][0] for r in rows], mode="lines+markers", name=label, line=dict(color=color, width=2),
                                 error_y=dict(type="data", array=[r["dD"][1] for r in rows], visible=True, thickness=1),
                                 hovertemplate=label + ": %{y:.1f} % (β = %{x})<extra></extra>"))
    fig.update_xaxes(title_text="Anteil der Abholkunden β", tickvals=sorted({r["beta"] for r in nach_rows}))
    fig.update_yaxes(title_text="Ersparnis ΔD (%)", range=[0, 32])
    return _base(fig, 380)


def build_spread():
    """Mittel von ΔD je Parameterwert über die Zellen (Hauptraster, Depot am Rand, beste bekannte Lösung)."""
    pm = R.main_param_means()
    names = {"beta": "β", "layout": "Lage", "K_L": "Knappheit K_L", "n": "n"}
    label_of = {0.2: "0,2", 0.4: "0,4", 0.6: "0,6", "gemischt": "gemischt", "ueberlappend": "überlappend", "getrennt": "getrennt", 2: "2", 4: "4", 20: "20", 40: "40"}
    colors = {"beta": "#2a6fb0", "layout": "#2a8f5b", "K_L": "#c77700", "n": "#8a4fb0"}
    fig = go.Figure()
    for param in ("beta", "layout", "K_L", "n"):
        means = pm[param]["means"]
        keys = ["gemischt", "ueberlappend", "getrennt"] if param == "layout" else sorted(means)
        fig.add_trace(go.Bar(x=[f"{names[param]}: {label_of[k]}" for k in keys], y=[means[k] for k in keys], name=names[param], marker_color=colors[param],
                             text=[f"{means[k]:.1f}".replace(".", ",") for k in keys], textposition="outside", hovertemplate="%{x}: %{y:.1f} %<extra></extra>"))
    fig.update_yaxes(title_text="Mittel von ΔD (%)", range=[0, 35])
    fig.update_layout(showlegend=False)
    return _base(fig, 340)


def build_r_cells(depot):
    """Anteil R der A-Ersparnis, den S1 holt, je Zelle (36 Zellen), mit den Schwellen 0,5 und 0,8."""
    cs = sorted(R.cells(depot), key=lambda c: c["ci"])
    fig = go.Figure(go.Bar(x=[c["ci"] for c in cs], y=[c["R"] for c in cs], marker_color=[C.STAGE_COLORS["S1"] if c["R"] > C.R_DEUTLICH_ZURUECK else "#9aa5b4" for c in cs],
                           hovertemplate="Zelle %{x}: R = %{y:.2f}<extra></extra>"))
    fig.add_hline(y=C.R_DEUTLICH_ZURUECK, line_dash="dot", line_color="rgba(128,128,128,0.8)")
    fig.add_hline(y=C.R_FAST_ALLES, line_dash="dot", line_color="rgba(192,57,43,0.8)")
    fig.update_xaxes(title_text="Zelle (0 bis 35)", tickvals=list(range(0, 36, 5)))
    fig.update_yaxes(title_text="R = ΔD(S→S1) / ΔD(S→A)", range=[0, 1])
    return _base(fig, 320)
