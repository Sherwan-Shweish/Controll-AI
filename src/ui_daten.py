"""Datenzugriff und Berechnungs-Caches der Oberfläche, getrennt von der Verdrahtung."""

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from src import analytics
from src.analytics import ProzessAnalyse, bereinige_sap_export, kennzahlen_bericht, lade_event_log, lade_tabelle
from src.cockpit import kernaussagen, quartalskennzahlen
from src.seed_data import erzeuge_alles
from src.strategie import dso_zeitreihe, ergebnisrechnung, prozess_kapital, scorecard
from src.zwischenspeicher import dateicache


@st.cache_resource(show_spinner="Demo-Daten werden erzeugt …")
def stelle_daten_sicher(db_path: str) -> str:
    db = Path(db_path)
    if not db.exists():
        if db.name != "controlling_erp.db":
            raise FileNotFoundError("Datenbank nicht gefunden; DB_PATH prüfen.")
        erzeuge_alles(db.parent)
    return str(db)


@dateicache
def tabelle(db: str, name: str) -> pd.DataFrame:
    return lade_tabelle(db, name)


@dateicache
def fakten(db: str, gj: int) -> dict[str, Any]:
    return kennzahlen_bericht(db, gj)


@dateicache
def bereinigung(db: str, rohexport: str) -> dict[str, Any] | None:
    if not Path(rohexport).exists():
        return None
    roh = pd.read_csv(rohexport, sep=";", dtype=str, keep_default_na=False)
    (_, report) = bereinige_sap_export(roh, tabelle(db, "materialien"), tabelle(db, "kunden"))
    return report.model_dump()


@dateicache
def prozess(eventlog: str) -> ProzessAnalyse:
    return analytics.analysiere_prozess(lade_event_log(eventlog), prozessname="Order-to-Cash · Makro-Sicht")


@dateicache
def strategiedaten(db: str, jahr: int, log: str):
    return (ergebnisrechnung(db), dso_zeitreihe(db), scorecard(db, jahr, log))


@dateicache
def kapital_cache(pfad):
    return prozess_kapital(lade_event_log(pfad))


quartale_cache = dateicache(quartalskennzahlen)
aussagen_cache = dateicache(kernaussagen)
