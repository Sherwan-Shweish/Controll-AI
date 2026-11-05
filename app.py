"""ControllAI: Aufbau, Sitzungsdienste und Verdrahtung der Fachseiten."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit import config as st_config

from desktop import praeferenzen
from src import ui_design as ui
from src import ui_seiten as seiten
from src.agent import AgentAnswer, AgentConfig
from src.audit import AuditProtokoll
from src.bericht_export import powerbi_strategie
from src.demo import erstelle_agent
from src.diagnose import bericht as diagnosebericht
from src.laufzeit import anbieter_vorauswahl, fehlender_zugang, lade_geheimnisse, laufzeit
from src.strategie import scorecard_stand
from src.ui_anzeigen import abschnitt
from src.ui_daten import (
    aussagen_cache,
    bereinigung,
    fakten,
    kapital_cache,
    prozess,
    stelle_daten_sicher,
    strategiedaten,
    tabelle,
)

st.set_page_config(
    page_title="ControllAI · Enterprise-BI-Copilot",
    page_icon=str(Path(__file__).parent / "static/favicon.png"),
    layout="wide",
)
lade_geheimnisse()
UMSCHALTBAR = laufzeit() in {"desktop", "lokal"}
darstellung = (
    st.session_state.setdefault("darstellung", praeferenzen.lade()["darstellung"]) if UMSCHALTBAR else "dunkel"
)
ui.setze_modus(darstellung)
if UMSCHALTBAR:
    thema_geaendert = False
    for schluessel, wert in ui.STREAMLIT_THEMA[darstellung].items():
        if st_config.get_option(schluessel) != wert:
            st_config.set_option(schluessel, wert)
            thema_geaendert = True
    if thema_geaendert:
        st.rerun()
st.html(ui.stylesheet())
PERSPEKTIVEN = ["Finanzen", "Kunden", "Interne Prozesse", "Lernen & Entwicklung"]
CONFIG = AgentConfig.from_env()
DB_PATH = CONFIG.db_path
SAMPLE_DIR = DB_PATH.parent / "sample"
EVENTLOG_PATH = SAMPLE_DIR / "event_log_o2c.csv"
ROHEXPORT_PATH = SAMPLE_DIR / "sap_export_faktura.csv"
FRAGEN = {
    "cockpit": "Welche Kunden, Produkte und Prozesse tragen den Erfolg – und wohin steuern wir?",
    "prozess": "Wo verlieren wir im Gesamtprozess Zeit?",
    "bsc": "Welche Digitalisierungsprojekte zahlen auf welche Unternehmensziele ein?",
    "sql": "Wie bekommen Entscheider verlässliche Antworten ohne BI-Wartezeit?",
    "audit": "Welche Schritte hat der Agent ausgeführt – und was wurde blockiert?",
}
TABS = ["Cockpit", "Portfolio", "Prozesse", "Scorecard", "KI-Analyst", "Bericht", "Agent & Audit"]


def zeige(html: str) -> None:
    st.html(html)


def leitfrage(modul: str) -> None:
    zeige(ui.leitfrage(FRAGEN[modul]))


def diagramm(chart) -> None:
    st.altair_chart(chart, theme=None, width="stretch")


@contextmanager
def fehlergrenze(name: str):
    try:
        yield
    except Exception as exc:
        st.error(f"{name} konnte nicht vollständig geladen werden. Andere Tabs bleiben nutzbar.")
        st.caption("Systemprüfung öffnen und Datenquelle prüfen.")
        audit.ergaenze("FEHLER", "Tab", f"{name}: {type(exc).__name__}")


def pruefstatus(antwort: AgentAnswer) -> None:
    if antwort.ist_faktentreu:
        st.success("Faktenprüfung bestanden: Jede Zahl der Antwort ist in den Quelldaten belegt.")
    else:
        st.warning("Faktenprüfung: unbelegte Zahlen; Formulierung nicht zur Übernahme freigegeben.")


def ki_fehler(exc: Exception) -> None:
    st.error("Die KI-Anfrage ist fehlgeschlagen. Offline (Mock) wählen oder Zugang prüfen.")
    audit.ergaenze("FEHLER", "KI-Anbieter", type(exc).__name__)


audit = st.session_state.setdefault("audit_protokoll", AuditProtokoll())
try:
    db = stelle_daten_sicher(str(DB_PATH))
except Exception:
    st.error("Daten konnten nicht geladen werden. DB_PATH und Systemprüfung kontrollieren.")
    st.code(diagnosebericht())
    st.stop()
datenstand = (
    Path(db).stat().st_mtime_ns,
    Path(db).stat().st_size,
    EVENTLOG_PATH.stat().st_mtime_ns if EVENTLOG_PATH.exists() else 0,
)
with st.sidebar:
    zeige(
        '<div class="va va-marke"><div '
        'class="va-logo">Σ</div><div><b>ControllAI</b><small>Profitabilität · '
        "Strategie · Prozesse</small></div></div>"
    )
    jahre = sorted(tabelle(db, "umsatz_transaktionen").geschaeftsjahr.unique().tolist(), reverse=True)
    gj = st.selectbox(
        "Geschäftsjahr",
        jahre,
        key="geschaeftsjahr",
        format_func=lambda j: f"{j} YTD · Jan–Sep" if j == 2026 else str(j),
    )
    anbieter = st.selectbox(
        "KI-Anbieter",
        ["mock", "claude", "gemini"],
        index=["mock", "claude", "gemini"].index(anbieter_vorauswahl()),
        key="ki_anbieter",
        format_func={"mock": "Offline (Mock)", "claude": "Anthropic Claude", "gemini": "Google Gemini"}.get,
    )
    grund = fehlender_zugang(anbieter)
    cfg = CONFIG.model_copy(
        update={
            "provider": "gemini" if anbieter == "gemini" else "anthropic",
            "model": os.getenv("LLM_MODEL") or ("gemini-2.5-flash" if anbieter == "gemini" else "claude-sonnet-5-5"),
        }
    )
    (agent, modus) = erstelle_agent(cfg, demo=anbieter == "mock" or bool(grund))
    agent.sql.audit = audit
    if grund:
        st.warning(grund + " Offline-Modus arbeitet weiter.")
    elif not anbieter == "mock" and modus.demo:
        st.warning("Anbieter konnte nicht geladen werden. uv sync und Zugang prüfen. Offline-Modus arbeitet weiter.")
    if modus.demo:
        st.info("Demo-Modus: regelbasierte Texte, echte Datenbankabfragen und Prüfungen.")
    st.caption(f"Modell: {('mock:deterministisch' if modus.demo else anbieter + ':' + cfg.model)}")
    with st.expander("Systemprüfung", expanded=False):
        st.code(diagnosebericht(), language=None)
    st.divider()
    export_bereich = st.container()
    st.caption("RheinMain Industrietechnik GmbH · fiktiv. Alle Unternehmensdaten sind synthetisch.")
    st.caption("DAX-40-Bezug: Klassifikationsmethodik für Geschäftsberichte; Beispieltexte sind frei erfunden.")
if UMSCHALTBAR:
    (kopf, rechts) = st.columns([5, 1.2], vertical_alignment="center")
    with rechts:
        wahl = st.segmented_control(
            "Darstellung",
            ["dunkel", "hell"],
            default=darstellung,
            key="darstellung_wahl",
            format_func={"dunkel": "Dunkel", "hell": "Hell"}.get,
        )
        if wahl and wahl != darstellung:
            st.session_state["darstellung"] = wahl
            praeferenzen.speichere({"darstellung": wahl})
            st.rerun()
else:
    kopf = st.container()
tx = tabelle(db, "umsatz_transaktionen")
objekte = tabelle(db, "kunden").shape[0] + tabelle(db, "materialien").shape[0] + tabelle(db, "kostenstellen").shape[0]
with kopf:
    zeige(
        ui.kopfzeile(
            "ControllAI",
            "Enterprise-BI-Copilot · Profitabilität · Strategie · Prozesse",
            f"Geschäftsjahr {gj}" + (" · YTD" if gj == 2026 else ""),
            "Stand 30.09.2026 · Jan–Sep" if gj == 2026 else f"Stand 31.12.{gj}",
            [
                ui.pill("Offline · Mock" if modus.demo else "KI · " + anbieter, "akzent", punkt=True),
                ui.pill("Synthetische Daten", "neutral"),
                ui.pill(f"{objekte} Analyseobjekte", "leise"),
            ],
        )
    )
ergebnis_jahr = pd.DataFrame()
bsc_stand = pd.DataFrame()
bsc_wert = dso_wert = float("nan")
dso_reihe = pd.DataFrame(columns=["geschaeftsjahr", "quartal", "dso_tage"])
bsc_reihe = pd.DataFrame(columns=["geschaeftsjahr", "quartal", "ist", "zielerreichung_pct"])
from src.simulation import Annahmen, simuliere

szenario_aktuell = None
with fehlergrenze("Strategische Datenbasis"):
    (ergebnis_alle, dso_reihe, bsc_reihe) = strategiedaten(db, gj, str(EVENTLOG_PATH))
    ergebnis_jahr = ergebnis_alle[ergebnis_alle.geschaeftsjahr == gj]
    (bsc_stand, bsc_wert) = scorecard_stand(bsc_reihe, gj)
    dso_wert = float(
        dso_reihe[
            (dso_reihe.geschaeftsjahr == gj) & (dso_reihe.quartal == ("Q3" if gj == 2026 else "Q4"))
        ].dso_tage.iloc[0]
    )
if not ergebnis_jahr.empty:
    szenario_aktuell = simuliere(ergebnis_jahr, Annahmen(*st.session_state.get("sim_annahmen", [0, 0, 0, 0])))
with fehlergrenze("Kennzahlen-Leiste"):
    from src.ui_kopf import kennzahlenleiste

    quartale = kennzahlenleiste(db, gj, dso_reihe, dso_wert, bsc_reihe, bsc_wert, zeige)

(tab_cockpit, tab_profit, tab_prozess, tab_bsc, tab_sql, tab_bericht, tab_audit) = st.tabs(
    TABS, key="haupttabs", on_change="rerun"
)
tab_sim = tab_profit
with tab_cockpit, fehlergrenze("Management-Cockpit"):
    seiten.cockpit(
        FRAGEN,
        ROHEXPORT_PATH,
        agent,
        anbieter,
        audit,
        aussagen_cache,
        bereinigung,
        db,
        diagramm,
        fakten,
        gj,
        ki_fehler,
        leitfrage,
        modus,
        quartale,
        tabelle,
        tx,
        zeige,
    )
with tab_profit, fehlergrenze("Profitabilität"):
    seiten.portfolio(ergebnis_jahr)
with tab_sim, fehlergrenze("Simulation"):
    szenario_aktuell = seiten.simulation(audit, ergebnis_jahr, gj)
if tab_prozess.open:
    with tab_prozess, fehlergrenze("Process Mining"):
        seiten.prozess(
            EVENTLOG_PATH,
            agent,
            anbieter,
            audit,
            diagramm,
            kapital_cache,
            ki_fehler,
            leitfrage,
            prozess,
            pruefstatus,
            zeige,
        )
with tab_bsc, fehlergrenze("Balanced Scorecard"):
    seiten.bsc(PERSPEKTIVEN, agent, audit, bsc_reihe, diagramm, gj, ki_fehler, modus)


def frage_setzen(text: str) -> None:
    st.session_state["frage"] = text
    st.session_state["frage_ausfuehren"] = True


with tab_sql, fehlergrenze("KI-Analyst"):
    seiten.sql(agent, frage_setzen, ki_fehler, leitfrage, pruefstatus)
with tab_bericht, fehlergrenze("Management-Bericht"):
    seiten.bericht(EVENTLOG_PATH, audit, bsc_stand, bsc_wert, dso_wert, ergebnis_jahr, gj, prozess, szenario_aktuell)
with tab_audit, fehlergrenze("Agent & Audit"):
    from src.ui_audit import zeige_audit

    zeige_audit(CONFIG, agent, audit, leitfrage, tx, ergebnis_jahr)
with export_bereich, fehlergrenze("Export"):
    abschnitt("Datenexport")
    st.caption("Berichte und Excel-Gegenprüfung im Tab Management-Bericht.")
    if st.button("Power-BI-Paket vorbereiten", key="export_vorbereiten"):
        st.download_button(
            "Power-BI-Paket (CSV)",
            powerbi_strategie(db, bsc_reihe, st.session_state.get("bsc_ergebnis")),
            file_name="ControllAI_PowerBI.zip",
            key="dl_powerbi",
        )
