"""Kennzahlen-Leiste mit periodenreinem Vorjahresvergleich."""

from dataclasses import replace

import pandas as pd
import streamlit as st

from src import ui_design as ui
from src.cockpit import kpis
from src.demo import de
from src.ui_daten import quartale_cache


def kennzahlenleiste(db, gj, dso_reihe, dso_wert, bsc_reihe, bsc_wert, zeige):
    quartale = quartale_cache(db)
    englisch = {
        "Umsatz · Mio. €": "Revenue",
        "DB-II-Marge": "Contribution Margin II",
        "EBIT · Mio. €": "Operating Profit",
    }
    karten = [replace(k, en=englisch.get(k.label, "")) for k in kpis(quartale, gj)[:3]]
    dso_py = dso_reihe[
        (dso_reihe.geschaeftsjahr == gj - 1) & (dso_reihe.quartal == ("Q3" if gj == 2026 else "Q4"))
    ].dso_tage
    dso_delta = dso_wert - float(dso_py.iloc[0]) if len(dso_py) else None
    karten.append(
        ui.Kpi(
            "DSO · Tage",
            de(dso_wert, 1),
            de(dso_delta, 1) + " Tage" if dso_delta is not None else "Kein PY",
            ui.ton_fuer(dso_delta <= 0) if dso_delta is not None else "neutral",
            ("30.09. · PY " if gj == 2026 else "31.12. · PY ")
            + (de(float(dso_py.iloc[0]), 1) if len(dso_py) else "nicht vorhanden"),
            dso_reihe.loc[dso_reihe.geschaeftsjahr == gj, "dso_tage"].tolist(),
            en="Days Sales Outstanding",
        )
    )
    bsc_spark = []
    for _, gruppe in bsc_reihe[bsc_reihe.geschaeftsjahr == gj].groupby("quartal"):
        if gruppe.ist.notna().all():
            bsc_spark.append(
                float(
                    gruppe.assign(erfolg=gruppe.zielerreichung_pct.clip(0, 100))
                    .groupby("perspektive")
                    .erfolg.mean()
                    .mean()
                )
            )
    karten.append(
        ui.Kpi(
            "BSC-Zielerreichung",
            de(bsc_wert, 1) + " %" if pd.notna(bsc_wert) else "nicht gemessen",
            "Stand Q3" if gj == 2026 else "Stand Q4",
            "neutral",
            "Vier Perspektiven",
            bsc_spark,
            en="Scorecard Achievement",
        )
    )
    zeige(ui.kpi_leiste(karten))
    st.caption(
        f"Berichtsperiode: Geschäftsjahr {gj} · "
        + (
            "Januar bis September, Vorjahr (PY) im gleichen Zeitraum"
            if gj == 2026
            else "Gesamtjahr, Vorjahr (PY) zum Vergleich"
        )
    )
    return quartale
