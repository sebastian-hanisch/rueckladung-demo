# Rückladung: wie viel Leerfahrt verschwindet? – Streamlit-Demo

<!-- TODO nach dem Deploy: direkt hierher den Live-Link setzen (Leerzeile davor und danach):
**[→ Demo live ausprobieren](https://sebastianhanisch-rueckladung-demo.streamlit.app/)** -->

Fall-Demo für die Website „Sebastian Hanisch – Operations Research und Machine Learning“ (`demos.html`, Gruppe „Transport & Tourenplanung“). Lkw liefern aus und fahren leer zurück. Liegen **Abholkunden** (Rückladung, Leergut, Retouren) auf dem Rückweg, befördert dieselbe Fahrt Last in beide Richtungen: erst alle Lieferkunden, danach Abholkunden (**VRP mit Rückladungen**, Backhauls). Die Demo rechnet live auf **einer Instanz** vier Planungsarten, **S** (getrennt), **S1** (ein Abholkunde je Tour), **A** (VRPB, Lieferung vor Abholung) und **M** (gemischt), mit einer eigenen Suche; OR-Tools und der exakte Löser CP-SAT (nur 20 Kunden, nur S und A) laufen auf Knopfdruck. Die Aussagen stützen sich auf eine **vorgerechnete Messreihe** (36 Zellen je Depot, je 25 Instanzen, Zufalls-Seeds ab 100000).

## Warum dieses Problem

Rückladung ist die naheliegende Antwort auf Leerfahrten, und die Fluss-Variante („Rückladungen finden“ als Bestandsausgleich im Zeit-Raum-Netz) steckt schon in `leercontainer-demo`. Die Routing-Variante, bei der die Reihenfolge Lieferung vor Abholung zählt, war im Portfolio bisher offen. Die Kernfrage: **Wie viel Distanz, wie viele Touren und Leerkilometer spart Rückladung, wovon hängt die Höhe ab, und wie viel davon steckt nur im strengen Vergleichsmaßstab?** Ein „Wo kippt es?“ gibt die Messung nicht her (siehe Befunde: keine Zelle ohne Ersparnis); der Aufhänger sind darum die Höhe und der Maßstab.

## Modell

Depot, `n` Kunden (20 oder 40) im 100 × 100-Gebiet, davon ein Anteil β Abholkunden (Abholung nimmt Last auf), der Rest Lieferkunden (Lieferung nimmt Last ab). Mengen gleichverteilt ganzzahlig 5 bis 25, Kapazität `Q = ⌈1,1 · Σ Lieferungen / K_L⌉` (mindestens die größte Einzelmenge; `K_L` = 2 oder 4 steuert die Knappheit der Lieferlast), unbegrenzte Flotte, euklidische Entfernungen auf 0,1 Längeneinheiten gerundet, Ziel Gesamtdistanz. Lieferung und Abholung belegen getrennte Last (je Tour Summe der Lieferungen ≤ `Q` und Summe der Abholungen ≤ `Q`). Lagen: gemischt, überlappend, getrennt (Lieferkunden links, Abholkunden rechts). Das Depot liegt am Rand (50, 0) oder in der Mitte (50, 50).

| Planungsart | Regel |
|---|---|
| **S** | Touren rein Lieferung oder rein Abholung (Abholkunden fahren in S nie auf einer Liefertour mit, sondern nur in reinen Abholtouren; mehrere Abholkunden je Abholtour möglich) |
| **S1** | eine Lieferstour darf nach den Lieferkunden **höchstens einen** Abholkunden bedienen; weitere nur in reinen Abholtouren |
| **A** (VRPB) | auf jeder Tour erst alle Lieferkunden, dann beliebig viele Abholkunden |
| **M** | beliebige Reihenfolge; die Last auf jeder Teilstrecke (noch auszuliefern plus bereits abgeholt) darf `Q` nicht überschreiten |

S ⊂ S1 ⊂ A ⊂ M: im Optimum gilt Distanz(S) ≥ Distanz(S1) ≥ Distanz(A) ≥ Distanz(M). **Leerkilometer** sind Strecke mit Last 0 (Rückweg nach der letzten Lieferung ohne Abholung, Hinweg einer reinen Abholtour, auch die Strecke von der letzten Lieferung zum ersten Abholkunden). Formeln im 📐-Expander der App.

## Methodik

- **Eigene Suche** (Ruin-and-Recreate mit Relocate, Swap, 2-opt und 2-opt\*, Annahme nach Record-to-Record 0,4 %): S und A mit Start Clarke-Wright je Art; S1 und M mit der allgemeinen Fassung, Start jeweils mit der Lösung der engeren Stufe (A zusätzlich von S1 aus, M zusätzlich von S aus, die bessere Lösung zählt). So gilt die Reihenfolge der Distanzen auf jeder Instanz. 1 000 Iterationen in der Messreihe; die App rechnet live mit 300 oder 1 000.
- **OR-Tools** (Routing, Guided Local Search) für S und A in zwei Einstellungen: Standard (Erststrategie PATH_CHEAPEST_ARC) und SAVINGS. Zusatzoperatoren und Warmstart machten OR-Tools in der Abstimmung schlechter und gehören nicht dazu.
- **CP-SAT** (Mehrfach-Kreis) für S (in zwei CVRP zerlegt) und A bei 20 Kunden, 40 s, ein Worker, Warmstart aus der eigenen Suche; immer mit Status „bewiesen / nicht bewiesen“.
- **Messreihe:** das Hauptraster der Vormessung (36 Zellen, Depot am Rand, beste bekannte Lösung aller Verfahren, nur S und A), die Restmessung AP 0 (alle vier Stufen, beide Depots, nur eigene Suche), eine Nachmessung der Extremwerte von β und ein Zusatzraster mit ungleichen Mengen. Die Rohdaten liegen nicht im Repo; `tools/dump_results.py` verdichtet sie zu `data/rkl_results.json` (unter 150 kB), aus dem App und Tests alle Zahlen lesen.

## Befunde (gemessen, keine Behauptungen)

Alle Zahlen stehen in `data/rkl_results.json` und sind in `tests/test_claims.py` nachgerechnet (Testname in der letzten Spalte). „Hauptmessreihe“: Depot am Rand, beste bekannte Lösung; „AP 0“: eigene Suche mit 1 000 Iterationen, je Depot 900 Instanzen. Zelle n steht für die Zellennummer 0 bis 35.

| Frage | Befund (Voraussetzung) | Test |
|---|---|---|
| Spart A Distanz gegen S? | **In allen 900 Instanzen** (Hauptmessreihe, 36 Zellen mit je 25 Instanzen, A gleich S in keiner). Zellmittel von 14,1 % (Zelle 21: n = 40, β = 20 %, getrennt, K_L = 4) bis 33,5 % (Zelle 13: n = 20, β = 60 %, gemischt, K_L = 4), Mittel über alle Instanzen 23,9 %. | `test_claim_a_spart_in_allen_900_instanzen` |
| Touren und Leerkilometer? | Hauptmessreihe: Zellmittel der Ersparnis an Touren 21,6 bis 48,0 %, an Leerkilometern 35,4 bis 84,0 %; in allen 36 Zellen mindestens 15 % Touren. Die Hypothese der Vormessung „spart Fahrzeuge, kaum Kilometer“ ist damit widerlegt. | `test_claim_touren_und_leerkilometer` |
| Gibt es eine Grenze, an der es kippt? | **Im gemessenen Raster nein** (Depot am Rand, β 20 bis 60 %, gleichverteilte Mengen, unbegrenzte Flotte): in keiner der 36 Zellen liegt das Zellmittel unter 2 % (0 von 36 Zellen), in allen mindestens 5 % (36 von 36), kleinstes Zellenmittel 14,1 %. Ampel der Vormessung: gelb („lohnt fast überall“). | `test_claim_keine_zelle_ohne_ersparnis` |
| Wovon hängt die Höhe ab? | Mittel von ΔD je Parameterwert (Hauptmessreihe, über die Zellen): β 18,2 / 25,6 / 27,9 % bei 20 / 40 / 60 % (Spreizung 9,7 Prozentpunkte, die größte); Lage gemischt 25,8, überlappend 25,0, getrennt 21,0 % (4,8 Pp); K_L 22,2 gegen 25,6 % (3,3 Pp); n 25,4 gegen 22,4 % (3,0 Pp). | `test_claim_hebel` |
| Hängt es am Löser? | Das Mittel hängt nicht am Löser: Mittel von ΔD 23,90 % aus der besten Lösung, 23,82 % nur aus den OR-Tools-Läufen, 23,89 % nur aus der eigenen Suche (Hauptmessreihe; Abweichung der OR-Tools-Läufe 0,1 Prozentpunkte im Mittel, je Zelle und je Instanz nicht ausgewertet). | `test_claim_loeser_unabhaengig` |
| Wie gut ist die eigene Suche? | Gegen bewiesene Optima bei n = 20: Lücke 0,026 % in S (optimal in 151 von 153 bewiesenen Instanzen) und 0,030 % in A (251 von 258); OR-Tools in S 0,52 % (Standard) und 0,36 % (SAVINGS), in A 0,35 % (Standard) und 0,37 % (SAVINGS). Gegen die beste bekannte Lösung bei n = 40 (die zum Teil aus der eigenen Suche stammt): eigene Suche 0,01 % (S) und 0,04 % (A), OR-Tools 1,19 bis 1,68 % (je 6 s). Bei n = 20 beweist CP-SAT nur einen Teil der Instanzen (siehe nächste Zeile): die Lücke ist nur dort belegt. | `test_claim_loeserguete` |
| Wie weit beweist CP-SAT? | Bei n = 20 (40 s, ein Worker, S in zwei CVRP zerlegt mit je 20 s, Warmstart aus der besten bis dahin bekannten Lösung, je 450 Instanzen): S in 153, A in 258. Wo nicht bewiesen, liegt die Schranke im Mittel 34,39 % (S) und 42,55 % (A) unter der besten Lösung (bezogen auf die beste Lösung; höchstens 55,90 % und 62,65 %): die Schranke sagt dann wenig. | `test_claim_cp_sat` |
| Wie viel holt die einfachste Zulassung S1? (AP 0, Depot am Rand) | Im Mittel 7,4 % von 23,9 % (S1 gegen A, beide gegen S), also rund ein Drittel (R = 0,31). R ≤ 0,5 in 29 von 36 Zellen, R ≥ 0,8 in 0, Median 0,26, größte Zelle 1 (n = 20, β = 20 %, gemischt, K_L = 4) mit 0,799 (knapp unter der Schwelle 0,8). Urteil nach den vorab festgelegten Schwellen (mindestens 24 von 36 Zellen): **S1 deutlich zurück**. | `test_claim_s1` |
| Dasselbe mit dem Depot in der Mitte | S1 6,3 % von 17,4 %; R ≤ 0,5 in 28 von 36 Zellen, R ≥ 0,8 in 1; Urteil gleich. R steigt bei kleinerem n und knapperem Laderaum (n = 20: 0,40, n = 40: 0,17; K_L = 2: 0,18, K_L = 4: 0,39; Depot am Rand) und ist bei getrennten Zonen am kleinsten (0,19 gegen 0,35 gemischt). | `test_claim_s1_mitte_und_treiber` |
| Was bringt M? (AP 0, Depot am Rand) | A gegen M im Mittel 4,2 % (Mitte 5,5 %); in 19 von 36 Zellen mindestens 2 % (Mitte 23), in 14 unter 1 % (Mitte 13): **M bringt etwas**. Nach Lage: gemischt 8,5 %, überlappend 4,0 %, getrennt 0,0 % (Mitte 10,7 / 5,7 / 0,0 %); bei getrennten Zonen ist M fast immer gleich A (Depot am Rand und in der Mitte je 282 von 300 Instanzen gleich, Mittel von A gegen M 0,03 %); in den Zellen 2, 8, 14, 15 und 27 ist es in allen 25 Instanzen gleich A. Größte Zelle 24 (n = 40, β = 40 %, gemischt, K_L = 2) mit 19,3 %. | `test_claim_m` |
| Das Depot? (AP 0) | Mit dem Depot in der Mitte sinkt die A-Ersparnis von 23,9 % auf 17,4 % (im Mittel 6,5 Prozentpunkte; die Mitte liegt in 0 von 36 Zellen höher, die Differenz reicht von 1,5 bis 11,2 Pp); kleinster Zellenmittelwert 6,9 % (Zelle 20: n = 40, β = 20 %, getrennt, K_L = 2). | `test_claim_depot` |
| Form über β? (Nachmessung, n = 20, K_L = 2, eigene Suche, 15 Instanzen je Punkt) | Unter den fünf gemessenen Punkten (β = 0,05; 0,1; 0,4; 0,8; 0,9) ist 0,4 in allen 6 Reihen (Depot Rand und Mitte, drei Lagen) der höchste; die Hauptmessreihe zeigt bei β = 0,6 noch höhere Werte, das Maximum liegt also zwischen 0,4 und 0,8. Nach beiden Seiten fällt die Ersparnis, geht aber nirgends auf null, kleinster Zellenmittelwert 4,9 % (Depot Mitte, getrennt, β = 0,9); 30 Zellen mit je 15 Instanzen, 450 Instanzen. Die Nachmessung war nicht vorab festgelegt. | `test_claim_nachmessung` |
| Ungleiche Mengen? (AP 0, nur Bericht, n = 20, 12 Zellen, je 25 Instanzen, andere Instanzen als im Hauptraster) | Kleine Abholmengen (2 bis 10): S1 5,6 % von 21,8 %, A gegen M 3,8 %. Große (15 bis 40): S1 14,9 % von 24,8 %, R = 0,60 (R ≥ 0,8 in 3 von 12 Zellen, R ≤ 0,5 in 6), A gegen M 1,8 %. Gegenüber denselben 12 Zellen des Hauptrasters (AP 0, Depot am Rand: S1 9,9 %, A 24,9 %, R 0,40) heben große Abholmengen vor allem den S1-Anteil (R 0,40 auf 0,60, S1 +5,0 Pp, A 0,0 Pp (−0,05)); kleine senken S1 und A ähnlich stark (S1 −4,3, A −3,1 Pp). | `test_claim_ungleiche_mengen` |
| Welcher Zustand der ersten Meldung wie oft? | Zellmittel unter 10 % („lohnt wenig“), 10 bis unter 25 % („deutlich“), ab 25 % („sehr“): Depot am Rand 0 / 20 / 16 von 36 Zellen, Depot in der Mitte 3 / 28 / 5 (Schwellen gesetzt, nicht hergeleitet). | `test_claim_zustaende` |
| Rechenzeit je Stufe (lokal, ein Prozess, 5 Instanzen: n, β = 40 %, gemischt, K_L = 2) | n = 20: 0,15 bis 0,17 s bei 300, 0,49 bis 0,56 s bei 1 000 Iterationen; n = 40: 0,41 bis 0,47 s und 1,36 bis 1,51 s (Mittel je Stufe). Eine Messung dieses Entwicklungsrechners; auf anderen Rechnern, auch auf Streamlit Cloud, anders. | `test_claim_zeiten` |

## Befunde und Korrekturen gegenüber dem Plan

- **Hypothesen der Vormessung widerlegt:** „Backhaul spart Fahrzeuge, kaum Kilometer“ (beides sinkt deutlich) und „keine Ersparnis bei β nahe 0 oder 1“ (widerlegt für β = 0,05 bis 0,9, n = 20, K_L = 2: in der Nachmessung kleinster Zellenmittelwert 4,9 %, A gleich S in keiner Instanz; bei β = 0 und β = 1 gibt es nichts zu mischen).
- **Der strenge Maßstab erklärt nur einen kleineren Teil:** Vermutet war, dass ein großer Teil der Ersparnis nur „keine eigene Tour für wenige Rückladungen“ misst. Die Restmessung zeigt: S1 (höchstens ein Abholkunde je Lieferstour) holt im Mittel rund ein Drittel der A-Ersparnis (eher untere Grenze); der Rest entsteht erst durch mehrere Abholkunden auf einer Lieferstour. Das gilt streng nur für S1; andere Lockerungen von S sind nicht gemessen.
- **M ist das Minimum aus zwei Läufen** (Start bei A und Start bei S), nicht nur der Start bei A: die gemischte Suche bleibt aus der A-Lösung vermutlich in einer Nachbarschaft hängen (Deutung aus Funktionstests und diesen Zählungen, nicht gesondert geprüft). Der Start von S ist bei M in 31 von 900 Instanzen (Depot am Rand) und 29 von 900 (Depot in der Mitte) besser. Die Änderung kam vor dem ersten Sweep der Restmessung (Protokoll in deren Bericht). Test: `test_claim_m_start`.
- **Live-Rechenbudget:** Standard 300 Iterationen statt der 1 000 der Messreihe (die Zeit auf Streamlit Cloud ist nicht gemessen; die Kette der vier Stufen besteht aus sechs Läufen). Die vorgerechneten Zahlen stammen von 1 000 Iterationen; die Live-Zahlen stehen unter der Überschrift „eine Instanz“.
- **OR-Tools in zwei Einstellungen (Standard, SAVINGS) statt „abgestimmt“:** In der Abstimmung machten Zusatzoperatoren und Warmstart OR-Tools bei n = 40 und 6 s (12 Instanzen) schlechter als die Standard-Einstellung; „abgestimmt“ hieß darum nur Erststrategie SAVINGS.
- **Zwei Tabs mehr als im Plan:** OR-Tools und das exakte Verfahren haben nach DEMO-PLAYBOOK §2 eigene Tabs im Methodenvergleich (der Plan sah Knöpfe im Hauptbereich vor).
- **Depot als Regler** und Presets auf gemessenen Zellen: alle Regler stehen auf gemessenen Stufen, zu jeder Einstellung gehört eine Zelle (`rkl_results.nearest_cell`).
- **Preset-Zufalls-Seeds** liegen bei 500000 und darüber, außerhalb aller Messbereiche (1000 bis 1011 Abstimmung, 100000 bis 103599 Hauptraster, 200000 aufwärts Nachmessung, 300000 aufwärts Mengen-Raster); gesucht mit `tools/find_preset_seeds.py`.

## Ehrliche Grenzen

| Annahme | Was passiert, wenn sie verletzt ist |
|---|---|
| Depot am Rand (Hauptmessreihe) | Das Depot färbt die Höhe: in der Mitte ist die A-Ersparnis im Mittel 6,5 Prozentpunkte kleiner. Die App zeigt beide Depots; die Aussagen zu S und A der Hauptmessreihe gelten für das Depot am Rand. |
| S verbietet jede Mischung | S ist ein strenger Maßstab; S1 zeigt, wie viel die einfachste Zulassung holt (rund ein Drittel). Ein anderer Maßstab (etwa mehrere Abholkunden je Tour, aber getrennte Zonen) ist nicht gemessen. |
| Kein bewiesenes Optimum für S1 und M | Bei 20 und 40 Kunden gibt es dafür keinen exakten Löser; die Zuwächse von S1 und M sind eher Untergrenzen. Bei n = 8 trifft die Suche (150 Iterationen) in der Restmessung in 24 von 24 Instanzen das Optimum; bei n = 20 und 40 ist die Güte für S1 und M unbekannt; bei n = 6 prüft `tests/test_oracle_rueckladung.py` die Suche gegen eine Aufzählung. |
| M gewinnt aus zwei Quellen | Freie Reihenfolge und Wiederverwendung des Laderaums nach einer Auslieferung sind nicht getrennt gemessen. |
| Zufallsinstanzen, euklidisch, gleichverteilte Mengen 5 bis 25 | Große Abholmengen heben vor allem den S1-Anteil, kleine senken S1 und A ähnlich stark (siehe Befunde); nur n = 20, nur Bericht. Echte Straßennetze und Kundenlagen sind nicht gemessen. |
| Unbegrenzte Flotte, nur Distanz | Mit Fixkosten je Fahrzeug würde die absolute Ersparnis wachsen (die Touren sinken stark); mit begrenzter Flotte kann S unzulässig werden. Nicht gemessen. |
| Keine Zeitfenster, keine Servicezeit | Zeitfenster können die Mischung einschränken; nicht gemessen. |
| Nur 20 und 40 Kunden | Für größere Instanzen keine Aussage; die Güte der eigenen Suche ist nur bei 20 Kunden gegen bewiesene Werte geprüft. |
| Anteile der eigenen Suche am Besten | Die eigene Suche stellt meist die beste Lösung; ihre Lücke zum Optimum ist nur dort belegt, wo CP-SAT beweist (bei 20 Kunden in 153 von 450 Instanzen für S und 258 von 450 für A). |
| Rechenzeiten | Auf anderen Rechnern anders; OR-Tools und CP-SAT sind zeitlimitiert und nicht bitgleich reproduzierbar. Die Zeit auf Streamlit Cloud ist nicht gemessen. |
| Die Zustände der ersten Meldung | Die Schwellen 10 und 25 % sind gesetzt, nicht hergeleitet; eine einzelne Instanz kann vom Zellmittel stark abweichen (Zelle 6: Einzelinstanzen von 18,5 bis 34,8 %). |

## Tests

162 Tests (`pytest --collect-only -q tests`), Laufzeit lokal 36 bis 83 s mit `pytest tests -q -n 6` (zwei Messungen mit unterschiedlicher Rechnerlast, Python 3.14, Windows, sechs Prozesse). Zusammensetzung:

- **Orakel** (`tests/test_oracle_rueckladung.py`): eigene Aufzählung aller Reihenfolgen je Teilmenge mit eigener Zulässigkeitsregel, geprüft an drei Handbeispielen (S, S1, A, M von Hand gerechnet) und an 24 Kleinstinstanzen mit sechs Kunden; die eigene Suche liegt nie darunter und trifft das Optimum in mindestens 90 % der Fälle (Testschwelle); Monotonie S ≥ S1 ≥ A ≥ M im Optimum; CP-SAT gegen die Aufzählung; Kennzahlen gegen eine eigene Nachrechnung.
- **Kern** (`tests/test_algorithm.py`, `tests/test_edge_cases.py`, `tests/test_rng.py`): Handrechnung, Zulässigkeitsprüfer an jeder Art von Verstoß, Instanzerzeugung, Zonen, Reproduzierbarkeit, Randfälle, SplitMix64 gegen feste Werte und das Original.
- **Ergebnisse und Aussagen** (`tests/test_results.py`, `tests/test_claims.py`, `tests/test_verdicts.py`): jede Zahl dieser README und der App aus der Ergebnisdatei nachgerechnet, Verdikte an handgesetzten Werten, Schwellen der Zustände.
- **Presets und Oberfläche** (`tests/test_presets.py`, `tests/test_layout.py`, `tests/test_app.py`, `tests/test_pdf.py`, `tests/test_footer.py`, `tests/test_runtime_imports.py`): jedes Preset liegt auf einer gemessenen Zelle und zeigt auf seiner Instanz seine Geschichte; AppTest für jedes Preset, jede Stufe der Regler, die drei Zustände der ersten Meldung, OR-Tools und CP-SAT mit kurzen Zeitlimits, PDF, Permalink.

## Verifikation

- **Kern:** Handbeispiele (S 1000 / S1 600 / A 600 / M 600 und S 1200 / S1 1200 / A 800 / M 800), Aufzählungs-Orakel, Kennzahlen, unabhängiger Zulässigkeitsprüfer (`verify_mode`), Reproduzierbarkeit.
- **Kette gegen die Messreihe:** die Kette der App rechnet die Referenzinstanzen (Zufalls-Seed 100600, n = 20, 1 000 Iterationen, Depot am Rand und in der Mitte) im Band wie in der Messreihe neu (`test_claim_neu_rechnen_als_band`); im Entwicklungslauf stimmten alle Distanzen von S, S1, A und M auf vier Instanzen exakt überein.
- **Oberfläche:** AppTest, Layout (Schnellstart in der Seitenleiste, fester Kopf, aktives Preset hervorgehoben, jede Reglerstufe), Footer.

## Dateistruktur

| Datei | Zweck |
|---|---|
| `.github/workflows/tests.yml` | CI: Push, Pull Request, wöchentlicher Canary |
| `.gitignore` | venv, Caches, Streamlit-Secrets |
| `.streamlit/config.toml` | Streamlit-Einstellungen (keine Nutzungsstatistik) |
| `app.py` | Streamlit-App (Skelett nach DEMO-PLAYBOOK §2) |
| `data/rkl_results.json` | vorgerechnete Messreihe (72 Zellen, Hauptraster, Nachmessung, Zusatzraster, Löser, Zeiten, Referenzinstanzen) |
| `requirements.txt`, `requirements-dev.txt` | Laufzeit-Bibliotheken (ungepinnt) und dazu pytest |
| `rkl_constants.py` | Regler-Stufen, feste Annahmen, Schwellen, Farben, Presets |
| `rkl_evaluation.py` | Live-Analyse der vier Stufen, Kennzahlen, Verdikte als reine Funktionen |
| `rkl_layout.py` | Fester Kopf (Stylesheet) |
| `rkl_model.py` | Instanz, Zulässigkeit (`feas`, `verify_mode`), Lastverlauf, Kennzahlen |
| `rkl_pdf_export.py` | Tourenplan als PDF (fpdf2) |
| `rkl_presets.py` | Permalink (Begrenzen, Einrasten), Presets (Schnellstart, aktives Preset hervorgehoben), Zufalls-Seed-Button |
| `rkl_results.py` | Laden und Auswerten der Ergebnisdatei, Zellen-Zuordnung, Zustände, Zählungen |
| `rkl_rng.py` | SplitMix64 (Kopie aus `ab-test-demo`) |
| `rkl_search.py` | eigene Suche für S, S1, A, M, Savings, Kette (mechanisch aus der Messreihe übernommen) |
| `rkl_solvers.py` | OR-Tools und CP-SAT (aus der Messreihe übernommen) |
| `rkl_stories.py` | Abnahmekriterien der Presets |
| `rkl_visualization.py` | Plotly-Abbildungen (Achsen gesperrt) |
| `tools/dump_results.py` | erzeugt `data/rkl_results.json` aus den Rohdaten (Umgebungsvariable `RKL_RAW_DIR`) |
| `tools/find_preset_seeds.py` | sucht die Zufalls-Seeds der Presets |
| `tools/PRESET_SWEEP.md` | gewählte Zufalls-Seeds der Presets mit den Werten der Instanz und der Zellmittel |
| `tests/` | Orakel, Kern, Randfälle, Ergebnisse, Aussagen, Verdikte, Presets, Layout, AppTest, PDF, Footer, Laufzeit-Importe, Zufallsgenerator |

## Bewusst nicht umgesetzt

- **Fixkosten je Fahrzeug und begrenzte Flotte:** eigene Zusatzraster; sonst würde aus dem Verfahrensvergleich ein zweites Modell.
- **Ungleiche Mengen als Regler:** nur als Bericht gemessen (n = 20).
- **Zeitfenster, Servicezeiten, echte Entfernungsdaten, mehr als 40 Kunden.**
- **Ein exakter Löser für S1 und M** und die Trennung des M-Gewinns in Reihenfolge und Laderaum.
- **Kooperation mit Aufteilung, Abfahrtsregeln mit Fristen, Multi-Trip und Frachtbörsen** sind eigene Fragen und nicht Teil dieser Demo.

## Verwandte Demos mit demselben mathematischen Modell

Vor einer neuen Demo-Idee das Modell vergleichen, nicht die Kulisse (Stand 2026-11-18):

- [`leercontainer-demo`](https://github.com/sebastian-hanisch/leercontainer-demo): derselbe Gedanke (Leerfahrten durch Gegenverkehr füllen) als **Fluss** im Zeit-Raum-Netz (Min-Cost-Flow mit Vorschau-Fenster), ohne Touren und ohne Reihenfolge. Die Lkw-Variante dieses Flusses ist als Dopplung verworfen; die Routing-Variante mit Reihenfolge Lieferung vor Abholung ist diese Demo.
- [`vrp-demo`](https://github.com/sebastian-hanisch/vrp-demo) und [`vrp-nachbarschaften-demo`](https://github.com/sebastian-hanisch/vrp-nachbarschaften-demo): CVRP mit Lieferkunden und Verfahrensvergleich; `vrp-demo` nannte VRP mit Rückladungen ausdrücklich als offene Ausnahme.
- [`alns-demo`](https://github.com/sebastian-hanisch/alns-demo): dieselbe Verfahrensfamilie (Destroy und Repair) auf einem reinen CVRP, ohne Rückladung oder Abholung.
- [`rufbus-demo`](https://github.com/sebastian-hanisch/rufbus-demo) und [`patiententransport-demo`](https://github.com/sebastian-hanisch/patiententransport-demo): Pickup-and-Delivery, bei dem Abholung und Ziel zusammengehören (Paare); hier haben Abholkunden kein Ziel außer dem Depot.
- [`inventory-routing-demo`](https://github.com/sebastian-hanisch/inventory-routing-demo): Tourenbausteine mit Bestand beim Kunden über mehrere Tage; hier gibt es nur einen Tag und keinen Bestand.

## Lokal ausführen

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt
streamlit run app.py
```

## Tests ausführen

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Gebaut mit Streamlit, Plotly, pandas, OR-Tools und fpdf2.

---

Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). Mehr zum Thema: [Tourenplanung optimieren](https://sebastianhanisch.net/tourenplanung-optimierung.html).
