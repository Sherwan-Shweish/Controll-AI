"""Interaktive Diagramme nach dem VarianceAI-Design: AC/PY, Nullbasis, deutsche Beschriftungen."""

from __future__ import annotations

import altair as alt
import pandas as pd

from src.demo import de
from src.ui_anzeigen import NAMEN
from src.ui_design import FARBEN


def _thema(chart, hoehe: int = 280):
    f = FARBEN
    return (
        chart.properties(
            height=hoehe, background="transparent", padding={"left": 4, "right": 70, "top": 14, "bottom": 4}
        )
        .configure_view(stroke=None)
        .configure_axis(
            labelColor=f["text_leise"],
            titleColor=f["text_leise"],
            gridColor=f["raster"],
            domainColor=f["linie_stark"],
            tickColor=f["linie_stark"],
            labelFont="Inter",
            titleFont="Inter",
            labelFontSize=11,
            titleFontSize=11,
            titleFontWeight=500,
            labelPadding=6,
        )
        .configure_text(font="Inter", fontSize=11)
        .configure_legend(
            labelColor=f["text_2"],
            titleColor=f["text_leise"],
            labelFont="Inter",
            titleFont="Inter",
            orient="top",
            direction="horizontal",
            symbolSize=90,
            labelFontSize=11,
        )
    )


def balken(daten: pd.DataFrame, kategorie: str, wert: str, einheit: str = "€", *, kosten: bool = False, hoehe=280):
    d = daten.copy()
    if einheit == "€":
        d[wert] = d[wert] / 1000
        einheit = "T€"
    d["Anzeige"] = d[wert].map(lambda w: de(w, 1) + " " + einheit)
    d["Farbe"] = d[wert].map(lambda w: FARBEN["schlecht"] if (w < 0 and not kosten) else FARBEN["ac"])
    basis = alt.Chart(d).encode(
        y=alt.Y(f"{kategorie}:N", sort="-x", title=None),
        x=alt.X(f"{wert}:Q", title=einheit, scale=alt.Scale(zero=True), axis=alt.Axis(labels=False)),
        tooltip=[alt.Tooltip(f"{kategorie}:N", title="Objekt"), alt.Tooltip("Anzeige:N", title="Wert")],
    )
    return _thema(
        basis.mark_bar(size=20).encode(color=alt.Color("Farbe:N", scale=None))
        + basis.mark_text(align="left", dx=6, color=FARBEN["text"]).encode(text="Anzeige:N"),
        hoehe,
    )


def verlauf(daten: pd.DataFrame, jahr: int, wert: str = "umsatz_eur"):
    d = daten[daten.geschaeftsjahr.isin([jahr, jahr - 1])].copy()
    d = d[d.quartal <= ("Q3" if jahr == 2026 else "Q4")]
    d["Serie"] = d.geschaeftsjahr.map(lambda j: "AC" if j == jahr else "PY")
    d["T€"] = d[wert] / 1000
    d["Anzeige"] = d["T€"].map(lambda w: de(w, 1) + " T€")
    d["Beschriftung"] = d["T€"].map(lambda w: de(w, 1))
    basis = alt.Chart(d).encode(
        x=alt.X("quartal:N", title=None),
        xOffset="Serie:N",
        y=alt.Y("T€:Q", scale=alt.Scale(zero=True), axis=alt.Axis(labels=False)),
        color=alt.Color(
            "Serie:N", scale=alt.Scale(domain=["AC", "PY"], range=[FARBEN["ac"], FARBEN["py"]]), title=None
        ),
        tooltip=[alt.Tooltip("quartal:N", title="Quartal"), "Serie:N", "Anzeige:N"],
    )
    return _thema(basis.mark_bar() + basis.mark_text(dy=-9).encode(text="Beschriftung:N"))


def verteilung(faelle: pd.DataFrame):
    return _thema(
        alt.Chart(faelle)
        .mark_bar(color=FARBEN["ac"])
        .encode(
            x=alt.X("durchlaufzeit_tage:Q", bin=alt.Bin(maxbins=25), title="Durchlaufzeit in Tagen"),
            y=alt.Y("count():Q", title="Fälle"),
            tooltip=[alt.Tooltip("count():Q", title="Fälle")],
        )
    )


def prozesslandkarte(uebergaenge: pd.DataFrame) -> str:
    """Prozessgraph aus beobachteten Übergängen; Nacharbeit bleibt als Rückkante sichtbar."""
    from src.ui_design import e, svg_bild

    reihenfolge = [
        "Auftrag anlegen",
        "Auftrag prüfen",
        "Teillieferung",
        "Lieferung abschließen",
        "Faktura buchen",
        "Gutschrift",
        "Mahnung",
        "Zahlungseingang",
        "Gutschrift verrechnen",
    ]
    vorhanden = set(uebergaenge["von"]) | set(uebergaenge["nach"])
    namen = [n for n in reihenfolge if n in vorhanden] + sorted(vorhanden - set(reihenfolge))
    position = {name: (190, 38 + i * 72) for i, name in enumerate(namen)}
    hoehe = len(namen) * 72 + 30
    teile = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 {hoehe}">',
        '<defs><marker id="pfeil" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto">'
        f'<path d="M0 0 L6 3 L0 6" fill="{FARBEN["text_leise"]}"/></marker></defs>',
    ]
    for i, row in enumerate(uebergaenge.itertuples()):
        _, start = position[row.von]
        _, ende = position[row.nach]
        farbe = FARBEN["schlecht"] if i == 0 else FARBEN["text_leise"]
        rueck = ende < start
        x = 390 + (i % 4) * 50
        teile.append(
            f'<path d="M350 {start} C{x} {start} {x} {ende} 350 {ende}" fill="none" '
            f'stroke="{farbe}" stroke-width="{3 if i == 0 else 1.4}" marker-end="url(#pfeil)" '
            + ('stroke-dasharray="5 3" ' if rueck else "")
            + "/>"
        )
        teile.append(
            f'<text x="{x + 5}" y="{(start + ende) / 2}" fill="{farbe}" font-family="Arial" '
            f'font-size="11">{e(de(row.anzahl) + "× · " + de(row.median_h, 1) + " h")}</text>'
        )
    for name, (_, y) in position.items():
        teile.append(
            f'<rect x="30" y="{y - 19}" width="320" height="38" rx="7" '
            f'fill="{FARBEN["karte"]}" stroke="{FARBEN["linie_stark"]}"/>'
        )
        teile.append(
            f'<text x="45" y="{y + 5}" font-family="Arial" font-size="13" fill="{FARBEN["text"]}">{e(name)}</text>'
        )
    teile.append("</svg>")
    return svg_bild("".join(teile), 720, hoehe, "O2C-Prozesslandkarte aus beobachteten Übergängen")


def simulationsbruecke(ergebnis: dict):
    """Basis/SIM auf Null, günstige Effekte grün, ungünstige rot wie VarianceAI."""
    d = pd.DataFrame(ergebnis["bruecke"])
    d["von"] = d.von_cent / 100000
    d["bis"] = d.bis_cent / 100000
    d["oben"] = d[["von", "bis"]].max(axis=1)
    d["Anzeige"] = d.wert_cent.map(lambda w: de(w / 100000, 1) + " T€")
    d["Farbe"] = d.typ.map(
        {"AC": FARBEN["ac"], "SIM": FARBEN["py"], "günstig": FARBEN["gut"], "ungünstig": FARBEN["schlecht"]}
    )
    x = alt.X("schritt:N", sort=d.schritt.tolist(), title=None, axis=alt.Axis(labelAngle=0, labelLimit=130))
    chart = alt.Chart(d).encode(x=x, tooltip=["schritt:N", "Anzeige:N"])
    return _thema(
        chart.mark_bar(size=45).encode(
            y=alt.Y("von:Q", title="T€", axis=alt.Axis(labels=False), scale=alt.Scale(zero=True)),
            y2="bis:Q",
            color=alt.Color("Farbe:N", scale=None),
        )
        + chart.mark_text(dy=-12, color=FARBEN["text"]).encode(
            y=alt.Y("oben:Q", title="T€", axis=alt.Axis(labels=False)), text="Anzeige:N"
        ),
        340,
    )


def pareto(daten: pd.DataFrame):
    d = daten.copy()
    d["Kunde"] = d.kunden_nr.map(NAMEN)
    d["Anzeige"] = d.kumuliert_pct.map(lambda w: de(w, 1) + " %")
    return _thema(
        alt.Chart(d)
        .mark_line(point=True, color=FARBEN["akzent"])
        .encode(
            x=alt.X(
                "Kunde:N",
                sort=d.Kunde.tolist(),
                title="Kunden nach DB II absteigend",
                axis=alt.Axis(labelAngle=-40, labelLimit=150),
            ),
            y=alt.Y("kumuliert_pct:Q", title="Kumulierter positiver DB II in %", scale=alt.Scale(domain=[0, 100])),
            tooltip=["Kunde:N", alt.Tooltip("abc:N", title="ABC-Klasse"), "Anzeige:N"],
        ),
        # Streamlit passt die Gesamthöhe an; die Achsbeschriftung braucht rund 130 px davon.
        420,
    )


def strategiekette() -> str:
    from src.ui_design import e, svg_bild

    namen = ["Lernen & Entwicklung", "Interne Prozesse", "Kunden", "Finanzen"]
    teile = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 100">']
    for i, name in enumerate(namen):
        x = 10 + i * 270
        teile.append(
            f'<rect x="{x}" y="15" width="240" height="65" rx="8" fill="{FARBEN["karte"]}" '
            f'stroke="{FARBEN["linie_stark"]}"/>'
        )
        teile.append(
            f'<text x="{x + 120}" y="53" text-anchor="middle" font-family="Arial" '
            f'font-size="17" fill="{FARBEN["text"]}">{e(name)}</text>'
        )
        if i < 3:
            teile.append(
                f'<text x="{x + 246}" y="53" font-family="Arial" font-size="24" fill="{FARBEN["akzent"]}">→</text>'
            )
    teile.append("</svg>")
    return svg_bild("".join(teile), 1080, 100, "Strategische Wirkungshypothese von Lernen zu Finanzen")
