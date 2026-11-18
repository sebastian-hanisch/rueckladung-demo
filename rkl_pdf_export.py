"""Tourenplan als PDF (fpdf2, Standardschriften). Sonderzeichen werden vorher bereinigt: Gedankenstrich, Minuszeichen, Euro, Anführungszeichen,
Pfeile und Emoji stürzen die Standardschriften sonst ab (DEMO-PLAYBOOK, fpdf2-Falle)."""

from fpdf import FPDF

import rkl_constants as C
import rkl_evaluation as E
import rkl_model as M

_REPLACE = {"–": "-", "—": "-", "−": "-", "€": "EUR", "„": '"', "“": '"', "”": '"', "‚": "'", "‘": "'", "’": "'", "→": "->", "×": "x", "±": "+/-",
            "≤": "<=", "≥": ">=", "·": "-", "…": "...", "β": "beta", "Δ": "Delta"}


def clean(text: str) -> str:
    """Nur Zeichen der Standardschrift (Latin-1) behalten; bekannte Sonderzeichen ersetzen, Unbekanntes (Emoji) streichen."""
    for old, new in _REPLACE.items():
        text = text.replace(old, new)
    return text.encode("latin-1", "ignore").decode("latin-1")


def build_pdf(settings: E.Settings, a: E.Analysis, step_key: str = "A") -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(0, 9, clean("Rückladung: Tourenplan"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 5, clean(
        f"{settings.n} Kunden, {round(100 * settings.beta)} % Abholkunden, Lage {C.LAYOUT_LABELS[settings.layout].lower()}, Depot {E.depot_text(settings.depot)}, "
        f"Laderaum so, dass die getrennte Planung etwa {settings.k} Lieferfahrten braucht (Kapazität {a.inst.Q}), Zufalls-Seed {settings.seed}, "
        f"Rechenbudget eigene Suche {settings.ils} Iterationen."), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Planungsarten auf dieser Instanz", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 9)
    widths = (66, 28, 20, 36, 30)
    for w, h in zip(widths, ("Planungsart", "Distanz", "Touren", "Leerkm-Anteil (%)", "Rechenzeit (s)")):
        pdf.cell(w, 6, h, border=1)
    pdf.ln()
    pdf.set_font("Helvetica", "", 9)
    for s in a.steps:
        for w, v in zip(widths, (s.label, E.km(s.dist), str(s.vehicles), f"{E.empty_share(s):.1f}".replace(".", ","), f"{s.seconds:.2f}")):
            pdf.cell(w, 6, clean(v), border=1)
        pdf.ln()
    step = E.step_of(a, step_key)
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, clean(f"Touren: {step.label} (Distanz {E.km(step.dist)})"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    for ri, route in enumerate(step.routes):
        stops = []
        for c in route:
            kind = "Lieferung" if a.inst.kind[c] == M.L else "Abholung"
            stops.append(f"K{c} ({kind} {a.inst.dem[c]})")
        peak = max(load for _a, _b, _d, load in M.load_profile(a.inst, list(route)))
        pdf.multi_cell(0, 5, clean(f"Tour {ri + 1} (Länge {E.km(M.route_len(a.inst.D, list(route)))}, größte Last {peak} von {a.inst.Q}): Depot - " + " - ".join(stops) + " - Depot"),
                       new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(0, 4, clean("Eine Instanz, kein Beleg: die Aussagen der Demo stützen sich auf die vorgerechnete Messreihe (25 Instanzen je Zelle, 36 Zellen je Depot)."),
                   new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
