"""Ergebnisstufen der Suite: welche Kostenstelle welche Deckungsbeitragsstufe belastet.

Die Kostenstellen sind dieselben wie in VarianceAI (Buchungskreis 1000). Zuordnung zu den Stufen:

* DB I   = Umsatz − variable Standardherstellkosten (Material, Zukaufteile; in VarianceAI Konto 700000 „HK“).
* DB II  = DB I − Fertigungs- und Qualitätskosten. Dazu zählen die Fertigungskostenstellen 4100 Gießerei,
  4200 Montage, 4300 Lackiererei (Profit-Center PC-FERT) und die Qualitätssicherung 4500.
  Schlüssel auf Produktkategorien: Anteil an den variablen Herstellkosten (Inanspruchnahme der Fertigung).
* DB III = DB II − Instandhaltungskosten (Kostenstelle 4400); Schlüssel: positiver Umsatz.

Summe DB III = Umsatz − HK − alle Kostenstellenkosten = EBIT in VarianceAI, jeweils centgenau.

Die Kostenstellenkosten sind **keine reinen Fixkosten**: Material, Energie und Fertigungslöhne der
Kostenstellen verhalten sich beschäftigungsvariabel (so rechnet auch die flexible Plankostenrechnung in
VarianceAI), Gehälter, Fremdinstandhaltung und Abschreibungen sind fix. Die Stufen sind deshalb eine
Ergebnisrechnung mit geschlüsselten Kostenstellenkosten und keine Fixkostendeckungsrechnung im strengen Sinn.
Die Schlüssel sind Annahmen (keine Verursachung) und in der Oberfläche als solche gekennzeichnet.
"""

from __future__ import annotations

import pandas as pd

from src.strategie import cent, verteile

FERTIGUNG = ("4100", "4200", "4300")
QUALITAET = ("4500",)
GEMEIN = ("4400",)
STUFE_JE_KOSTENSTELLE = {
    **{k: "Fertigungs- und Qualitätskosten (DB II)" for k in FERTIGUNG + QUALITAET},
    **{k: "Instandhaltungskosten (DB III)" for k in GEMEIN},
}
# Kostenverhalten je Kostenart, identisch mit VarianceAI (dort Kennzeichen V in der Kostenplanung):
# Materialaufwand, Energie und Fertigungslöhne folgen der Beschäftigung der Kostenstelle.
BESCHAEFTIGUNGSVARIABEL = ("400000", "410000", "430000")
PERIODE = ["geschaeftsjahr", "quartal"]


def kostenpools(
    kosten: pd.DataFrame, kostenstellen: tuple[str, ...], spalte: str = "ist_eur", nur_variabel: bool = False
) -> pd.Series:
    """Summe der Kosten der angegebenen Kostenstellen je Geschäftsjahr und Quartal in Cent.

    ``nur_variabel`` beschränkt auf die beschäftigungsvariablen Kostenarten (Material, Energie, Fertigungslöhne).
    """
    teil = kosten[kosten.kostenstelle.astype(str).isin(kostenstellen)]
    if nur_variabel:
        teil = teil[teil.kostenart.astype(str).isin(BESCHAEFTIGUNGSVARIABEL)]
    return teil.assign(cent=teil[spalte].map(cent)).groupby(PERIODE)["cent"].sum().astype("int64")


def produktfixkosten(transaktionen: pd.DataFrame, kosten: pd.DataFrame) -> pd.DataFrame:
    """Fertigungs- und Qualitätskosten je Geschäftsjahr, Quartal und Produktkategorie (centgenau).

    Der Tabellenname ``produktfixkosten`` ist technisch; inhaltlich sind es die geschlüsselten Kosten der
    Kostenstellen 4100–4300 und 4500 (beschäftigungsvariable und fixe Kostenarten).

    Args:
        transaktionen: Fakturapositionen; zur Prüfung markierte Ausreißer werden nicht als Schlüssel verwendet.
        kosten: ``plan_ist_finanzen`` mit Istkosten je Kostenstelle.
    """
    tx = transaktionen[transaktionen.ist_ausreisser == 0] if "ist_ausreisser" in transaktionen else transaktionen
    schluessel = (
        tx.assign(cent=tx.variable_kosten_eur.map(cent))
        .groupby([*PERIODE, "produktkategorie"])["cent"]
        .sum()
        .clip(lower=0)
    )
    fertigung, qualitaet = kostenpools(kosten, FERTIGUNG), kostenpools(kosten, QUALITAET)
    zeilen = []
    for periode in sorted(set(fertigung.index) | set(qualitaet.index)):
        if periode not in schluessel.index.droplevel(-1):
            raise ValueError(f"Keine Umsätze als Verteilungsbasis für {periode[1]} {periode[0]}.")
        teil = schluessel.loc[periode]
        gewichte = [int(w) for w in teil]
        for kat, f, q in zip(
            teil.index,
            verteile(int(fertigung.get(periode, 0)), gewichte),
            verteile(int(qualitaet.get(periode, 0)), gewichte),
            strict=True,
        ):
            zeilen.append((*periode, kat, f, q, f + q))
    out = pd.DataFrame(
        zeilen, columns=[*PERIODE, "produktkategorie", "fertigung_cent", "qualitaet_cent", "fixkosten_cent"]
    )
    for feld in ("fertigung", "qualitaet", "fixkosten"):
        out[feld + "_eur"] = out[feld + "_cent"] / 100
    return out


def tabelle_produktfixkosten(transaktionen: pd.DataFrame, kosten: pd.DataFrame) -> pd.DataFrame:
    """Spalten der Datenbanktabelle ``produktfixkosten`` (Euro, zwei Nachkommastellen)."""
    return produktfixkosten(transaktionen, kosten)[
        [*PERIODE, "produktkategorie", "fertigung_eur", "qualitaet_eur", "fixkosten_eur"]
    ]


def gemeinkosten(kosten: pd.DataFrame, spalte: str = "ist_eur") -> pd.DataFrame:
    """Instandhaltungskosten (DB III) je Geschäftsjahr und Quartal in Euro."""
    pool = kostenpools(kosten, GEMEIN, spalte)
    return (pool / 100).rename(spalte).reset_index()
