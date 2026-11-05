> Historischer Abschluss von Schritt 1. Der aktuelle Lieferstand einschließlich O2C steht in Endabnahme.md.

# Abnahme · ControllAI 2.1.0 · Schritt 1

Lokale Offline-Abnahme, 31.10.2026. Beide Python-Umgebungen wurden neu aus derselben uv.lock aufgebaut.
Messwerte sind lokale Beobachtungen auf diesem Mac, keine Laufzeitgarantie für beliebige Geräte.

| Befund | Maßnahme | Gemessener Wert |
|---|---|---|
| Erststart ≤ 12 s | Daten-/Berechnungscache; Exportbibliotheken erst bei Bedarf | 1,935 s |
| Folgelauf ≤ 1,0 s | Wiederverwendung deterministischer Ergebnisse | 0,118 s |
| Jahreswechsel ≤ 1,5 s | Cache mit Jahr, Dateistand und Einstellungen | 0,384 s |
| Testsuite ≤ 180 s | Regressionstest Folgelauf ≤ 3 s; alle vorhandenen Prüfzwecke erhalten | 3.11.18: 416 Tests, 29,36 s / 3.13.18: 416 Tests, 26,18 s |
| Zeitachse und Vorjahresvergleich | 2024/2025 vollständig, 2026 bis September; PY gleiche Quartale | 11 Quartale; 3 Quartale AC und 3 PY im YTD-Vergleich |
| Umsatzabweichung ≤ 0,5 % je Jahr/Produktgruppe | Feste Referenz aus VarianceAI, zusätzlich Regionen geprüft | 18 Referenzen · maximal 0,00 % · 0 Cent |
| Kanonische Bezeichnungen | Suite-Stamm für Produkte, Regionen, Kunden, Materialien, Kostenstellen | Keine abweichende Produktbezeichnung; Daten-/UI-/Exporttest bestanden |
| Deutsche Tabellen und Zahlen | Anzeigegrenze, Namen mit Nummern, Diagramme in T€ | 0 Unterstriche in geprüften sichtbaren Spaltentiteln; 1 Dezimalstelle in Betragsdiagrammen |
| Höchstens 7 Tabs ohne Scrollpfeil bei 1440 px | Simulation in Portfolio; Textanalyse in Scorecard | 7 / 7 sichtbar; letzter rechter Tab-Rand 1.020,2 px |
| Leitfrage und Kopfzeile | Eine Leitfrage je Hauptseite; Periode/Stand rechts | 7 Seiten mit je 1 Leitfrage; 30.09.2026 rechts |
| Designbausteine und Textschutz | Karten/Statistik statt Standardmetriken; Fremdtext als maskiertes HTML | 0 st.metric / st.subheader; kein ui.e → Markdown |
| Audit auf Suite-Niveau | Karten, objektgleicher Prüfpfad und disjunkte Ausschlussgründe | 7 Karten · 6 Stufen; Browser-Freigabe und Export erfolgreich |
| Zwei getrennte Angriffstests | BSC-Datentext-Quarantäne und DELETE-SQL-Guard | 2 / 2 blockiert; Daten unverändert; Zähler im selben Lauf |
| E501 = 0; Ruff-Regeln unverändert | Formatierung, lange Literale/CSS umgebrochen | 0 Ruff-Verstöße; 0 E501; Regelsatz unverändert |
| Seiten aus app.py auslagern | ui_seiten / ui_strategie / ui_audit / ui_daten / ui_kopf | app.py: 285 Zeilen; keine Fachseiten implementiert |
| Version und Desktop-Referenz | 2.1.0 in Projekt und Desktop; Hashvergleich aktualisiert | 8 Desktop-Dateien bytegleich; nur app.toml projektspezifisch |
| Aktuelle Änderungsdokumentation | SchrittA.md durch Aenderungsprotokoll.md ersetzt | Stand 2.0/2.1 getrennt; Schritt 2 ausdrücklich ausstehend |

## Profiling vorher / nachher

Abschnittsmessung im AppTest-Ausführungsthread. „Cache“ bedeutet kein erneuter Engine-Aufruf.
Erstlaufwerte für Abschnitte sind gesondert gekennzeichnet; der gesamte Akzeptanzlauf oben folgt dem
vorgegebenen Zweiaufruf-Skript. Beide Messarten prüfen, dass kein Seitenfehler die Laufzeit künstlich verkürzt.

| Abschnitt | Vorher | Nachher | Bedeutung |
|---|---:|---:|---|
| Prozesskapital | 1,158 s | 0,000 s | Cache / aktiver Tab |
| Quartalskennzahlen | 0,013 s | 0,000 s | Cache / aktiver Tab |
| Kernaussagen | 0,010 s | 0,000 s | Cache / aktiver Tab |
| Scorecard | 0,510 s | 0,159 s | Erstberechnung |
| Gesamter instrumentierter Folgelauf | 1,397 s | 0,117 s | Gesamte Ausführung |

Erstes Öffnen der Prozessseite: 1,501 s; danach
0,171 s. Die einmalige Prozesskapitalberechnung wurde verschoben, nicht als
Rechenzeitverbesserung der Engine ausgegeben. Keine Daten-/Exportberechnung wird nur zur Messung ausgelassen.

## Reproduktion

Aus dem Projektordner im Offline-Modus, entsprechend dem Abnahmeskript:

```python
import time, os
from streamlit.testing.v1 import AppTest

at = AppTest.from_file(os.path.abspath("app.py"), default_timeout=300)
t = time.time()
at.run()
print("erster Lauf", round(time.time() - t, 1))
t = time.time()
at.run()
print("Folgelauf", round(time.time() - t, 1))
at.selectbox(key="geschaeftsjahr").select(2025)
t = time.time()
at.run()
print("Jahreswechsel", round(time.time() - t, 1))
```

Eingangsbedingungen: LLM_ANBIETER=mock, Webmodus, eigener neuer AGENT_DATENORDNER, Python 3.11.18.
Die erste Messung enthält die Demo-Datenerzeugung. Für jeden Zielinterpreter separat eine neue Umgebung
mit uv sync --locked --python 3.11 beziehungsweise 3.13 aufbauen; nachfolgende uv run mit derselben Version.

Detaillierte Werte: pruefergebnisse.json. Komplette Testausgaben: pytest-python311.txt / pytest-python313.txt.
Browser: Chromium, 1440 × 1100, keine JavaScript-Ausnahme; beide Themes, alle Tabs, BSC,
beide Angriffstests, namentliche Demo-Freigabe und Management-Export geprüft.

## Abgrenzung dieses Lieferstands

Kein Order-to-Cash implementiert. P2P, das separate DSO-Zahlungsmodell und die als nicht gemessen markierte
BSC-Prozessperspektive 2026 bleiben bis Schritt 2 bestehen. Word-Erklärdokumente sind historischer Stand 2.0;
die aktuellen fachlichen Zahlen stehen ausschließlich in den neuen Markdown-/JSON-Nachweisen.
Keine Live-API, kein Upload, kein Deployment. VarianceAI und FlowAudit-AI blieben unverändert.
