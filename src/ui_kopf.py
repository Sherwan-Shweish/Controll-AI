"""Kennzahlen-Leiste mit periodenreinem Vorjahresvergleich."""

import pandas as pd
import streamlit as st

from src import ui_design as ui
from src.cockpit import kpis
from src.demo import de
from src.ui_daten import quartale_cache


def kennzahlenleiste(db, gj, dso_reihe, dso_wert, bsc_reihe, bsc_wert, zeige):
    quartale = quartale_cache(db)
    karten = kpis(quartale, gj)[:3]
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
            "Vier Perspektiven · Demo-Ziele",
            bsc_spark,
        )
    )
    zeige(ui.kpi_leiste(karten))
    st.caption(
        f"Berichtsperiode: Geschäftsjahr {gj} · "
        + ("Jan–Sep / PY Jan–Sep · " if gj == 2026 else "Ganzjahr / PY Ganzjahr · ")
        + "Sparklines: Quartale · Ausreißer aus Kennzahlen ausgenommen"
    )
    return quartale
