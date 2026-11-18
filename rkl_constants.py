"""Konstanten: Regler-Stufen, feste Annahmen, Farben und Presets.

Alle Regler stehen auf gemessenen Stufen (Hauptraster der Messreihe: 36 Zellen je Depot), damit zu jeder Einstellung eine vorgerechnete Zelle gehört."""

N_OPTIONS = (20, 40)
DEFAULT_N = 20
BETA_OPTIONS = (0.2, 0.4, 0.6)
DEFAULT_BETA = 0.4
LAYOUT_OPTIONS = ("gemischt", "ueberlappend", "getrennt")
DEFAULT_LAYOUT = "gemischt"
LAYOUT_LABELS = {"gemischt": "Gemischt", "ueberlappend": "Überlappend", "getrennt": "Getrennt"}
LAYOUT_HELP = {
    "gemischt": "Lieferkunden und Abholkunden liegen im ganzen Gebiet durcheinander.",
    "ueberlappend": "Lieferkunden eher links (x bis 70), Abholkunden eher rechts (x ab 30); die Zonen überlappen.",
    "getrennt": "Lieferkunden links (x bis 45), Abholkunden rechts (x ab 55): zwei getrennte Zonen.",
}
DEPOT_OPTIONS = ("rand", "mitte")
DEFAULT_DEPOT = "rand"
DEPOT_LABELS = {"rand": "Am Rand (50, 0)", "mitte": "In der Mitte (50, 50)"}
K_OPTIONS = (2, 4)
DEFAULT_K = 2
ILS_OPTIONS = (300, 1000)
DEFAULT_ILS = 300
ILS_LABELS = {300: "300 Iterationen (schnell)", 1000: "1 000 Iterationen (wie die Messreihe)"}
MEASURE_ILS = 1000                       # Iterationen der eigenen Suche in der vorgerechneten Messreihe
SEED_MAX, DEFAULT_SEED = 999999, 500018   # Messreihen: 1000-1011 (Abstimmung), 100000-103599 (Hauptraster), 200000+ (Nachmessung), 300000+ (Mengen-Raster)

CAP_FACTOR = 1.1                          # Q = Kapazitätsfaktor mal Summe der Lieferungen durch K_L
DEM_RANGE = (5, 25)                       # Mengen gleichverteilt ganzzahlig 5 bis 25 (Lieferung wie Abholung)

ORTOOLS_SECONDS = {20: 3, 40: 6}          # Zeitlimit je OR-Tools-Lauf (wie in der Messreihe)
EXACT_SECONDS = 40                        # CP-SAT, ein Worker (wie in der Messreihe)
EXACT_N_MAX = 20                          # exakt nur für n = 20 (bei n = 40 nicht gemessen, kein Beweis zu erwarten)

# Meldung in drei Zuständen aus dem Zellmittel der Distanzersparnis (S -> A) in Prozent; Schwellen gesetzt, nicht hergeleitet
LEVEL_WENIG = 10.0                        # unter 10 %: "lohnt wenig"
LEVEL_SEHR = 25.0                         # ab 25 %: "lohnt sehr"; dazwischen "lohnt deutlich"
R_DEUTLICH_ZURUECK = 0.5                  # Anteil R der A-Ersparnis, den S1 holt: höchstens 0,5 = "S1 deutlich zurück" (Schwelle der Restmessung AP 0)
R_FAST_ALLES = 0.8                        # mindestens 0,8 = "S1 holt fast alles"

STAGE_KEYS = ("S", "S1", "A", "M")
STAGE_LABELS = {"S": "S: getrennt", "S1": "S1: eine Rückladung je Tour", "A": "A: VRPB (Lieferung, dann Abholung)", "M": "M: gemischt"}
STAGE_SHORT = {"S": "S", "S1": "S1", "A": "A", "M": "M"}
STAGE_COLORS = {"S": "#9aa5b4", "S1": "#c77700", "A": "#2a6fb0", "M": "#2a8f5b"}
COLOR_LIEFER = "#2a6fb0"
COLOR_ABHOL = "#c77700"
COLOR_DEPOT = "#1c2430"
COLOR_EMPTY = "rgba(150,150,150,0.8)"
COLOR_ROUTES = ("#2a6fb0", "#c0392b", "#2a8f5b", "#8a4fb0", "#c77700", "#00897b", "#6d4c41", "#d81b60", "#5c6bc0", "#7cb342", "#f4511e", "#3949ab")

PRESETS = {
    "Standard": {"n": 20, "beta": 0.4, "layout": "gemischt", "depot": "rand", "k": 2, "ils": 300, "seed": 500018},
    "Viel Rückladung, knapper Laderaum": {"n": 20, "beta": 0.6, "layout": "gemischt", "depot": "rand", "k": 4, "ils": 300, "seed": 500002},
    "Wenig Rückladung, getrennte Zonen": {"n": 40, "beta": 0.2, "layout": "getrennt", "depot": "rand", "k": 4, "ils": 300, "seed": 500020},
    "Große Leerkilometer-Wirkung": {"n": 40, "beta": 0.6, "layout": "gemischt", "depot": "rand", "k": 4, "ils": 300, "seed": 500018},
    "Depot in der Mitte": {"n": 20, "beta": 0.4, "layout": "getrennt", "depot": "mitte", "k": 2, "ils": 300, "seed": 500001},
    "Wenig Rückladung, Depot Mitte": {"n": 40, "beta": 0.2, "layout": "getrennt", "depot": "mitte", "k": 2, "ils": 300, "seed": 500018},
}
PRESET_HELP = {
    "Standard": "20 Kunden, 40 % Abholkunden, gemischte Lage, Depot am Rand, zwei Liefertouren in S: Rückladung spart mehr als ein Viertel der Distanz.",
    "Viel Rückladung, knapper Laderaum": "20 Kunden, 60 % Abholkunden, knapper Laderaum (vier Liefertouren in S): die größte gemessene Ersparnis des Hauptrasters.",
    "Wenig Rückladung, getrennte Zonen": "40 Kunden, nur 20 % Abholkunden in einer eigenen Zone: die kleinste gemessene Ersparnis des Hauptrasters, immer noch deutlich.",
    "Große Leerkilometer-Wirkung": "40 Kunden, 60 % Abholkunden, gemischte Lage: die Leerkilometer fallen relativ am stärksten (84 %).",
    "Depot in der Mitte": "Gleiche Kundenzahl wie der Standard, aber getrennte Zonen und das Depot in der Mitte: die Randlage hat die Zahlen größer gemacht.",
    "Wenig Rückladung, Depot Mitte": "40 Kunden, 20 % Abholkunden in eigener Zone, Depot in der Mitte: die kleinste Ersparnis der 72 Zellen des Hauptrasters (beider Depots), hier lohnt Rückladung wenig.",
}
