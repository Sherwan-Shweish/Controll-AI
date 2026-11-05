# Änderungsprotokoll · ControllAI

## 2.0.0 · abgeschlossener Ausgangsstand

Agenten-Standard v1, Desktop-Starter, SQL-Parser mit Tabellen-/Spaltenfreigaben und SQLite-Authorizer,
Fakten- und Zitatprüfung, manipulationsprüfbare Audit-Hash-Kette. Fachausbau abgeschlossen:
DB I–III mit Cent-Allokation, ABC/Pareto, Simulation, DSO, numerische BSC, namentliche Kommentare,
Management-PPT/PDF, Excel-Gegenprüfung und Power-BI-Sternschema. P2P blieb eine Makro-Sicht.
Die frühere Zwischenstandsnotiz „Schritt A“ ist durch dieses Protokoll ersetzt.

## 2.1.0 · Korrektur, Schritt 1

- Profiling vor der Änderung; Cache nach Funktion, Dateipfad, Änderungszeit, Größe und Argumenten.
  Ergebnis-, DSO-, Scorecard-, Quartals-, Text-, DB-, Simulations- und Exportberechnungen werden wiederverwendet.
  Die besonders aufwendige Prozesskapitalrechnung läuft erst im Prozess-Tab oder beim Berichtsexport.
  Zeichenbibliotheken werden erst beim Export geladen. Keine sitzungsübergreifenden Agenten-/Freigabeobjekte.
- 2024 und 2025 vollständig, 2026 Januar–September. Vorjahresvergleich ebenfalls Januar–September.
  Umsatz auf VarianceAI 1.2, Seed 42, je Quartal × Region × Produktgruppe centgenau kalibriert.
  Begründung und feste Referenzwerte in Suite-Abstimmung.md.
- Eigene Modellkosten und Planwerte auf die größere Umsatzbasis skaliert; keine behauptete Gleichheit von
  EBIT, Einzelbelegen oder Plänen mit VarianceAI. SAP-Musterexport und Datenbank enthalten dieselben Beträge.
  Ausreißerregel im Generator: robuster Score auf logarithmierten Beträgen, Schwelle 4,0 statt 3,5;
  durch die größere Zeitachse wird ein zusätzlicher Fehlalarm vermieden. Alle injizierten Fehler werden
  weiterhin gefunden; allgemeine Analysefunktionen und deren Standardschwelle bleiben unverändert.
- Frischer Demo-Datenordner daten-v2.1. Bestehende 2.0-Daten bleiben erhalten; ein expliziter DB_PATH gewinnt.
- Sieben Hauptseiten: Cockpit, Portfolio, Prozesse, Scorecard, KI-Analyst, Bericht, Agent & Audit.
  Profitabilität und Simulation gehören in dasselbe Portfolio; BSC-Textanalyse ist ein Unterbereich.
  Je Hauptseite eine Leitfrage. Deutsche Tabellen und Zahlen, Kunden-/Materialnamen aus Suite-Stammdaten.
- Sieben Agentenkarten und ein nachvollziehbarer Trichter über aktuelle Kennzahlobjekte. Getrennte
  Datentext- und DELETE-Tests; beide schreiben vor der Zählung ins Audit. Datentext-Quarantäne entfernt
  bekannte Anweisungszeilen vor dem Modellaufruf, ohne Scorecardwerte zu beeinflussen.
- Dynamische Texte werden als maskiertes HTML gerendert, niemals maskiert und anschließend als Markdown.
  Die Erkennung bekannter Injection-Muster ist keine universelle Erkennung beliebiger Angriffe.
- Seiten und Datenzugriff sind aus app.py in ui_seiten, ui_strategie, ui_audit, ui_daten und ui_kopf ausgelagert.
  Bestehende englische Agentenkern-APIs bleiben stabil: Umbenennung würde Integrationsrisiken ohne fachlichen
  Nutzen verursachen. Neue Fachfunktionen und Erläuterungen sind deutsch.
- Versionsnummern 2.1.0. desktop/ einschließlich Ressourcen bleibt außer app.toml bytegleich mit VarianceAI.
  Designfarben und Bausteine übernommen; Formatierung/CSS-Zeilenumbrüche zur E501-Einhaltung angepasst.
- FlowAudit-AI 1.2 wurde als dritter, unveränderter Suite-Referenzagent einbezogen:
  Karten mit Regel/Zähler, Aktionen vor Audit-Zählung, Prüftrichter, Gründe und Mensch-entscheidet-Prinzip.

## 2.1.0 · abgeschlossener Schritt 2

- O2C-Log aus denselben bereinigten Fakturapositionen, Seed 42; Zahlungen und signierte Gutschriften
  bilden die einzige OP-Basis für DSO. Invariante je Kunde und Stichtag centgenau geprüft.
- Varianten, Übergänge, Landkarte und geprüfte BPMN-Vorschläge wiederverwendet; P2P in der Oberfläche
  auf den Verweis zu FlowAudit-AI reduziert. Historische Generatorfunktion bleibt als kompatible API erhalten.
- Prozessseite zeigt Netto-OP und additive DSO-Beiträge nach Kunde/Variante; offene Falllaufzeiten klar gekennzeichnet.
- BSC Kunden: DSO und Liefertreue; Prozesse: Nacharbeit abgeschlossener O2C-Fälle. Vier Perspektiven gleichgewichtet.
- Prozesskapital als vorzeichenrichtige Netto-OP-Zeitintegration vektorisiert. Neuer Datenordner daten-v2.1-o2c.
- README, Laufzahlen, Screenshots und beide Erklärdokumente aktualisiert. Arabische Fassungen separat geliefert.
- 423 Tests auf beiden Zielversionen, keine Tests gelöscht oder übersprungen. Aktuelle Werte in Endabnahme.md.

## 2.2.0 · Suite-Kostenabgleich mit VarianceAI

- Variable Herstellkosten je Quartal × Region × Produktgruppe centgenau auf VarianceAI (Konto 700000).
  DB I 2025: 46.461.995,51 € (55,40 %) statt bisher 37,41 % Marge.
- Istkosten je Kostenstelle und Kostenart aus VarianceAI (254 Zeilen, 4100–4500, einschließlich der
  außerplanmäßigen Abschreibung 4400/481000 im Q3 2026). EBIT 2024/2025/2026 YTD:
  7.946.753,30 € / 8.720.441,56 € / 5.629.259,60 € – identisch mit VarianceAI (vorher 13,83 / 14,07 / 12,45 Mio. €).
- Neue Stufenzuordnung in `src/kostenstufen.py`: Erzeugnisfixkosten (DB II) = Fertigung 4100–4300 und
  Qualitätssicherung 4500, Unternehmensfixkosten (DB III) = Instandhaltung 4400. Neue Tabelle `produktfixkosten`
  (SQL-Freigabe, Power-BI-Fakt, DAX für DB II/EBIT). Konstante Produktfixkosten je Kategorie entfallen.
- Kundenrechnung: Fertigung nach Herstellkosten, QS nach Demo-Servicegewicht. Ergebnis: kein Kunde mit negativem
  DB II; die drei serviceintensiven Kunden haben die niedrigsten Margen (K104 2026: 2,3 % gegenüber 12,6 %).
  ABC-Kennzahlen um negative DB-III-Kunden und schwächste Marge ergänzt.
- Plan 2026 (Umsatz, HK, Kostenstellen) aus VarianceAI. 2024/2025 bleibt die eigene Planung mit erhaltenem
  Plan/Ist-Verhältnis; Plan-HK = Plan-Umsatz × Standard-HK-Satz der Produktgruppe. Ungeplante Istkosten (Plan 0)
  werden rot bewertet. BSC-Ziel DB-II-Marge 13,4 % aus dem VarianceAI-Plan statt pauschal 30 %.
- SENX1 erst ab 04.04.2026 wie in VarianceAI; frühere Positionen deterministisch auf SEN01–SEN03 umgeschlüsselt.
- Executive Summary (Offline) nennt beide eingebauten Budgetüberschreitungen (4200/400000 und 4100/410000).
  Der frühere Befund „Antriebe mit höherer Materialkostenquote“ entfällt, weil VarianceAI mit Standard-HK rechnet.
- Werkzeuge: `tools/suite_referenz_erzeugen.py` (Referenz aus VarianceAI), `tools/demolauf_erzeugen.py` (Nachweis).
  Neuer Datenordner `daten-v2.2`. Tests: 11 neue Abgleichstests in `tests/test_suite_kosten.py`;
  angepasste Tests prüfen EBIT zusätzlich unabhängig von jeder Schlüsselung (Umsatz − HK − alle Kostenstellen).
- Versionsnummern 2.2.0. VarianceAI und FlowAudit-AI unverändert.

## 2.2.1 · Kundenabgleich mit VarianceAI

- Referenzzelle um den Kunden erweitert (Quartal × Region × Produktgruppe × Kunde, 396 Zellen): Umsatz und HK je Kunde
  centgenau wie in VarianceAI (z. B. K201 2025: 11.355.882,87 € statt 10.063.440,53 €).
- Vier Zellen ohne Beleg werden deterministisch durch Umschlüsselung je einer Position gefüllt und dokumentiert
  (Suite-Abstimmung.md).
- Folgen: DSO 30.09.2026 46,42 Tage (vorher 45,63), Netto-OP 10.398.886,94 €; K304 im Jahr 2026 mit negativem DB II
  (−118.781,44 €), K204 und K304 mit negativem DB III. Gesamtwerte (Umsatz, DB I, Kostenstellen, EBIT) unverändert.
- Oberfläche: „1 Kunde“ statt „1 Kunden“ in der ABC-Zusammenfassung. Zwei neue Abgleichstests.
- Neuer Datenordner `daten-v2.2.1`, Versionsnummern 2.2.1, Erklärdokumente und Screenshots neu erzeugt.
