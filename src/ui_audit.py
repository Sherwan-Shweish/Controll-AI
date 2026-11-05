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
    # Zuerst Aktionen ausführen, anschließend aus dem aktuellen Protokoll zählen (FlowAudit-AI).
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
    analysen = sum(e.art == "ANALYSE" for e in ereignisse)
    prozess = st.session_state.get("prozess_zaehler", 0)
    karten = [
        (
            "datenbank",
            "Datenprüfung",
            "Schlüssel und Währungen prüfen; Ausreißer kennzeichnen.",
            "Fakten ohne markierte Ausreißer.",
            f"{de(len(daten))} Positionen · {de(daten.ist_ausreisser.sum())} markiert",
        ),
        (
            "datenbank",
            "Ergebnis-Engine",
            "DB I → DB II → DB III; Allokation auf Cent.",
            "DB III summiert sich zum EBIT.",
            f"{de(len(ergebnis))} Ergebnisobjekte",
        ),
        (
            "funke",
            "Simulation",
            "Preis, Menge, Material und Fixkosten deterministisch.",
            "Brückensumme = EBIT-Differenz.",
            f"{len(st.session_state.get('szenarien', {}))} gespeicherte Szenarien",
        ),
        (
            "check",
            "Process Mining",
            "Beobachtete Ereignisse, Varianten und Engpässe.",
            "Berechnung beim Öffnen des Prozess-Tabs.",
            f"{de(prozess)} analysierte Fälle",
        ),
        (
            "funke",
            "KI-Agent",
            "Formuliert aus Fakten; Daten sind keine Anweisungen.",
            "Keine eigenständige Freigabe.",
            f"{analysen} protokollierte Analysen",
        ),
        (
            "schild",
            "Faktenprüfung / SQL-Wächter",
            "Zahlenbeleg, Parser, Whitelist und read-only.",
            "Unbelegte Aussagen und Schreibzugriffe sperren.",
            f"{erlaubt} zugelassen · {blockiert} blockiert",
        ),
        (
            "person",
            "Freigabe",
            "Name, Fakten und Datenstand gehören zusammen.",
            "Nach einer Änderung erneut prüfen und freigeben.",
            f"{pfad['stufen'][4]} Kennzahlen namentlich freigegeben",
        ),
    ]
    st.html(
        ui.agentenkarten(
            [
                ui.Agentenkarte(icon, name, "Aktiv", aufgabe, regel, zahl, "neutral")
                for icon, name, aufgabe, regel, zahl in karten
            ]
        )
    )
    st.caption(
        "Berichtstrichter: aktuelle Kennzahlobjekte, nicht Kunden oder Transaktionszeilen. "
        "Demo-Wesentlichkeit: Geldbeträge ab 1.000 €; übrige gemessene Kennzahlen vollständig. "
        "„Im Bericht“ zählt im vorbereiteten Export enthaltene, freigegebene Kommentar-Fakten."
    )
    links, rechts = st.columns([1, 1.4])
    with links:
        namen = ["Analyseobjekte", "Wesentlich", "Kommentiert", "Faktengeprüft", "Namentlich freigegeben", "Im Bericht"]
        st.html(
            ui.karte(
                ui.trichter(
                    [
                        ("check", n, "Aktueller Daten- und Szenariostand", str(z), "Kennzahlen")
                        for n, z in zip(namen, pfad["stufen"], strict=True)
                    ]
                ),
                "Vom Fakt zum Bericht",
            )
        )
        gr = sorted(pfad["gruende"].items(), key=lambda x: -x[1])
        maximum = max((z for _, z in gr), default=1) or 1
        st.html(
            ui.karte(
                ui.rangliste([(n, "Kennzahlobjekte", str(z), z / maximum, "leise") for n, z in gr]),
                "Warum nicht berichtet",
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
                "Append-only · Sitzungsprotokoll",
            )
        )
    st.caption(
        f"Zeilenlimit: {config.sql_max_rows} · Zeitlimit: {de(config.sql_timeout_seconds, 1)} s. "
        "Hash-Kette exportierbar; kein revisionssicheres Archiv."
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
