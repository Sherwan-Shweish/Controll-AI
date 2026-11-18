"""Agentenkette und Sicherheitstests nach dem Muster der beiden Suite-Referenzen."""

import streamlit as st

from src import ui_design as ui
from src.demo import de
from src.pruefpfad import pruefpfad
from src.sicherheitstest import pruefe_datentext, pruefe_injection
from src.ui_anzeigen import sicherer_text


def zeige_audit(config, agent, audit, leitfrage, daten, ergebnis):
    leitfrage("audit")
    links, rechts = st.columns(2)
    # Zuerst Aktionen ausführen, anschließend aus dem aktuellen Protokoll zählen.
    if links.button("Datentext-Injection testen", key="datentext_test"):
        if pruefe_datentext(agent):
            st.success("Datentext-Anweisung erkannt und blockiert. Keine BSC-Kennzahl oder Datenbank verändert.")
        else:
            st.error("Datentext-Test fehlgeschlagen.")
    if rechts.button("SQL-Angriff (DELETE) testen", key="injection_test"):
        if pruefe_injection(config, audit):
            st.success("Manipulierter SQL-Vorschlag blockiert. Keine Daten verändert.")
        else:
            st.error("SQL-Test fehlgeschlagen.")
    fakten, kontext = st.session_state.get("bericht_basis", ({}, {}))
    pfad = pruefpfad(
        fakten,
        kontext,
        st.session_state.get("management_kommentare", []),
        st.session_state.get("management_entwurf"),
        st.session_state.get("berichtstand"),
    )
    ereignisse = audit.eintraege
    erlaubt = sum(e.art == "ZUGELASSEN" for e in ereignisse)
    blockiert = sum(e.art == "ABGELEHNT" for e in ereignisse)
    karten = [
        (
            "datenbank",
            "Datenprüfung",
            "Prüft Schlüssel und Währungen, kennzeichnet Ausreißer.",
            "Kennzahlen ohne markierte Ausreißer.",
            f"{de(len(daten))} Positionen · {de(daten.ist_ausreisser.sum())} markiert",
        ),
        (
            "diagramm",
            "Analyse",
            "Python berechnet Deckungsbeiträge, Simulation und Prozesskennzahlen.",
            "Rechnet centgenau – nie die KI.",
            "",
        ),
        (
            "funke",
            "KI-Agent",
            "Formuliert aus geprüften Fakten und übersetzt Fragen in SQL.",
            "Nur Lesezugriff; jede Zahl wird geprüft.",
            f"{erlaubt} zugelassen · {blockiert} blockiert",
        ),
        (
            "person",
            "Freigabe",
            "Name, Fakten und Datenstand gehören zusammen.",
            "Kein Bericht ohne namentliche Freigabe.",
            f"{pfad['stufen'][4]} Kennzahlen freigegeben",
        ),
    ]
    links, rechts = st.columns([1.15, 1])
    with links:
        st.html(
            ui.karte(
                ui.agentenkarten(
                    [
                        ui.Agentenkarte(icon, name, "aktiv", aufgabe, regel, zahl, "neutral")
                        for icon, name, aufgabe, regel, zahl in karten
                    ]
                ),
                "So arbeitet ControllAI",
                "How It Works",
            )
        )
        namen = ["Kennzahlen", "Wesentlich", "Kommentiert", "Faktengeprüft", "Namentlich freigegeben", "Im Bericht"]
        st.html(
            ui.karte(
                ui.trichter([("check", n, "", str(z), "") for n, z in zip(namen, pfad["stufen"], strict=True)]),
                "Von der Kennzahl zum Bericht",
                "From KPI to Report",
            )
        )
    with rechts:
        st.html(
            ui.karte(
                ui.protokoll(
                    [
                        ui.Logeintrag(
                            e.zeit[11:19], e.art, "schlecht" if e.art == "ABGELEHNT" else "neutral", e.schicht, e.grund
                        )
                        for e in ereignisse
                    ]
                ),
                "Audit-Protokoll",
                "Audit Log",
            )
        )
    st.caption(
        f"SQL-Grenzen: höchstens {config.sql_max_rows} Zeilen und {de(config.sql_timeout_seconds, 1)} s je Abfrage."
    )
    with st.expander("Warum Kennzahlen nicht im Bericht stehen"):
        gr = sorted(pfad["gruende"].items(), key=lambda x: -x[1])
        maximum = max((z for _, z in gr), default=1) or 1
        st.html(ui.karte(ui.rangliste([(n, "Kennzahlen", str(z), z / maximum, "leise") for n, z in gr])))
        st.caption(
            "Demo-Wesentlichkeit: Geldbeträge ab 1.000 €; übrige gemessene Kennzahlen vollständig. "
            "„Im Bericht“ zählt im vorbereiteten Export enthaltene, freigegebene Kommentar-Fakten."
        )
    with st.expander("SQL-Guardrails: Abfrage, Entscheidung und Grund"):
        for e in ereignisse:
            if e.sql:
                sicherer_text(f"**{e.art} · {e.schicht}** – {e.grund}")
                st.code(e.sql, language="sql")
        st.json(agent.sql.erlaubte_spalten)
    st.download_button(
        "Audit-Protokoll als JSON",
        audit.exportiere(),
        file_name="ControllAI_Audit.json",
        mime="application/json",
        key="audit_export",
    )
