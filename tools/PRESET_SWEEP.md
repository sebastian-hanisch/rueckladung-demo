# Preset-Abstimmung: Zufalls-Seeds der Presets

Aufruf: `python tools/find_preset_seeds.py 24 8` (je Preset 24 Zufalls-Seeds ab 500000, acht Prozesse, Rechenbudget 300 Iterationen wie in den Presets). Bedingung ist die Geschichte
des Presets auf der angezeigten Instanz (`rkl_stories.py`, bewusst grob); gewählt wurde aus den passenden Seeds der, dessen Ersparnisse am nächsten an den Zellmitteln der Messreihe liegen
(Zellmittel aus `data/rkl_results.json`, eigene Suche mit 1 000 Iterationen). Messbereiche der Zufalls-Seeds: 1000 bis 1011 (Abstimmung), 100000 bis 103599 (Hauptraster), 200000 aufwärts
(Nachmessung), 300000 aufwärts (Mengen-Raster); gesucht wurde ab 500000.

| Preset | passende Seeds (von 24) | gewählter Zufalls-Seed | S1 / A / M gegen S auf der Instanz (%) | Zellmittel S1 / A / M (%) |
|---|---|---|---|---|
| Standard | 23 | 500018 | 10,4 / 27,6 / 39,7 | 8,2 / 27,2 / 36,8 |
| Viel Rückladung, knapper Laderaum | 22 | 500002 | 20,3 / 33,6 / 34,7 | 21,6 / 33,5 / 34,5 |
| Wenig Rückladung, getrennte Zonen | 22 | 500020 | 0,0 / 13,9 / 13,9 | 0,5 / 14,0 / 14,1 |
| Große Leerkilometer-Wirkung | 23 | 500018 | 9,5 / 33,4 / 35,9 | 10,2 / 33,4 / 36,6 |
| Depot in der Mitte | 21 | 500001 | 2,9 / 14,1 / 14,1 | 2,4 / 13,1 / 13,1 |
| Wenig Rückladung, Depot Mitte | 21 | 500018 | 0,0 / 7,1 / 7,1 | 0,0 / 6,9 / 7,0 |

Hinweis: Die Spalte „auf der Instanz“ ist eine Instanz und kein Beleg; die Aussagen der Demo stützen sich auf die Messreihe. Die Zahlen der Tabelle stammen aus einem Lauf des Suchwerkzeugs
(Zufalls-Seed, 300 Iterationen) und stehen so nicht in den Tests; `tests/test_presets.py::test_die_instanz_jedes_presets_zeigt_ihre_geschichte` prüft für jedes Preset die Geschichte live.
