"""Strategische Ergebnisrechnung. Geldbeträge werden als ganze Cent verarbeitet."""

from __future__ import annotations

import calendar
import math
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import numpy as np
import pandas as pd

from src.analytics import lade_event_log, lade_tabelle

# BSC-Ziel Finanzen: geplante DB-II-Marge laut VarianceAI-Plan 2026 (Q1–Q3), auf eine Nachkommastelle.
ZIEL_DB_II_MARGE_PCT = 13.4
GELD = ["umsatz", "variabel", "db_i", "produktfix", "db_ii", "gemein", "db_iii"]
DIMENSIONEN = ["geschaeftsjahr", "quartal", "kunden_nr", "region", "produktgruppe"]


def cent(wert: float | str | Decimal) -> int:
    return int((Decimal(str(wert)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def verteile(betrag: int, gewichte: list[int]) -> list[int]:
    """Größter Rest, stabile Reihenfolge bei Gleichstand; keine verlorenen Cent."""
    if not gewichte or min(gewichte) < 0 or sum(gewichte) <= 0:
        raise ValueError("Positive Verteilungsbasis erforderlich.")
    sign = -1 if betrag < 0 else 1
    basis = sum(gewichte)
    anteile = [abs(betrag) * w // basis for w in gewichte]
    rest = abs(betrag) - sum(anteile)
    rang = sorted(range(len(gewichte)), key=lambda i: (-(abs(betrag) * gewichte[i] % basis), i))
    for i in rang[:rest]:
        anteile[i] += 1
    return [a * sign for a in anteile]


def ergebnisrechnung(db: str | Path) -> pd.DataFrame:
    """Vollständige Allokation vor jedem Filter. Summe DB III = EBIT (identisch mit VarianceAI).

    Stufen und Schlüssel (siehe ``src/kostenstufen.py``):
    * Erzeugnisfixkosten je Quartal und Produktkategorie aus der Tabelle ``produktfixkosten``;
      Fertigung (4100–4300) weiter nach variablen Herstellkosten auf Kunden und Regionen,
      Qualitätssicherung (4500) nach Demo-Servicegewicht (Kunden-Endziffer 4 → 12, sonst 1).
    * Unternehmensfixkosten (Instandhaltung 4400) je Quartal nach positivem Umsatz.
    Es entstehen keine zusätzlichen Kosten; jeder Cent wird genau einmal verteilt.
    """
    from src.kostenstufen import GEMEIN, kostenpools

    tx = lade_tabelle(db, "umsatz_transaktionen")
    tx = tx[tx.ist_ausreisser == 0].copy()
    for quelle, ziel in [("umsatz_eur", "umsatz_cent"), ("variable_kosten_eur", "variabel_cent")]:
        tx[ziel] = tx[quelle].map(cent)
    d = tx.groupby(DIMENSIONEN, as_index=False)[["umsatz_cent", "variabel_cent"]].sum()
    d["servicegewicht"] = d.kunden_nr.map(lambda k: 12 if str(k).endswith("4") else 1)
    d["produktfix_cent"] = 0
    fix = lade_tabelle(db, "produktfixkosten").set_index(["geschaeftsjahr", "quartal", "produktkategorie"])
    zuordnung = tx[["produktgruppe", "produktkategorie"]].drop_duplicates().set_index("produktgruppe").produktkategorie
    for (jahr, quartal, gruppe), ind in d.groupby(["geschaeftsjahr", "quartal", "produktgruppe"]).groups.items():
        zeile = fix.loc[(jahr, quartal, zuordnung[gruppe])]
        fertigung = verteile(cent(zeile.fertigung_eur), d.loc[ind, "variabel_cent"].clip(lower=0).tolist())
        qualitaet = verteile(cent(zeile.qualitaet_eur), d.loc[ind, "servicegewicht"].tolist())
        d.loc[ind, "produktfix_cent"] = [f + q for f, q in zip(fertigung, qualitaet, strict=True)]
    pools = kostenpools(lade_tabelle(db, "plan_ist_finanzen"), GEMEIN)
    d["gemein_cent"] = 0
    for periode, ind in d.groupby(["geschaeftsjahr", "quartal"]).groups.items():
        gewichte = d.loc[ind, "umsatz_cent"].clip(lower=0).tolist()
        d.loc[ind, "gemein_cent"] = verteile(int(pools.get(periode, 0)), gewichte)
    d["db_i_cent"] = d.umsatz_cent - d.variabel_cent
    d["db_ii_cent"] = d.db_i_cent - d.produktfix_cent
    d["db_iii_cent"] = d.db_ii_cent - d.gemein_cent
    return d


def verdichte(daten: pd.DataFrame, gruppen: list[str]) -> pd.DataFrame:
    if not set(gruppen) <= set(DIMENSIONEN):
        raise ValueError("Unbekannte Dimension.")
    felder = [g + "_cent" for g in GELD]
    d = daten.groupby(gruppen, as_index=False)[felder].sum() if gruppen else daten[felder].sum().to_frame().T
    for g in GELD:
        d[g + "_eur"] = d[g + "_cent"] / 100
    d["db_ii_marge_pct"] = d.db_ii_cent / d.umsatz_cent.replace(0, np.nan) * 100
    d["status"] = np.where(d.db_ii_cent < 0, "Negativer DB II", "Positiver DB II")
    return d


def abc_analyse(daten: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """ABC auf positiven Beiträgen; Top-Fünftel auf Netto-DB II (kann >100 % sein)."""
    d = (
        verdichte(daten, ["kunden_nr"])
        .sort_values(["db_ii_cent", "kunden_nr"], ascending=[False, True])
        .reset_index(drop=True)
    )
    positiv = d.db_ii_cent.clip(lower=0)
    total = int(positiv.sum())
    d["anteil_pct"] = positiv / total * 100 if total else 0.0
    d["kumuliert_pct"] = d.anteil_pct.cumsum()
    davor = d.kumuliert_pct - d.anteil_pct
    d["abc"] = np.select([d.db_ii_cent <= 0, davor < 80, davor < 95], ["C", "A", "B"], default="C")
    n = math.ceil(len(d) * 0.2)
    netto = int(d.db_ii_cent.sum())
    mit_umsatz = d[d.umsatz_cent > 0]
    schwach = mit_umsatz.loc[mit_umsatz.db_ii_marge_pct.idxmin()] if len(mit_umsatz) else None
    return d, {
        "kunden": len(d),
        "top_kunden": n,
        "kundenanteil_pct": n / len(d) * 100 if len(d) else 0,
        "db_anteil_pct": int(d.head(n).db_ii_cent.sum()) / netto * 100 if netto > 0 else None,
        "negative_kunden": int((d.db_ii_cent < 0).sum()),
        "negative_db_iii_kunden": int((d.db_iii_cent < 0).sum()),
        "schwaechster_kunde": schwach.kunden_nr if schwach is not None else None,
        "schwaechste_marge_pct": float(schwach.db_ii_marge_pct) if schwach is not None else None,
        "portfolio_marge_pct": netto / int(d.umsatz_cent.sum()) * 100 if int(d.umsatz_cent.sum()) else None,
        "positiver_db_cent": total,
    }


def debitoren_snapshots(db: str | Path) -> pd.DataFrame:
    """Synthetische Netto-OP: Zahlung nach 30 + 10 × Kunden-Endziffer Tagen.

    Keine echte OP-Buchhaltung und keine Umsatzsteuer. Quelle: bereinigte Fakturen.
    DSO = Netto-OP am Stichtag / Netto-Umsatz der letzten 90 Tage × 90.
    """
    tx = lade_tabelle(db, "umsatz_transaktionen")
    tx = tx[tx.ist_ausreisser == 0].copy()
    tx["datum"] = pd.to_datetime(tx.buchungsdatum)
    from src.o2c import log_aus_db, offene_posten

    log = log_aus_db(db)
    tx["cent"] = tx.umsatz_eur.map(cent)
    zeilen = []
    for jahr in sorted(tx.geschaeftsjahr.unique()):
        for q in range(1, 4 if jahr == 2026 else 5):
            stichtag = pd.Timestamp(int(jahr), q * 3, calendar.monthrange(int(jahr), q * 3)[1])
            fenster = tx[(tx.datum <= stichtag) & (tx.datum > stichtag - pd.Timedelta(days=90))]
            offen = offene_posten(log, stichtag)
            for kunde in sorted(tx.kunden_nr.unique()):
                op = int(offen.loc[offen.kunden_nr == kunde, "op_bewegung_cent"].sum())
                umsatz = int(fenster.loc[fenster.kunden_nr == kunde, "cent"].sum())
                zeilen.append(
                    {
                        "geschaeftsjahr": int(jahr),
                        "quartal": f"Q{q}",
                        "stichtag": stichtag.strftime("%Y-%m-%d"),
                        "kunden_nr": kunde,
                        "op_netto_cent": op,
                        "umsatz_90t_cent": umsatz,
                    }
                )
    return pd.DataFrame(zeilen)


def dso_zeitreihe(db: str | Path) -> pd.DataFrame:
    d = (
        debitoren_snapshots(db)
        .groupby(["geschaeftsjahr", "quartal"], as_index=False)[["op_netto_cent", "umsatz_90t_cent"]]
        .sum()
    )
    d["dso_tage"] = d.op_netto_cent / d.umsatz_90t_cent.replace(0, np.nan) * 90
    return d


def lern_daten() -> pd.DataFrame:
    """Eigenständige, reproduzierbare Demo-Beobachtungen; kein Rückschluss aus Finanzdaten."""
    rng = np.random.default_rng(2042)
    return pd.DataFrame(
        [
            {
                "geschaeftsjahr": jahr,
                "quartal": f"Q{q}",
                "teilnehmende": 80,
                "lernstunden": int(rng.integers(1000, 1750)),
                "ziel_stunden_pro_person": 20,
            }
            for jahr in (2024, 2025, 2026)
            for q in range(1, 5)
        ]
    )


def prozess_kapital(log: pd.DataFrame, zinssatz_pct: float = 6) -> dict:
    """Netto-Forderungsexposition aus gebuchten Faktura- und Zahlungsbewegungen."""
    from src.o2c import offene_posten

    d = log.copy()
    d["zeitstempel"] = pd.to_datetime(d.zeitstempel)
    d["op_bewegung_cent"] = pd.to_numeric(d.op_bewegung_cent)
    stand = d.zeitstempel.max()
    tage = (stand - d.zeitstempel).dt.total_seconds() / 86400
    werttage = float((d.op_bewegung_cent * tage).sum()) / 100
    dauer = max(1.0, (stand - d.zeitstempel.min()).total_seconds() / 86400)
    return {
        "faelle": d.case_id.nunique(),
        "beobachtung_tage": dauer,
        "werttage_eur": werttage,
        "durchschnitt_exposition_eur": werttage / dauer,
        "kalkulatorische_kosten_eur": werttage / 365 * zinssatz_pct / 100,
        "zinssatz_pct": zinssatz_pct,
        "offen_cent": int(offene_posten(d, stand).op_bewegung_cent.sum()),
    }


def scorecard(db: str | Path, jahr: int, eventlog: str | Path) -> pd.DataFrame:
    d = ergebnisrechnung(db)
    dsos = dso_zeitreihe(db)
    lernen = lern_daten()
    log = lade_event_log(eventlog)
    zeilen = []
    for j in (jahr - 1, jahr):
        for q in range(1, 5):
            quartal = f"Q{q}"
            fin = d[(d.geschaeftsjahr == j) & (d.quartal == quartal)]
            if fin.empty:
                continue
            marge = fin.db_ii_cent.sum() / fin.umsatz_cent.sum() * 100
            kunden = dsos[(dsos.geschaeftsjahr == j) & (dsos.quartal == quartal)].dso_tage.iloc[0]
            beob = lernen[(lernen.geschaeftsjahr == j) & (lernen.quartal == quartal)]
            stunden = beob.lernstunden.sum() / beob.teilnehmende.sum() if len(beob) else float("nan")
            # Vollständige YTD-Fälle mit Start im Jahr und Abschluss bis Quartalsende.
            starts = log.groupby("case_id").zeitstempel.min()
            ends = log.groupby("case_id").zeitstempel.max()
            stichtag = pd.Timestamp(j, q * 3, calendar.monthrange(j, q * 3)[1]) + pd.Timedelta(days=1)
            bezahlt = log[log.aktivitaet.isin(["Zahlungseingang", "Gutschrift verrechnen"])].case_id
            ids = starts[(starts.dt.year == j) & (ends < stichtag) & starts.index.isin(bezahlt)].index
            teil = log[log.case_id.isin(ids)]
            rework = (
                teil.duplicated(["case_id", "aktivitaet"]).groupby(teil.case_id).any().mean() * 100
                if len(teil)
                else float("nan")
            )
            from src.o2c import liefertreue

            treue = liefertreue(log, j, q)
            for perspektive, kpi, ist, ziel, einheit, niedriger in [
                ("Finanzen", "DB-II-Marge", marge, ZIEL_DB_II_MARGE_PCT, "%", False),
                ("Kunden", "DSO", kunden, 50, "Tage", True),
                ("Kunden", "Liefertreue YTD", treue, 95, "%", False),
                ("Interne Prozesse", "Nacharbeitsquote YTD", rework, 15, "%", True),
                ("Lernen & Entwicklung", "Lernstunden je Person", stunden, 20, "Stunden", False),
            ]:
                erfolg = (ziel / ist * 100 if ist else 100) if niedriger else ist / ziel * 100
                status = (
                    "nicht gemessen" if pd.isna(ist) else "grün" if erfolg >= 100 else "gelb" if erfolg >= 90 else "rot"
                )
                zeilen.append(
                    {
                        "geschaeftsjahr": j,
                        "quartal": quartal,
                        "perspektive": perspektive,
                        "kennzahl": kpi,
                        "ist": float(ist),
                        "ziel": ziel,
                        "einheit": einheit,
                        "zielerreichung_pct": float(erfolg),
                        "ampel": status,
                        "niedriger_ist_besser": niedriger,
                    }
                )
    return pd.DataFrame(zeilen)


def scorecard_stand(daten: pd.DataFrame, jahr: int) -> tuple[pd.DataFrame, float]:
    quartal = "Q3" if jahr == 2026 else "Q4"
    d = daten[(daten.geschaeftsjahr == jahr) & (daten.quartal == quartal)].copy()
    vor = daten[(daten.geschaeftsjahr == jahr) & (daten.quartal == ("Q2" if jahr == 2026 else "Q3"))].set_index(
        "kennzahl"
    )
    d["trend"] = [
        float(r.ist - vor.loc[r.kennzahl, "ist"]) if r.kennzahl in vor.index else float("nan") for r in d.itertuples()
    ]
    # Fehlende Perspektiven werden nicht durch andere ersetzt.
    gesamt = (
        float(d.assign(erfolg=d.zielerreichung_pct.clip(0, 100)).groupby("perspektive").erfolg.mean().mean())
        if d.perspektive.nunique() == 4 and d.ist.notna().all()
        else float("nan")
    )
    return d, gesamt
