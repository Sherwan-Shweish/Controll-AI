"""Fachliche Bedienflächen der strategischen Erweiterung."""

from __future__ import annotations

from dataclasses import asdict

import pandas as pd
import streamlit as st

from src import ui_design as ui
from src import ui_diagramme as dia
from src.demo import de
from src.kommentare import Fakt, entwurf, fingerprint, freigeben, freigegebene, pruefe
from src.pruefpfad import wesentlich
from src.simulation import Annahmen, simuliere
from src.strategie import abc_analyse, scorecard_stand, verdichte
from src.ui_anzeigen import GRUPPEN, NAMEN, REGIONEN, abschnitt, tabelle_anzeigen
from src.zwischenspeicher import dateicache

simuliere = dateicache(simuliere)
verdichte = dateicache(verdichte)
abc_analyse = dateicache(abc_analyse)


def diagramm(c):
    st.altair_chart(c, theme=None, width="stretch")


def anzahl_kunden(n: int) -> str:
    return f"{n} Kunde" if n == 1 else f"{n} Kunden"


def profitabilitaet(daten: pd.DataFrame):
    st.html(ui.leitfrage("Welche Kunden, Regionen und Produkte tragen den Ergebnisbeitrag?"))
    st.caption(
        "DB I = Umsatz − variable Herstellkosten · DB II = DB I − Erzeugnisfixkosten (Fertigung 4100–4300, "
        "QS 4500) · DB III = DB II − Unternehmensfixkosten (Instandhaltung 4400). Summe DB III = EBIT in VarianceAI."
    )
    cols = st.columns(3)
    region = cols[0].selectbox(
        "Region",
        ["Alle", *sorted(daten.region.unique())],
        key="region_filter",
        format_func=lambda v: REGIONEN.get(v, v),
    )
    produkt = cols[1].selectbox(
        "Produktgruppe",
        ["Alle", *sorted(daten.produktgruppe.unique())],
        key="produkt_filter",
        format_func=lambda v: GRUPPEN.get(v, v),
    )
    kunde = cols[2].selectbox(
        "Kunde", ["Alle", *sorted(daten.kunden_nr.unique())], key="kunden_filter", format_func=lambda v: NAMEN.get(v, v)
    )
    d = daten.copy()
    for feld, wert in [("region", region), ("produktgruppe", produkt), ("kunden_nr", kunde)]:
        if wert != "Alle":
            d = d[d[feld] == wert]
    if d.empty:
        st.info("Für diese Kombination sind keine Daten vorhanden.")
        return
    dimension = st.radio("Verdichtung", ["Kunde", "Region", "Produktgruppe"], horizontal=True)
    feld = {"Kunde": "kunden_nr", "Region": "region", "Produktgruppe": "produktgruppe"}[dimension]
    t = verdichte(d, [feld]).sort_values("db_ii_cent", ascending=False)
    t["Objekt"] = t[feld].map(lambda v: {**NAMEN, **GRUPPEN, **REGIONEN}.get(v, v))
    diagramm(dia.balken(t, "Objekt", "db_ii_eur", "€", hoehe=max(260, len(t) * 33)))
    anzeige = t[[feld, "umsatz_eur", "db_i_eur", "db_ii_eur", "db_iii_eur", "db_ii_marge_pct", "status"]]
    tabelle_anzeigen(
        anzeige.style.format({k: lambda v: de(v, 2) for k in anzeige.columns if k.endswith(("_eur", "_pct"))}).map(
            lambda v: "color: #c54b4b; font-weight: bold" if v == "Negativer DB II" else "", subset=["status"]
        ),
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "Allokation erfolgt vor dem Drill-down. Ein Filter verteilt die Kosten nicht neu. "
        "Schlüssel: Fertigung nach variablen Herstellkosten; Qualitätssicherung nach Demo-Servicegewicht "
        "(Kunden-Endziffer 4 → 12, sonst 1); Instandhaltung nach positivem Umsatz. "
        "Diese Schlüssel sind Annahmen, keine nachgewiesenen Verursachungsbeziehungen."
    )
    abschnitt("Pareto und ABC · ausgewähltes Portfolio")
    abc, f = abc_analyse(d)
    if f["db_anteil_pct"] is not None:
        st.write(
            f"Top-Fünftel: {f['top_kunden']} von {f['kunden']} Kunden ({de(f['kundenanteil_pct'], 1)} %) "
            f"erzielen {de(f['db_anteil_pct'], 1)} % des Netto-DB II. "
            f"{anzahl_kunden(f['negative_kunden'])} mit negativem DB II, "
            f"{f['negative_db_iii_kunden']} mit negativem DB III."
        )
        if f["schwaechster_kunde"] is not None:
            st.write(
                f"Niedrigste DB-II-Marge: {ui.e(NAMEN.get(f['schwaechster_kunde'], f['schwaechster_kunde']))} "
                f"mit {de(f['schwaechste_marge_pct'], 1)} % (Portfolio {de(f['portfolio_marge_pct'], 1)} %)."
            )
    else:
        st.info("Netto-DB II ist nicht positiv; ein Pareto-Anteil am Nettoergebnis wäre nicht aussagekräftig.")
    diagramm(dia.pareto(abc))
    st.caption(
        "Auf volle Kunden aufgerundet: exakt 20 % sind bei kleinen Portfolios oft unmöglich. "
        "ABC nutzt nur positive DB-II-Beiträge; A bis zur überschreitenden "
        "80-%-Position, B bis 95 %, Rest C. "
        "Negative Beiträge sind C. Der Anteil am Netto-DB kann über 100 % liegen."
    )
    tabelle_anzeigen(
        abc[["kunden_nr", "db_ii_eur", "anteil_pct", "kumuliert_pct", "abc", "status"]],
        hide_index=True,
        width="stretch",
    )
    with st.expander("Allokation je Quartal und Detaildimension"):
        tabelle_anzeigen(d, hide_index=True, width="stretch")


def simulation(daten: pd.DataFrame, jahr: int, audit) -> dict:
    abschnitt("Simulation · Preis, Menge und Kosten")
    st.caption(
        "Jahresportfolio ohne Drill-down-Filter. Konstanter Kunden-/Produktmix; keine Elastizität. "
        "Materialanteil der variablen Kosten: 70 % als Demo-Annahme."
    )
    cols = st.columns(4)
    werte = [
        cols[i].slider(label, -50, 50, 0, key=key)
        for i, (label, key) in enumerate(
            [
                ("Preisänderung %", "sim_preis"),
                ("Mengenänderung %", "sim_menge"),
                ("Materialkostenänderung %", "sim_material"),
                ("Fixkostenänderung %", "sim_fix"),
            ]
        )
    ]
    ergebnis = simuliere(daten, Annahmen(*werte))
    st.session_state["sim_annahmen"] = werte
    diagramm(dia.simulationsbruecke(ergebnis))
    cols = st.columns(4)
    for c, (label, feld) in zip(
        cols,
        [("DB I", "db_i_cent"), ("DB II", "db_ii_cent"), ("EBIT", "ebit_cent"), ("Wirkung", "wirkung_cent")],
        strict=True,
    ):
        c.html(ui.karte(ui.statistik([(de(ergebnis[feld] / 100000, 1) + " T€", label, "neutral")])))
    st.caption(
        "Reihenfolge: Preis → Menge → Materialkosten → Fixkosten. Preis-Mengen-Interaktion liegt im Mengeneffekt. "
        + "Variable Kosten skalieren mit der Menge, Fixkosten nur mit ihrem Regler. "
        "Jeder Schritt wird auf Cent gerundet."
    )
    name = st.text_input("Szenarioname", value="Strategievariante", max_chars=80)
    basis_hash = fingerprint({"jahr": int(jahr), "daten": daten.to_dict("records")})
    gespeichert = st.session_state.setdefault("szenarien", {})
    if st.button("Szenario speichern", key="sim_speichern"):
        if not name.strip():
            st.error("Szenarionamen eingeben.")
        else:
            gespeichert[(int(jahr), name.strip())] = {
                "name": name.strip(),
                "jahr": int(jahr),
                "basis_hash": basis_hash,
                **ergebnis,
            }
            audit.ergaenze("SZENARIO", "Simulation", f"Szenario {name.strip()} für {jahr} gespeichert.")
            st.success("Szenario in dieser Sitzung gespeichert.")
    passende = [s for s in gespeichert.values() if s["jahr"] == jahr and s["basis_hash"] == basis_hash]
    if passende:
        abschnitt("Szenarien vergleichen · gleicher Datenstand")
        tabelle_anzeigen(
            pd.DataFrame(
                [
                    {
                        "Szenario": s["name"],
                        **s["annahmen"],
                        "DB I €": s["db_i_cent"] / 100,
                        "DB II €": s["db_ii_cent"] / 100,
                        "EBIT €": s["ebit_cent"] / 100,
                        "Wirkung €": s["wirkung_cent"] / 100,
                    }
                    for s in passende
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    st.caption("Szenarien und Freigaben gelten für die Sitzung. Für dauerhafte Ablage Bericht und Audit exportieren.")
    return ergebnis


def balanced_scorecard(daten: pd.DataFrame, jahr: int):
    st.html(ui.leitfrage("Erreichen wir unsere strategischen Ziele in allen vier Perspektiven?"))
    stand, gesamt = scorecard_stand(daten, jahr)
    st.caption(
        f"Stand {'Q3' if jahr == 2026 else 'Q4'} · Trend zum Vorquartal. Prozessquote: "
        "bis zum Stichtag abgeschlossene YTD-Fälle. DB-II-Ziel = geplante Marge laut VarianceAI-Plan 2026 "
        "(Quartalswert); übrige Ziele sind gesetzte Demo-Ziele."
    )
    for r in stand.itertuples():
        ton = {"grün": "gut", "gelb": "warnung", "rot": "schlecht"}.get(r.ampel, "neutral")
        delta = (
            "nicht gemessen" if pd.isna(r.trend) else de(r.trend, 2) + (" Pp" if r.einheit == "%" else " " + r.einheit)
        )
        st.html(
            ui.karte(
                ui.statistik(
                    [
                        (de(r.ist, 2) + " " + r.einheit if pd.notna(r.ist) else "nicht gemessen", r.kennzahl, ton),
                        (de(r.ziel, 1) + " " + r.einheit, "Ziel", "neutral"),
                        (delta, "Trend zum Vorquartal", "neutral"),
                    ]
                )
                + ui.pill(r.ampel, ton),
                r.perspektive,
            )
        )
    st.write("BSC-Zielerreichung: " + (de(gesamt, 1) + " %" if pd.notna(gesamt) else "nicht vollständig messbar"))
    st.caption(
        "Je Perspektive: Ist/Ziel bzw. Ziel/Ist bei niedriger-ist-besser. Kunden = Mittel aus DSO und Liefertreue. "
        "Gesamt = Mittel der vier Perspektiven, "
        + "je Perspektive auf 100 % begrenzt. Grün ≥100 %, Gelb ≥90 %, sonst Rot. "
        "Fehlende Perspektive → kein Gesamtwert."
    )
    st.html(dia.strategiekette())
    st.caption(
        "Wirkungshypothese: Lernen unterstützt Prozessqualität, diese Kundenziele und finanzielle Ergebnisse. "
        + "Die Pfeile belegen keine statistische Kausalität. DSO ist Zahlungsbindung, kein Zufriedenheitsmaß."
    )
    tabelle_anzeigen(daten[daten.geschaeftsjahr == jahr], hide_index=True, width="stretch")


def berichtsfakten(daten: pd.DataFrame, jahr: int, dso: float, bsc: float, sz: dict) -> tuple[dict, dict]:
    gesamt = verdichte(daten, []).iloc[0]
    fakten = {
        k: Fakt(k, label, float(wert), einheit, stellen)
        for k, label, wert, einheit, stellen in [
            ("umsatz", "Umsatz AC", gesamt.umsatz_eur, "€", 2),
            ("db_ii", "DB II AC", gesamt.db_ii_eur, "€", 2),
            ("ebit", "EBIT AC", gesamt.db_iii_eur, "€", 2),
            ("dso", "DSO am Berichtsstichtag", dso, "Tage", 2),
            ("simulation", "EBIT im aktuellen Szenario", sz["ebit_cent"] / 100, "€", 2),
        ]
    }
    if pd.notna(bsc):
        fakten["bsc"] = Fakt("bsc", "BSC-Zielerreichung Stichtag", bsc, "%", 1)
    kontext = {
        "jahr": int(jahr),
        "daten": daten.to_dict("records"),
        "fakten": {k: asdict(v) for k, v in fakten.items()},
        "szenario": sz,
        "definition": "ControllAI 2.1 DBIII EBIT, DSO 90 Tage, BSC Stichtag",
    }
    return fakten, kontext


def management(fakten: dict, kontext: dict, audit):
    st.html(ui.leitfrage("Welche Aussagen sind belegt und namentlich für das Management freigegeben?"))
    st.caption(
        "Faktensätze werden aus benannten Kennzahlen aufgebaut und vor Freigabe sowie Export erneut geprüft. "
        + "Qualitative Empfehlungen prüft die freigebende Person; die Zahlenprüfung "
        "bestätigt keine Ursache oder Prognose."
    )
    auswahl = [k for k, f in fakten.items() if wesentlich(f)]
    ids = st.multiselect(
        "Fakten für den Kommentar",
        auswahl,
        default=[k for k in ["umsatz", "db_ii", "ebit"] if k in auswahl],
        format_func=lambda k: fakten[k].satz(),
        key="kommentar_fakten",
    )
    empfehlung = st.text_area(
        "Qualitative Empfehlung ohne Zahlen",
        value="Serviceintensive Kunden mit niedriger Marge gemeinsam mit dem Vertrieb prüfen.",
        max_chars=600,
    )
    if st.button("Geprüften Kommentar erstellen", key="kommentar_erstellen"):
        try:
            st.session_state["management_entwurf"] = entwurf(fakten, ids, empfehlung, kontext)
            audit.ergaenze("KOMMENTAR", "Faktenprüfung", "Faktengebundenen Entwurf erzeugt.")
        except ValueError as exc:
            st.error(str(exc))
    k = st.session_state.get("management_entwurf")
    if k:
        st.text(k.text + "\nEmpfehlung: " + k.empfehlung)
        aktuell = pruefe(k, fakten, kontext)
        if aktuell:
            st.success("Faktenprüfung bestanden. Zahlen, Kennzahlenbezug und Datenstand stimmen überein.")
        else:
            st.warning("Daten oder Szenario verändert. Neuen Entwurf erstellen; alte Freigabe ist nicht exportfähig.")
        name = st.text_input("Freigabe durch Vor- und Nachname", key="freigeber")
        bestaetigt = st.checkbox("Ich habe Fakten und qualitative Empfehlung geprüft.", key="freigabe_bestaetigt")
        if st.button("Namentlich freigeben", disabled=not aktuell or not bestaetigt, key="kommentar_freigeben"):
            try:
                frei = freigeben(k, name, fakten, kontext)
                st.session_state.setdefault("management_kommentare", []).append(frei)
                audit.ergaenze("FREIGABE", "Management", f"Kommentar namentlich durch {frei.freigeber} freigegeben.")
                st.success("Kommentar für diesen Daten- und Szenariostand freigegeben.")
            except ValueError as exc:
                st.error(str(exc))
    alle = st.session_state.get("management_kommentare", [])
    gueltig = freigegebene(alle, fakten, kontext)
    st.write(
        f"{len(gueltig)} aktuell freigegebene Kommentare · {len(alle) - len(gueltig)} "
        f"nicht mehr zum Datenstand passend."
    )
    st.caption("Namenseingabe dokumentiert die Verantwortung; sie ersetzt keine Anmeldung oder elektronische Signatur.")
    return alle
