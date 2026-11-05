"""Deutsche Anzeigegrenze; Datenfelder bleiben intern unverändert.

Fremdtexte gehen ausschließlich durch maskierte HTML-Bausteine. Markdown ist
nur für statische, vertrauenswürdige Texte zulässig; niemals ui.e → Markdown.
"""

import re

import pandas as pd
import streamlit as st

from src import suite_stammdaten as suite
from src import ui_design as ui
from src.demo import de

NAMEN = {nr: f"{name} ({nr})" for nr, name, _ in suite.KUNDEN}
MATERIALNAMEN = {m[0]: f"{m[1]} ({m[0]})" for m in suite.MATERIALIEN}
GRUPPEN = dict(suite.PRODUKTGRUPPEN)
REGIONEN = {nr: name for nr, name, _ in suite.REGIONEN}
TITEL = {
    "kunden_nr": "Kunde",
    "gebunden_eur": "Netto-OP (€)",
    "dso_beitrag_tage": "DSO-Beitrag (Tage)",
    "variante": "Beobachtete Variante",
    "material_nr": "Material",
    "faktura_nr": "Faktura",
    "ist_ausreisser": "Ausreißer",
    "ist_storno": "Storno",
    "ausreisser_grund": "Ausreißergrund",
    "ausreisser_score": "Ausreißer-Score",
    "produktgruppe": "Produktgruppe",
    "produktkategorie": "Produktbezeichnung",
    "geschaeftsjahr": "Geschäftsjahr",
    "db_i_eur": "DB I (€)",
    "db_ii_eur": "DB II (€)",
    "db_iii_eur": "DB III (€)",
    "db_ii_marge_pct": "DB-II-Marge (%)",
    "zielerreichung_pct": "Zielerreichung (%)",
    "ist": "Ist",
    "ziel": "Ziel",
    "preis_pct": "Preis (%)",
    "menge_pct": "Menge (%)",
    "material_pct": "Materialkosten (%)",
    "fix_pct": "Fixkosten (%)",
    "niedriger_ist_besser": "Niedriger ist besser",
}


def spaltentitel(name):
    name = str(name)
    return TITEL.get(
        name,
        name.replace("_eur", " (€)").replace("_pct", " (%)").replace("_cent", " (Cent)").replace("_", " ").capitalize(),
    )


def anzeigedaten(daten):
    d = daten.copy() if isinstance(daten, pd.DataFrame) else daten.data.copy()
    for k in d:
        if k == "kunden_nr":
            d[k] = d[k].map(lambda v: NAMEN.get(v, v))
        elif k == "material_nr":
            d[k] = d[k].map(lambda v: MATERIALNAMEN.get(v, v))
        elif k == "produktgruppe":
            d[k] = d[k].map(lambda v: GRUPPEN.get(v, v))
        elif k == "region":
            d[k] = d[k].map(lambda v: REGIONEN.get(v, v))
        elif pd.api.types.is_float_dtype(d[k]):
            d[k] = d[k].map(lambda v: de(v, 2) if pd.notna(v) else "–")
        elif pd.api.types.is_datetime64_any_dtype(d[k]):
            d[k] = d[k].dt.strftime("%d.%m.%Y")
        elif pd.api.types.is_integer_dtype(d[k]) and k not in {"geschaeftsjahr", "berichtsjahr"}:
            d[k] = d[k].map(lambda v: de(v, 0))
    return d.rename(columns={k: spaltentitel(k) for k in d})


def tabelle_anzeigen(daten, **kwargs):
    anzeige = anzeigedaten(daten)
    if "Status" in anzeige:
        anzeige = anzeige.style.map(
            lambda v: "color: #c54b4b; font-weight: bold" if v == "Negativer DB II" else "", subset=["Status"]
        )
    return st.dataframe(anzeige, **kwargs)


def abschnitt(titel):
    st.html(f'<div class="va"><h3 style="font-size:1.1rem;margin:1.2rem 0 .6rem">{ui.e(titel)}</h3></div>')


def kennzahl(bereich, titel, wert):
    with bereich:
        st.html(ui.karte(ui.statistik([(str(wert), titel, "neutral")])))


def sicherer_text(text):
    sicher = ui.e(str(text))
    sicher = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", sicher)
    st.html('<div class="va" style="white-space:pre-wrap">' + sicher + "</div>")
