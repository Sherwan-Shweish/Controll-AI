"""Seiten der Anwendung; Daten und Sitzungsdienste werden explizit übergeben."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from src import ui_design as ui
from src import ui_diagramme as dia
from src import ui_strategie as strategie_ui
from src.agent import AgentAnswer, AgentError, Intent, LLMError, SQLGuardError
from src.analytics import (
    deckungsbeitragsrechnung,
)
from src.bericht_export import berichtseiten, erstelle_pdf, erstelle_pptx, excel_gegenpruefung
from src.demo import DEMO_FRAGEN, de
from src.exporter import bsc_tabelle
from src.seed_data import PROJEKTTEXTE
from src.textextraktion import abdeckung, extrahiere_pdf, fundstellen_text, text_zu_seiten, vorfiltern
from src.ui_anzeigen import abschnitt, kennzahl, sicherer_text, tabelle_anzeigen
from src.zwischenspeicher import dateicache

deckungsbeitragsrechnung = dateicache(deckungsbeitragsrechnung)


def bericht(EVENTLOG_PATH, audit, bsc_stand, bsc_wert, dso_wert, ergebnis_jahr, gj, prozess, szenario_aktuell):
    if szenario_aktuell is None:
        raise ValueError("Simulationsbasis nicht verfügbar.")
    bericht_fakten, bericht_kontext = strategie_ui.berichtsfakten(
        ergebnis_jahr, gj, dso_wert, bsc_wert, szenario_aktuell
    )
    st.session_state["bericht_basis"] = (bericht_fakten, bericht_kontext)
    management_kommentare = strategie_ui.management(bericht_fakten, bericht_kontext, audit)
    if st.button("Management-Exporte vorbereiten", key="management_export"):
        seiten = berichtseiten(
            ergebnis_jahr,
            gj,
            szenario_aktuell,
            bsc_stand,
            prozess(str(EVENTLOG_PATH)).to_facts(),
            management_kommentare,
            bericht_fakten,
            bericht_kontext,
        )
        st.download_button("Management-Bericht PowerPoint", erstelle_pptx(seiten), file_name=f"ControllAI_{gj}.pptx")
        st.download_button("Management-Bericht PDF", erstelle_pdf(seiten), file_name=f"ControllAI_{gj}.pdf")
        st.download_button(
            "Excel mit Formel-Gegenprüfung",
            excel_gegenpruefung(ergebnis_jahr, szenario_aktuell),
            file_name=f"ControllAI_Gegenpruefung_{gj}.xlsx",
        )
        from src.kommentare import fingerprint, freigegebene

        frei = freigegebene(management_kommentare, bericht_fakten, bericht_kontext)
        st.session_state["berichtstand"] = {
            "kontext": fingerprint(bericht_kontext),
            "ids": [i for k in frei for i in k.fakten_ids],
        }
        audit.ergaenze("EXPORT", "Management", "Berichte nur mit aktuell freigegebenen Kommentaren vorbereitet.")


def sql(agent, frage_setzen, ki_fehler, leitfrage, pruefstatus):
    st.caption("Strategische Datenfragen. Monatliche Plan-Ist-Abweichungszerlegung → VarianceAI.")
    leitfrage("sql")
    sicherer_text("**Beispielfragen**")
    kurztitel = {
        "abweichung": "Plan-Ist-Abweichung Q3 2025",
        "kosten": "Budgetüberschreitungen 2025",
        "yoy": "Umsatz zum Vorjahr je Quartal",
        "marge": "Höchste DB-Marge 2025",
        "ausreisser": "Markierte Ausreißer",
    }
    beispiele = [d for d in DEMO_FRAGEN if d.id in {"yoy", "marge", "ausreisser"}]
    angriff = next(d for d in DEMO_FRAGEN if d.id == "angriff")
    spalten = st.columns(3)
    for i, demo in enumerate(beispiele):
        spalten[i % 3].button(
            kurztitel.get(demo.id, demo.frage),
            key=f"bsp_{demo.id}",
            on_click=frage_setzen,
            args=(demo.frage,),
            help=demo.frage,
            width="stretch",
        )
    spalten[len(beispiele) % 3].button(
        "🛡️ Sicherheitstest: Daten löschen",
        key="bsp_angriff",
        on_click=frage_setzen,
        args=(angriff.frage,),
        help=angriff.frage,
        width="stretch",
    )
    with st.form("frageformular", border=False):
        st.text_input(
            "Ihre Frage",
            key="frage",
            placeholder="z. B. Welche Kostenstellen haben 2025 ihr Budget am stärksten überschritten?",
        )
        gesendet = st.form_submit_button("Frage stellen", type="primary")
    if gesendet:
        st.session_state["frage_ausfuehren"] = True
    if st.session_state.pop("frage_ausfuehren", False) and st.session_state.get("frage", "").strip():
        frage = st.session_state["frage"].strip()
        with st.spinner("Abfrage wird erzeugt, geprüft und ausgeführt …"):
            try:
                st.session_state["sql_ergebnis"] = ("ok", frage, agent.ask(frage, intent=Intent.TEXT_TO_SQL))
            except SQLGuardError as exc:
                st.session_state["sql_ergebnis"] = ("blockiert", frage, exc)
            except (AgentError, LLMError) as exc:
                st.session_state["sql_ergebnis"] = ("fehler", frage, exc)
    if "sql_ergebnis" in st.session_state:
        art, frage, inhalt = st.session_state["sql_ergebnis"]
        sicherer_text(f"#### {frage}")
        if art == "blockiert":
            st.error(f"**Vom SQL-Guard blockiert:** {inhalt}", icon="🛡️")
            if getattr(inhalt, "sql", None):
                st.code(inhalt.sql, language="sql")
            st.caption(
                "Sicherheitsverstöße werden protokolliert und bewusst nicht zur „Korrektur“ "
                "an das Sprachmodell zurückgegeben. Die Datenbank ist unverändert."
            )
        elif art == "fehler":
            ki_fehler(inhalt)
        else:
            antwort: AgentAnswer = inhalt
            with st.container(border=True):
                sicherer_text(antwort.antwort)
            if antwort.sql_result is not None:
                pruefstatus(antwort)
                links, rechts = st.columns([1, 1.2])
                with links:
                    sicherer_text("**Ausgeführte Read-Only-Abfrage**")
                    st.code(antwort.sql_result.sql, language="sql")
                    st.caption(
                        f"{antwort.sql_result.row_count} Zeilen · {de(antwort.sql_result.duration_ms, 1)} ms"
                        + (" · Ergebnis gekürzt" if antwort.sql_result.truncated else "")
                    )
                with rechts:
                    sicherer_text("**Ergebnis**")
                    tabelle_anzeigen(
                        pd.DataFrame(antwort.sql_result.rows, columns=antwort.sql_result.columns),
                        hide_index=True,
                        width="stretch",
                    )
            for warnung in antwort.warnungen:
                st.caption(f"Hinweis: {warnung}")
            with st.expander("Arbeitsschritte des Agenten"):
                for schritt in antwort.trace:
                    sicherer_text(f"- {schritt}")
    with st.expander("Warum ist das sicher? – Parser, Whitelist und Ressourcenlimits"):
        sicherer_text(
            "1. **SQL-Parser (sqlglot):** genau eine Anweisung, nur `SELECT`/`WITH`, "
            "keine Kommentare, keine schreibenden Schlüsselwörter\n2. "
            "**Read-Only-Verbindung:** Datenbank im Modus `mode=ro`, zusätzlich `PRAGMA "
            "query_only`\n3. **SQLite-Authorizer:** Tabellen-/Spalten-Whitelist und "
            "freigegebene Funktionen\n4. **Ressourcenlimits:** Zeitlimit je Abfrage und "
            "begrenzte Zeilenzahl\n\nDanach prüft die Faktenprüfung jede Zahl der "
            "formulierten Antwort gegen das Abfrageergebnis."
        )


def bsc(PERSPEKTIVEN, agent, audit, bsc_reihe, diagramm, gj, ki_fehler, modus):
    strategie_ui.balanced_scorecard(bsc_reihe, gj)
    abschnitt("BSC-Textanalyse · DAX-40-Methodik")
    sicherer_text(
        "Digitalisierungsprojekte werden den vier Perspektiven der **Balanced "
        "Scorecard** zugeordnet – nach der *Zielsetzung*, nicht nach der Technologie. "
        "Das **Drei-Schichten-Prinzip** hält Originalzitat, KI-Vorschlag und "
        "menschliche Entscheidung getrennt; der KI-Vorschlag wird nie überschrieben."
    )
    quelle = st.radio(
        "Textquelle",
        ["Beispieltexte (12 fiktive Berichtsauszüge)", "Eigene Datei (PDF oder TXT)"],
        horizontal=True,
        key="bsc_quelle",
    )
    dokumente: list[dict[str, Any]] = []
    if quelle.startswith("Beispiel"):
        optionen = {f"{t['id']} · {t['unternehmen']} ({t['berichtsjahr']})": t for t in PROJEKTTEXTE}
        auswahl = st.multiselect("Berichtsauszüge", list(optionen), default=list(optionen), key="bsc_auswahl")
        dokumente = [
            {
                "id": optionen[a]["id"],
                "text": optionen[a]["text"],
                "quelle": f"{optionen[a]['unternehmen']} {optionen[a]['berichtsjahr']}, S. {optionen[a]['seite']}",
                "referenz": optionen[a]["erwartung"]["perspektive"],
            }
            for a in auswahl
        ]
        with st.expander("Ausgewählte Texte lesen"):
            for d in dokumente:
                sicherer_text(f"**{d['id']} · {d['quelle']}**")
                st.write(d["text"])
    else:
        datei = st.file_uploader("Geschäftsbericht oder Projektbeschreibung", type=["pdf", "txt"], key="bsc_upload")
        if datei is not None:
            try:
                seiten = (
                    extrahiere_pdf(datei.getvalue())
                    if datei.name.lower().endswith(".pdf")
                    else text_zu_seiten(datei.getvalue().decode("utf-8", errors="replace"))
                )
                funde = vorfiltern(seiten)
                ab = abdeckung(seiten, funde)
                a, b, c = st.columns(3)
                kennzahl(a, "Seiten", ab["seiten"])
                kennzahl(b, "Seiten mit Treffern", ab["seiten_mit_treffern"])
                kennzahl(c, "Fundstellen für die KI", ab["fundstellen"])
                with st.expander("Fundstellen der Vorfilterung (Suchdiktionär)"):
                    for fs in funde[:50]:
                        sicherer_text(f"**S. {fs.seite}** · Treffer: {', '.join(fs.treffer)}")
                        st.caption(fs.text[:600])
                if funde:
                    dokumente = [
                        {"id": "Upload", "text": fundstellen_text(funde), "quelle": datei.name, "referenz": None}
                    ]
                if modus.demo:
                    st.info(
                        "Im Demo-Modus sind Muster-Antworten nur für die Beispieltexte hinterlegt. "
                        "Die Vorfilterung oben läuft echt; für die Klassifikation eigener Dateien "
                        "einen API-Schlüssel eintragen."
                    )
            except Exception as exc:
                st.error(f"Die Datei konnte nicht gelesen werden: {exc}")
    if st.button("KI-Analyse starten", type="primary", key="btn_bsc", disabled=not dokumente):
        zeilen = []
        with st.spinner("Texte werden klassifiziert …"):
            try:
                for d in dokumente:
                    antwort = agent.classify_bsc(d["text"], source=d["quelle"])
                    tabelle_bsc = bsc_tabelle(antwort.bsc_initiativen)
                    if not tabelle_bsc.empty:
                        tabelle_bsc.insert(0, "text_id", d["id"])
                        tabelle_bsc["referenz"] = d["referenz"]
                        zeilen.append(tabelle_bsc)
                st.session_state["bsc_basis"] = pd.concat(zeilen, ignore_index=True) if zeilen else pd.DataFrame()
                audit.ergaenze("ANALYSE", "BSC", "Projekttexte klassifiziert; Zitate geprüft.")
                st.session_state["bsc_lauf"] = st.session_state.get("bsc_lauf", 0) + 1
            except (AgentError, LLMError) as exc:
                ki_fehler(exc)
    basis: pd.DataFrame | None = st.session_state.get("bsc_basis")
    if basis is not None and basis.empty:
        st.info("In den ausgewählten Texten wurden keine Digitalisierungsprojekte identifiziert.")
    elif basis is not None:
        abschnitt("Prüfen und entscheiden")
        st.caption(
            "Spalte **Finale Perspektive** ändern, um den KI-Vorschlag zu überstimmen; "
            "**Geprüft** anhaken, um die Entscheidung freizugeben. Markierte Fälle zuerst "
            "prüfen."
        )
        editor_basis = basis.copy()
        editor_basis["ki_konfidenz"] = editor_basis.ki_konfidenz.map(lambda v: de(v * 100, 1) + " %")
        bearbeitet = st.data_editor(
            editor_basis[
                [
                    "text_id",
                    "titel",
                    "ki_perspektive",
                    "ki_technologiefeld",
                    "ki_konfidenz",
                    "zitat_verifiziert",
                    "pruefung_erforderlich",
                    "finale_perspektive",
                    "geprueft",
                ]
            ],
            key=f"bsc_editor_{st.session_state.get('bsc_lauf', 0)}",
            hide_index=True,
            width="stretch",
            height=36 * (len(basis) + 1) + 4,
            disabled=[
                "text_id",
                "titel",
                "ki_perspektive",
                "ki_technologiefeld",
                "ki_konfidenz",
                "zitat_verifiziert",
                "pruefung_erforderlich",
            ],
            column_config={
                "text_id": "Text",
                "titel": st.column_config.TextColumn("Projekt", width="medium"),
                "ki_perspektive": "KI-Vorschlag",
                "ki_technologiefeld": "Technologiefeld",
                "ki_konfidenz": st.column_config.TextColumn("Konfidenz (%)"),
                "zitat_verifiziert": st.column_config.CheckboxColumn("Zitat belegt"),
                "pruefung_erforderlich": st.column_config.CheckboxColumn("Prüfen!"),
                "finale_perspektive": st.column_config.SelectboxColumn(
                    "Finale Perspektive", options=PERSPEKTIVEN, required=True
                ),
                "geprueft": st.column_config.CheckboxColumn("Geprüft"),
            },
        )
        ergebnis = basis.copy()
        ergebnis["finale_perspektive"] = bearbeitet["finale_perspektive"].to_numpy()
        ergebnis["geprueft"] = bearbeitet["geprueft"].to_numpy()
        ergebnis["status"] = [
            ("überstimmt" if fin != ki else "bestätigt") if ok else "offen"
            for fin, ki, ok in zip(
                ergebnis["finale_perspektive"], ergebnis["ki_perspektive"], ergebnis["geprueft"], strict=True
            )
        ]
        st.session_state["bsc_ergebnis"] = ergebnis
        k = st.columns(5)
        kennzahl(k[0], "Projekte", len(ergebnis))
        kennzahl(k[1], "Zitate belegt", f"{int(ergebnis['zitat_verifiziert'].sum())} / {len(ergebnis)}")
        kennzahl(k[2], "Zur Prüfung markiert", int(ergebnis["pruefung_erforderlich"].sum()))
        kennzahl(
            k[3],
            "Bestätigt · überstimmt",
            f"{(ergebnis['status'] == 'bestätigt').sum()} · {(ergebnis['status'] == 'überstimmt').sum()}",
        )
        kennzahl(k[4], "Offen", int((ergebnis["status"] == "offen").sum()))
        links, rechts = st.columns([1, 1.3])
        with links:
            verteilung = ergebnis["finale_perspektive"].value_counts().reindex(PERSPEKTIVEN, fill_value=0)
            diagramm(
                dia.balken(
                    pd.DataFrame({"Perspektive": verteilung.index, "Projekte": verteilung.values}),
                    "Perspektive",
                    "Projekte",
                    "Projekte",
                )
            )
            mit_ref = ergebnis[ergebnis["referenz"].notna()]
            if not mit_ref.empty:
                ki_treffer = (mit_ref["ki_perspektive"] == mit_ref["referenz"]).mean() * 100
                final_treffer = (mit_ref["finale_perspektive"] == mit_ref["referenz"]).mean() * 100
                sicherer_text(
                    f"**Abgleich mit den Referenzlabels:** KI-Vorschlag {de(ki_treffer, 0)} % · "
                    f"nach menschlicher Prüfung {de(final_treffer, 0)} % ({len(mit_ref)} Projekte)"
                )
        with rechts:
            sicherer_text("**Prüfansicht: Originalzitat → KI-Vorschlag → Entscheidung**")
            projekt = st.selectbox(
                "Projekt",
                ergebnis.index,
                format_func=lambda i: (
                    ("⚠️ " if ergebnis.loc[i, "pruefung_erforderlich"] else "")
                    + f"{ergebnis.loc[i, 'text_id']} · {ergebnis.loc[i, 'titel']}"
                ),
                key="bsc_projekt",
            )
            p = ergebnis.loc[projekt]
            originaltext = next((d["text"] for d in dokumente if d["id"] == p["text_id"]), "")
            with st.container(border=True):
                sicherer_text("**① Originalzitat**")
                if originaltext and p["belegzitat"] in originaltext:
                    sicherer_text(originaltext.replace(p["belegzitat"], f":orange-background[{p['belegzitat']}]"))
                else:
                    sicherer_text(f"> {p['belegzitat']}")
                if p["zitat_verifiziert"]:
                    st.success("Zitat wörtlich im Originaltext gefunden.", icon="✅")
                else:
                    st.error(
                        "Zitat nicht wörtlich im Originaltext – möglicherweise umformuliert. Bitte prüfen.", icon="❌"
                    )
                sicherer_text("**② KI-Vorschlag (unverändert gespeichert)**")
                sicherer_text(
                    f"{p['ki_perspektive']} · {p['ki_technologiefeld']} · Konfidenz "
                    f"{de(p['ki_konfidenz'] * 100, 0)} %  \n*{p['ki_begruendung']}*"
                )
                sicherer_text("**③ Menschliche Entscheidung**")
                sicherer_text(f"{p['finale_perspektive']} · Status: **{p['status']}**")


def prozess(
    EVENTLOG_PATH, agent, anbieter, audit, diagramm, kapital_cache, ki_fehler, leitfrage, prozess, pruefstatus, zeige
):
    leitfrage("prozess")
    st.caption("Order-to-Cash · Makro-Sicht auf das gesamte Fallportfolio. Einkaufsrechnungen und P2P → FlowAudit-AI.")
    pa = prozess(str(EVENTLOG_PATH))
    st.session_state["prozess_zaehler"] = len(pa.faelle)
    pf = pa.to_facts()

    st.caption(
        f"Prozesszeitraum {pf['zeitraum']['von']} bis {pf['zeitraum']['bis']} · unabhängig vom gewählten Finanzjahr."
    )
    from src.analytics import lade_event_log
    from src.o2c import offene_posten, treiber

    log = lade_event_log(EVENTLOG_PATH)
    jahr = st.session_state.get("geschaeftsjahr", 2026)
    stichtag = f"{jahr}-09-30" if jahr == 2026 else f"{jahr}-12-31"
    op = int(offene_posten(log, stichtag).op_bewegung_cent.sum())
    st.write(f"Gebundenes Netto-Debitorenkapital am {pd.Timestamp(stichtag):%d.%m.%Y}: {de(op / 100, 2)} €")
    st.caption(
        "DSO und offene Posten stammen aus denselben Faktura- und Zahlungsereignissen. "
        "Offene Fälle sind rechtszensiert; deren letzte Aktivität ist kein Zahlungseingang. "
        "Durchlaufzeiten unten beschreiben beobachtete Verläufe, keine abgeschlossene O2C-Dauer."
    )
    tabelle_anzeigen(
        treiber(log, stichtag)[["kunden_nr", "gebunden_eur", "dso_beitrag_tage", "variante"]],
        hide_index=True,
        width="stretch",
        column_config={
            "Kunde": st.column_config.TextColumn(width=250),
            "Netto-OP (€)": st.column_config.TextColumn(width=150),
            "DSO-Beitrag (Tage)": st.column_config.TextColumn(width=155),
            "Beobachtete Variante": st.column_config.TextColumn(width=400),
        },
    )
    eng = pf["engpaesse"][0]
    zeige(
        ui.karte(
            ui.statistik(
                [
                    (de(pf["anzahl_faelle"]), "Fälle", "neutral"),
                    (de(pf["anzahl_varianten"]), "Varianten", "neutral"),
                    (de(pf["durchlaufzeit_tage"]["median"], 1) + " Tage", "Median", "neutral"),
                    (de(pf["nacharbeit"]["quote_pct"], 1) + " %", "Nacharbeit", "warnung"),
                ]
            ),
            "Prozessportfolio",
        )
    )
    st.error(f"Engpass: {eng['uebergang']} · {de(eng['anteil_an_gesamtzeit_pct'], 1)} % der gesamten Übergangszeit.")
    links, rechts = st.columns([1.4, 1])
    with links:
        abschnitt("Wartezeit nach Übergang")
        ue = pa.uebergaenge.head(8).copy()
        ue["Übergang"] = ue["von"] + " → " + ue["nach"]
        diagramm(dia.balken(ue, "Übergang", "anteil_gesamtzeit_pct", "%", kosten=True, hoehe=320))
    with rechts:
        abschnitt("Durchlaufzeiten")
        diagramm(dia.verteilung(pa.faelle))
    with st.expander("Prozesslandkarte und Varianten", expanded=False):
        zeige(dia.prozesslandkarte(pa.uebergaenge))
        st.caption("Kanten: Fallübergänge und Median in Stunden; gestrichelt = Rücksprung, rot = größter Zeitanteil.")
        zeige(
            ui.karte(
                ui.rangliste(
                    [
                        (
                            r.von + " → " + r.nach,
                            de(r.anzahl) + " Übergänge",
                            de(r.median_h, 1) + " h",
                            r.anteil_gesamtzeit_pct / 100,
                            "schlecht" if i == 0 else "neutral",
                        )
                        for i, r in enumerate(pa.uebergaenge.itertuples())
                    ]
                ),
                "Übergänge · Median",
            )
        )
        tabelle_anzeigen(pa.varianten, hide_index=True, width="stretch")
    if st.button("BPMN-Vorschläge erzeugen", type="primary", key="btn_bpmn"):
        try:
            st.session_state[f"bpmn_{anbieter}"] = agent.analyze_process(pf, process_name="Order-to-Cash")
            audit.ergaenze("ANALYSE", "Prozess", "BPMN-Vorschläge erzeugt und Zahlen geprüft.")
        except (AgentError, LLMError) as exc:
            ki_fehler(exc)
    if f"bpmn_{anbieter}" in st.session_state:
        vorschlag = st.session_state[f"bpmn_{anbieter}"]
        pruefstatus(vorschlag)
        sicherer_text(vorschlag.antwort)


def simulation(audit, ergebnis_jahr, gj):
    return strategie_ui.simulation(ergebnis_jahr, gj, audit)


def portfolio(ergebnis_jahr):
    strategie_ui.profitabilitaet(ergebnis_jahr)


def cockpit(
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
):
    leitfrage("cockpit")
    with st.expander("So ist die App aufgebaut", expanded=False):
        tabelle_anzeigen(
            pd.DataFrame(
                [
                    ("Management-Cockpit", "ERP und Stammdaten", FRAGEN["cockpit"], "Geschäftsführung"),
                    ("Profitabilität", "Allokierte Ergebnisrechnung", "Wer trägt den Erfolg?", "Controlling, Vertrieb"),
                    ("Simulation", "Jahresportfolio", "Was wäre wenn?", "Geschäftsführung"),
                    ("Process Mining", "O2C-Event-Log", FRAGEN["prozess"], "Prozessmanagement"),
                    ("Balanced Scorecard", "Kennzahlen und Berichtstexte", FRAGEN["bsc"], "Strategie"),
                    ("KI-Analyst · SQL", "SQL-Datenbank", FRAGEN["sql"], "Fachbereiche"),
                    (
                        "Management-Bericht",
                        "Geprüfte Fakten und Freigaben",
                        "Was darf berichtet werden?",
                        "Controlling",
                    ),
                    ("Agent & Audit", "Sitzungsprotokoll", FRAGEN["audit"], "Controlling, IT"),
                ],
                columns=["Tab", "Datenquelle", "Leitfrage", "Für wen"],
            ),
            hide_index=True,
            width="stretch",
        )
    links, rechts = st.columns([1.5, 1])
    with links:
        zeige(
            ui.karte(
                ui.ablauf(
                    [
                        ("Daten", "fertig"),
                        ("Analyse", "fertig"),
                        ("Simulation", "fertig"),
                        ("Kommentar", "aktiv"),
                        ("Freigabe", "offen"),
                    ]
                )
                + '<p class="va-unter">'
                + ui.e("Simulation im Portfolio; namentliche Freigabe im Bericht.")
                + "</p>"
                + ui.checkliste([(a, "deterministisch", "neutral") for a in aussagen_cache(db, gj)]),
                "BI-Copilot",
            )
        )
    with rechts:
        r = bereinigung(db, str(ROHEXPORT_PATH))
        zeige(
            ui.karte(
                ui.checkliste(
                    [
                        ("Daten-Scan", de(len(tx)) + " Fakturapositionen", "gut"),
                        ("Ausreißer separat", de(int(tx.ist_ausreisser.sum())) + " Positionen", "warnung"),
                        ("Buchungskreis", ", ".join(sorted(tx.buchungskreis.unique())), "neutral"),
                        ("Quellen", "Faktura · Stammdaten · Kosten", "neutral"),
                    ]
                ),
                "Geprüfte Datenbasis",
            )
        )
    steuerung = tx[(tx.ist_ausreisser == 0) & (tx.geschaeftsjahr == gj)]
    dbj = deckungsbeitragsrechnung(steuerung, tabelle(db, "produktfixkosten"), gruppen=["produktkategorie"])
    links, rechts = st.columns(2)
    with links:
        abschnitt("Umsatzentwicklung · AC / PY")
        diagramm(dia.verlauf(quartale, gj))
    with rechts:
        abschnitt("Ergebnisbeitrag nach Produktkategorie")
        diagramm(dia.balken(dbj, "produktkategorie", "db_ii_eur", "€"))
    st.caption(
        "DB I = Umsatz − variable Herstellkosten · DB II = DB I − Erzeugnisfixkosten (Fertigung 4100–4300, "
        "QS 4500) · EBIT = DB II − Unternehmensfixkosten (Instandhaltung 4400) – identisch mit VarianceAI."
    )
    with st.expander("Deckungsbeiträge und Datenqualität", expanded=False):
        tabelle_anzeigen(dbj, hide_index=True, width="stretch")
        if r:
            st.json(r)
        tabelle_anzeigen(tx[(tx.ist_ausreisser == 1) & (tx.geschaeftsjahr == gj)], hide_index=True)
    abschnitt("Management-Kommentar · Entwurf")
    st.caption(
        "Plan-Ist-Analyse → VarianceAI. Dieser KI-Entwurf wird nicht exportiert. "
        "Faktengebundene Freigabe im Tab Management-Bericht."
    )
    f = fakten(db, gj)
    schluessel = f"bericht_{gj}_{anbieter}"
    if st.button("Executive Summary erzeugen", type="primary", key="btn_bericht"):
        try:
            strategie = {
                k: v
                for k, v in f.items()
                if k
                in {
                    "unternehmen",
                    "geschaeftsjahr",
                    "umsatz_eur",
                    "deckungsbeitrag_i_eur",
                    "deckungsbeitrag_ii_eur",
                    "db_i_marge_pct",
                    "db_ii_marge_pct",
                    "betriebsergebnis_eur",
                    "umsatzrentabilitaet_pct",
                }
            }
            from src.agent import ExecutiveSummary

            if modus.demo:
                kommentar = ExecutiveSummary(
                    titel=f"Management-Bericht Geschäftsjahr {gj}",
                    kernaussagen=aussagen_cache(db, gj),
                    handlungsempfehlungen=[],
                    risiken=[],
                    datenhinweise=[],
                )
                st.session_state[schluessel] = kommentar.to_markdown()
            else:
                antwort = agent.generate_executive_summary(strategie, focus="Profitabilität und strategische Steuerung")
                st.session_state[schluessel] = (
                    antwort.antwort if antwort.ist_faktentreu else "Faktenprüfung fehlgeschlagen."
                )
            audit.ergaenze("KOMMENTAR", "Deterministische Fakten", "Strategischer Kommentar als Entwurf erzeugt.")
        except (AgentError, LLMError) as exc:
            ki_fehler(exc)
    if schluessel in st.session_state:
        sicherer_text(st.session_state[schluessel])
