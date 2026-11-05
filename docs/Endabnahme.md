# Endabnahme · ControllAI 2.2.1

Lokale Offline-Abnahme am 03.11.2026 im Cloud-Container; Mock, keine kostenpflichtige API.
Gegenüber 2.1.0 neu: Kostenabgleich mit VarianceAI (DB I, Kostenstellen, EBIT, Plan 2026, SENX1); ab 2.2.1 auch je Kunde.

| Kriterium | Gemessener Wert |
|---|---|
| Erstlauf ≤ 12 s | 5,566 s (mit Datenerzeugung); 3,129 s bei vorhandenen Daten |
| Folgelauf ≤ 1 s | 0,355 s |
| Jahreswechsel ≤ 1,5 s | 0,278 s |
| Tests ≤ 180 s je Version | 3.11.18: 436 bestanden in 67,21 s / 3.13.18: 436 bestanden in 66,41 s; 0 Fehler, 0 übersprungen |
| Suite-Umsatzabweichung ≤ 0,5 % | 18 feste Referenzen; 0 Cent / 0,00 % |
| Suite-Kostenabgleich (neu) | Umsatz, HK, DB I, Kostenstellen, EBIT 2024/2025/2026 YTD: 0 Cent Differenz zu VarianceAI |
| Kundenabgleich (2.2.1) | Umsatz und HK 2025 je Kunde (12 Kunden): 0 Cent Differenz; 396 Referenzzellen, 4 protokollierte Umschlüsselungen |
| EBIT | 7.946.753,30 € / 8.720.441,56 € / 5.629.259,60 € (2024 / 2025 / 2026 YTD) |
| Allokation | jeder Kostenstellen-Cent genau einmal verteilt; Summe DB III = EBIT; Tabelle produktfixkosten reproduzierbar |
| Plan 2026 | Umsatz, HK und 69 Kostenzeilen aus VarianceAI; ungeplante Abschreibung 4400/481000 rot |
| SENX1 | erster Verkauf 07.04.2026, nicht vor der Markteinführung am 04.04.2026 |
| Belegidentität O2C/DSO | 132 Kunden-Stichtage, 11 Stichtage; maximal 0 Cent Differenz |
| Zeitachse und PY | 2024/2025 vollständig; 2026 YTD 3 Quartale gegen dieselben 3 PY-Quartale |
| Pareto-Diagramm | Korrektur: Achsbeschriftung verdrängte die Zeichenfläche; jetzt 420 px, Beschriftung −40° |
| Codequalität | 0 Ruff / 0 E501; maximal 120 Zeichen; unveränderter Regelsatz |
| Aufteilung | app.py 285 Zeilen; Kostenstufen in src/kostenstufen.py |
| Desktop und Version | 2.2.1; 8 Desktop-Dateien bytegleich mit VarianceAI, nur app.toml projektspezifisch |
| Dokumentation | 4 DOCX neu erzeugt (2 deutsch im Repository, 2 arabisch separat), 34 PDF-Seiten visuell geprüft |
| Screenshots | 01–04, 06, 07 nach der letzten UI-Änderung neu aufgenommen; 05 unverändert (keine Finanzzahlen) |

## Durchführung und Nachweise

Beide Zielumgebungen wurden frisch mit uv sync --locked --offline und explizitem Python-Interpreter erstellt.
Der Desktop-Lebenszyklustest darf einen lokalen Server starten. Ein vorheriger Lauf in eingeschränkter
Ausführungsumgebung konnte diesen Server nicht starten; der vollständige Endlauf mit lokalen Socketrechten
bestand ohne übersprungene Prüfungen. Tests wurden fachlich auf den Kosten- und Kundenabgleich angepasst, keiner entfernt; 13 neue Abgleichstests.

Laufzeiten: AppTest mit neuem Datenordner (Erstlauf einschließlich Datenerzeugung), Folgelauf und Wechsel des Geschäftsjahres.
Die Testlaufzeiten im Cloud-Container liegen über den Mac-Werten von 2.1.0 (23–26 s); die Grenze von 180 s ist eingehalten.
Das historische Profiling steht dort; es ist ausdrücklich kein aktueller O2C-Abschnittswert.
Aktuelle Rohdaten: pruefergebnisse.json, pytest-python311.txt, pytest-python313.txt und demolauf.json.
Browserprüfung (Playwright, Chromium): 1440 × 1100, Cockpit hell/dunkel, Portfolio mit Pareto/ABC, Prozesse,
Scorecard, Agent & Audit; keine JavaScript-Ausnahme. Screenshots nach der letzten UI-Änderung.

Die OP-Prüfung aggregiert die Bewegungen direkt aus dem Log je Kunde/Stichtag und vergleicht mit
Debitoren-Snapshots. DSO-Treiber summieren sich bis auf Gleitkomma-Rundung zum Gesamtwert.
Der bestehende separate Rechentest für Zahlungstermine bleibt als unabhängige Kontrolle erhalten.

## Grenzen und offene Integrationsarbeit

Keine offenen Punkte im beauftragten Demo-Umfang. SAP-Anbindung bleibt ein zu prüfendes Integrationskonzept,
kein produktiver Connector. Tabellenbeispiele im Zielsystem prüfen. Ein Fall entspricht einer Fakturaposition;
Zahlungen sind synthetisch, keine Teilzahlungen/Steuern/Bankzuordnung. Die Variantenrangfolge erklärt Beiträge,
beweist keine Ursache. Offene Falllaufzeiten sind rechtszensiert. Netto-Debitoren-OP ist nur ein Teil des Working Capital.
Freigaben sind sitzungsgebunden; Name ersetzt keine Authentifizierung. Keine Veröffentlichung und kein GitHub-Upload.
Referenzarchive VarianceAI und FlowAudit-AI blieben unverändert, SHA-256 erneut geprüft.
