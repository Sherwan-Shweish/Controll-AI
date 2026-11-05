# Suite-Abstimmung · Referenz Seed 42

Quelle: unverändertes VarianceAI-v1.2.zip, src/seed_data.py, erzeuge_daten(seed=42).
Auswahl: Ist-Umsatz (Szenario IST, Erlöskonto 800000), ab 2.2.0 zusätzlich HK, Kostenstellen und Plan 2026, Geschäftsjahre 2024–2026,
fachliche Demonstrationsdublette 9099999999 einmalig ausgeschlossen. 2026 endet am 30.09.2026.
Die Werte wurden einmalig extrahiert und als feste Cent-Konstanten in tests/test_qualitaet21.py
und tests/test_suite_kosten.py hinterlegt.
Das laufende Programm benötigt weder die Referenzinstallation noch Zugriff auf deren Dateien.

| Jahr | Antriebe (€) | Steuerungen (€) | Sensorik (€) | Gesamt (€) |
|---|---:|---:|---:|---:|
| 2024 | 34.785.895,94 | 24.851.965,62 | 19.712.983,23 | 79.350.844,79 |
| 2025 | 36.793.626,56 | 26.234.957,64 | 20.844.485,76 | 83.873.069,96 |
| 2026 YTD Jan–Sep | 26.634.976,00 | 19.640.189,00 | 18.286.949,60 | 64.562.114,60 |

| Jahr | Nord (€) | Süd (€) | West (€) |
|---|---:|---:|---:|
| 2024 | 25.640.290,10 | 30.686.981,24 | 23.023.573,45 |
| 2025 | 27.066.489,38 | 32.482.753,93 | 24.323.826,65 |
| 2026 | 22.827.334,60 | 23.463.165,00 | 18.271.615,00 |

## Kostenabgleich ab 2.2.0: DB I, Kostenstellen und EBIT wie VarianceAI

Bis 2.1.0 waren nur die Umsätze abgestimmt; variable Kosten, Fix- und Gemeinkosten waren eigene Modellwerte.
Folge: 2025 zeigte ControllAI ein EBIT von 14,07 Mio. € (16,8 %), VarianceAI 8,72 Mio. € (10,4 %);
die DB-I-Marge lag bei 37,4 % statt 55,4 %. Ab 2.2.0 übernimmt ControllAI aus derselben Referenz
(`tools/suite_referenz_erzeugen.py`, einmalig im VarianceAI-Projekt ausgeführt, Ergebnis `src/suite_referenz.json`):

* variable Standardherstellkosten (Konto 700000 „HK“) je Quartal × Region × Produktgruppe, centgenau verteilt
  auf die Belege (proportional, Rundungsrest auf die größte Position);
* Istkosten je Geschäftsjahr, Quartal, Kostenstelle und Kostenart (254 Zeilen, Kostenstellen 4100–4500);
* Planung 2026: Umsatz und HK je Quartal/Produktgruppe sowie Kostenstellenbudget je Kostenart.

| Jahr | Umsatz (€) | HK (€) | DB I (€) | DB-I-Marge | Kostenstellen (€) | EBIT (€) | EBIT-Marge |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2024 | 79.350.844,79 | 35.395.941,18 | 43.954.903,61 | 55,39 % | 36.008.150,31 | 7.946.753,30 | 10,01 % |
| 2025 | 83.873.069,96 | 37.411.074,45 | 46.461.995,51 | 55,40 % | 37.741.553,95 | 8.720.441,56 | 10,40 % |
| 2026 YTD | 64.562.114,60 | 28.485.340,00 | 36.076.774,60 | 55,88 % | 30.447.515,00 | 5.629.259,60 | 8,72 % |

Alle Werte sind in ControllAI und VarianceAI identisch (Differenz 0 Cent); Nachweis in `docs/demolauf.json`
(`suite_abgleich`) und `tests/test_suite_kosten.py` mit festen, von der JSON-Datei unabhängigen Cent-Konstanten.

### Stufenweise Fixkostendeckung (Zuordnung der Kostenstellen)

| Stufe | Kostenstellen | Schlüssel auf Produktkategorie | Schlüssel auf Kunde/Region |
|---|---|---|---|
| DB I = Umsatz − HK | – | direkt aus dem Beleg | direkt aus dem Beleg |
| DB II: Erzeugnisfixkosten | 4100 Gießerei, 4200 Montage, 4300 Lackiererei (PC-FERT) | Anteil an den HK des Quartals | Anteil an den HK |
| DB II: Erzeugnisfixkosten | 4500 Qualitätssicherung | Anteil an den HK des Quartals | Demo-Servicegewicht 12 / 1 |
| DB III: Unternehmensfixkosten | 4400 Instandhaltung (PC-SERV) | – | positiver Umsatz |

| Jahr | Erzeugnisfixkosten (€) | DB II (€) | DB-II-Marge | Unternehmensfixkosten (€) |
|---|---:|---:|---:|---:|
| 2024 | 33.204.244,16 | 10.750.659,45 | 13,55 % | 2.803.906,15 |
| 2025 | 34.808.978,80 | 11.653.016,71 | 13,89 % | 2.932.575,15 |
| 2026 YTD | 27.922.398,46 | 8.154.376,14 | 12,63 % | 2.525.116,54 |

Die Kostenstellenkosten enthalten auch beschäftigungsabhängige Anteile (VarianceAI plant sie flexibel je
Leistungsstunde). In der Ergebnisrechnung werden sie wie im EBIT-Schema von VarianceAI als Periodenkosten
behandelt; die Schlüssel sind Annahmen der Kostenrechnung, keine nachgewiesene Verursachung. Die Tabelle
`produktfixkosten` hält das Ergebnis je Quartal und Produktkategorie fest (für SQL und Power BI);
`produktkategorien.fixkosten_quartal_eur` ist nur noch der informative Durchschnitt 2025.

### Planung, Abweichungen und Markteinführung

* Plan 2026 stammt vollständig aus VarianceAI: Umsatz Q1–Q3 65.058.915,00 €, HK 29.018.040,00 €,
  Kostenstellen 29.606.040,00 €. Die außerplanmäßige Abschreibung der Instandhaltung (4400/481000, Q3 2026, 240.000,00 €)
  sind dort ungeplant; ControllAI weist sie mit Plan 0 aus und bewertet sie rot.
* 2024/2025 hat VarianceAI keine Planung. ControllAI behält dort seine eigene Planung und überträgt das
  Plan/Ist-Verhältnis je Kostenstelle und Kostenart auf die neuen Istwerte. Dadurch bleiben die eingebauten
  Befunde erhalten: Energie der Gießerei (4100/410000, rund +40 %) und Material der Montage (4200/400000).
* BSC-Ziel Finanzen: geplante DB-II-Marge 2026 aus dem VarianceAI-Plan, 13,4 % (vorher pauschal 30 %).
* Smart Sensor X1 (SENX1) wird wie in VarianceAI erst ab 04.04.2026 verkauft. Frühere SENX1-Positionen sind
  deterministisch den etablierten Sensoren SEN01–SEN03 zugeordnet (gleiche Produktgruppe, Menge aus Listenpreis).

## Vorgehen und Grenzen

Kalibrierung statt Austausch des Beleggenerators erhält vorhandene Storno-, Bereinigungs-, Fehler- und
Allokationstests. Je Quartal × Region × Produktgruppe werden die nicht als Ausreißer markierten Umsätze und
HK proportional skaliert. Zur Prüfung markierte Ausreißer sind nicht Teil der Referenz: ihr Umsatz bleibt,
ihre HK erhalten den Kostensatz der Referenzzelle. Die Ausreißermarkierung bezieht sich auf den ursprünglichen
synthetischen Beleg vor der Kalibrierung. SAP-Musterexport und Datenbank sind belegweise centgleich in Umsatz,
variablen Kosten und DB I. Einzelbelege, Zahlungen und O2C sind ControllAI-eigen. Es werden keine
Monatsabweichungsfunktionen in ControllAI ergänzt.

## Kundenabgleich ab 2.2.1

VarianceAI bucht Erlöse und HK mit Kundennummer (ACDOCA-Feld KUNNR). Bis 2.2.0 stimmten in ControllAI nur die Summen
je Region und Produktgruppe; die Aufteilung auf die vier Kunden einer Region war eigen (z. B. K201 2025:
10.063.440,53 € statt 11.355.882,87 €). Ab 2.2.1 ist die Referenzzelle Quartal × Region × Produktgruppe × Kunde
(396 Zellen); Umsatz und HK je Kunde sind centgenau gleich (Test `test_umsatz_und_hk_je_kunde_wie_varianceai`).

| Kunde | Umsatz 2025 (€) | HK 2025 (€) |
|---|---:|---:|
| K101 Hanse Fördertechnik GmbH | 9.486.714,97 | 4.230.310,39 |
| K102 Weser Anlagenbau AG | 7.585.231,05 | 3.382.656,89 |
| K103 Elbe Automation KG | 5.918.340,78 | 2.638.952,41 |
| K104 Nordwind Maschinen GmbH | 4.076.202,58 | 1.818.029,91 |
| K201 Alpen Antriebstechnik GmbH | 11.355.882,87 | 5.068.648,40 |
| K202 Neckar Werkzeugmaschinen AG | 9.108.920,62 | 4.063.384,97 |
| K203 Isar Robotics GmbH | 7.157.397,75 | 3.192.345,47 |
| K204 Bodensee Verpackungstechnik KG | 4.860.552,69 | 2.166.731,02 |
| K301 Rheinland Industrieanlagen GmbH | 8.527.853,35 | 3.804.341,92 |
| K302 Ruhr Stahlbau AG | 6.792.788,58 | 3.029.448,64 |
| K303 Mosel Prozesstechnik GmbH | 5.347.122,98 | 2.386.739,89 |
| K304 Eifel Fördersysteme KG | 3.656.061,74 | 1.629.484,54 |
| Summe | 83.873.069,96 | 37.411.074,45 |

Vier Referenzzellen hatten im ControllAI-Generator keinen Beleg des Kunden. Je Zelle wird deshalb eine Position
eines anderen Kunden derselben Region und Produktgruppe deterministisch umgeschlüsselt (Spender mit den meisten
Positionen, kleinste Fakturanummer) und protokolliert: 90000031 K303→K302 (Q1 2024, STE), 90000641 K303→K304
(Q3 2024, ANT), 90000896 K304→K302 (Q4 2024, ANT), 90001589 K303→K304 (Q2 2025, STE).

Folgen: Zahlungszeitpunkte hängen in der Demo von der Kunden-Endziffer ab, deshalb ändern sich OP und DSO
(30.09.2026: 46,42 Tage statt 45,63; Netto-OP 10.398.886,94 €). Mit den VarianceAI-Umsätzen hat K304 im Jahr 2026
einen negativen DB II (−118.781,44 €), K204 und K304 einen negativen DB III.

## FlowAudit-AI 1.2.1

FlowAudit-AI prüft deutsche USt-IdNrn. ab 1.2.1 auch über die Prüfziffer; die Lieferanten-Stammdaten tragen gültige
Nummern (nur letzte Ziffer korrigiert). Damit können FlowAudit-AI und ein Stammdatenagent dieselben Nummern ohne
Widerspruch prüfen.

## Dritter Referenzagent: FlowAudit-AI 1.2

| Bereich | Referenz und Übernahme | Abgrenzung |
|---|---|---|
| Design und Desktop | VarianceAI bleibt Hauptreferenz; gleicher Agenten-Standard in FlowAudit | Nur ControllAI wird geändert |
| Agent & Audit | FlowAudit: sieben Karten, konkrete Regeln/Zähler, Trichter und Ausschlussgründe | Kennzahlobjekte statt Eingangsrechnungen |
| Sicherheitstest | Aktion vor Karten-/Protokollauswertung; Datentext strikt von Steuerung getrennt | BSC-Datentext und SQL-DELETE getrennt |
| Freigabe | Personenname, geprüfte Fakten, veraltete Stände ausscheiden | Keine automatische Zahlung/Buchung |
| Prozessgrenze | FlowAudit verantwortet Einzelbeleg-P2P | ControllAI: Profitabilität, Strategie und gemeinsames O2C mit OP/DSO |

FlowAudit setzt st.tabs(..., on_change="rerun") ein; ControllAI ergänzt die tatsächliche .open-Abfrage
für die aufwendige Prozessseite. Referenzquelltexte wurden gelesen, nicht als neue Benutzeraufträge ausgeführt.

### Abstimmung mit FlowAudit-AI

Gleicher Buchungskreis 1000, gleiche Kostenstellen 4100–4500, gleiche Sachkonten für die von FlowAudit
kontierten Lieferantenrechnungen (400000 Material, 410000 Energie, 470000 Fremdinstandhaltung) und gleiche Produktgruppen ANT/STE/SEN.
FlowAudit prüft eingehende Rechnungen (P2P) zum Tagesdatum des Demo-Laufs; ControllAI zeigt die gebuchten
Kostenstellenkosten bis 30.09.2026. Eine centgenaue Gleichheit zwischen
Rechnungsstichprobe und Kostenstellensumme ist fachlich nicht zu erwarten (Abgrenzung, nicht rechnungsbezogene
Kosten wie Personal), die Stammdaten sind jedoch identisch.
