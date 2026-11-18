"""Abnahmekriterien der Presets: was die angezeigte Instanz jedes Presets qualitativ zeigen muss.

Die Aussage der Demo stützt sich auf die Messreihe (25 Instanzen je Zelle); ein Preset zeigt nur eine Instanz, die zur Geschichte passt. Die Kriterien sind
deshalb bewusst grob (Schwellen in Prozent) und prüfen die Instanz, nicht die Messreihe. Suche der Zufalls-Seeds: tools/find_preset_seeds.py
(Seeds ab 500000, nie 1000 bis 1011 der Abstimmung, 100000 bis 103599 des Hauptrasters, 200000 aufwärts der Nachmessung und 300000 aufwärts des Mengen-Rasters)."""

import rkl_evaluation as E


def _gain(a, key):
    """Ersparnis der Stufe gegenüber S in Prozent."""
    return E.saving(E.step_of(a, "S").dist, E.step_of(a, key).dist)


def story_standard(a):
    """Rückladung spart mehr als ein Achtel der Distanz und mindestens eine Tour; S1 holt nur einen Teil der A-Ersparnis."""
    return _gain(a, "A") >= 15.0 and E.step_of(a, "A").vehicles < E.step_of(a, "S").vehicles and _gain(a, "S1") <= 0.8 * _gain(a, "A")


def story_viel(a):
    """Viele Abholkunden und knapper Laderaum: mindestens ein Viertel Ersparnis und weniger Touren."""
    return _gain(a, "A") >= 25.0 and E.step_of(a, "A").vehicles < E.step_of(a, "S").vehicles


def story_wenig_getrennt(a):
    """Eigene Zone, wenige Abholkunden: Ersparnis zwischen 8 und 22 %, M bringt gegenüber A nichts (getrennte Zonen)."""
    return 8.0 <= _gain(a, "A") <= 22.0 and E.step_of(a, "A").dist - E.step_of(a, "M").dist <= 0.005 * E.step_of(a, "A").dist


def story_leerkm(a):
    """Gemischte Lage, viele Abholkunden: der Leerkilometer-Anteil fällt von S zu A auf höchstens die Hälfte."""
    s, aa = E.step_of(a, "S"), E.step_of(a, "A")
    return E.empty_share(aa) <= 0.5 * E.empty_share(s) and _gain(a, "A") >= 20.0


def story_mitte(a):
    """Depot in der Mitte, getrennte Zonen: kleine bis mittlere Ersparnis (5 bis 20 %), M gleich A."""
    return 5.0 <= _gain(a, "A") <= 20.0 and E.step_of(a, "A").dist - E.step_of(a, "M").dist <= 0.005 * E.step_of(a, "A").dist


def story_wenig_mitte(a):
    """Wenige Abholkunden in eigener Zone, Depot in der Mitte: höchstens 12 % Ersparnis, S1 holt (fast) nichts (höchstens 1 %)."""
    return _gain(a, "A") <= 12.0 and _gain(a, "S1") <= 1.0


STORIES = {
    "Standard": story_standard,
    "Viel Rückladung, knapper Laderaum": story_viel,
    "Wenig Rückladung, getrennte Zonen": story_wenig_getrennt,
    "Große Leerkilometer-Wirkung": story_leerkm,
    "Depot in der Mitte": story_mitte,
    "Wenig Rückladung, Depot Mitte": story_wenig_mitte,
}
