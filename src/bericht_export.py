"""Strategische Exporte mit denselben Fakten, Freigaberegeln und deutschen Zahlen."""

from __future__ import annotations

import io
import json
import textwrap
import zipfile
from pathlib import Path

import pandas as pd
import xlsxwriter

from src.analytics import lade_tabelle
from src.demo import de
from src.kommentare import Fakt, Kommentar, freigegebene
from src.strategie import debitoren_snapshots, ergebnisrechnung, verdichte
from src.ui_anzeigen import GRUPPEN, NAMEN, REGIONEN
from src.zwischenspeicher import dateicache

FARBEN = {"AC": "#3b4148", "SIM": "#a7adb5", "günstig": "#27866b", "ungünstig": "#c55353"}


def _bild(fig) -> bytes:
    import matplotlib.pyplot as plt

    p = io.BytesIO()
    fig.savefig(p, format="png", dpi=180, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    return p.getvalue()


def diagramm_kunden(daten: pd.DataFrame) -> bytes:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    d = verdichte(daten, ["kunden_nr"]).sort_values("db_ii_cent", ascending=False)
    fig, ax = plt.subplots(figsize=(11.5, 4.7))
    werte = d.db_ii_eur / 1000
    ax.barh(
        d.kunden_nr.map(NAMEN),
        werte,
        color=[FARBEN["ungünstig"] if w < 0 else FARBEN["AC"] for w in werte],
        height=0.55,
    )
    ax.invert_yaxis()
    spanne = max(float(werte.max() - min(0, werte.min())), 1)
    for i, w in enumerate(werte):
        ax.text(w + spanne * 0.015, i, de(w, 1), va="center", fontsize=10)
    ax.set_xlim(min(0, float(werte.min())) - spanne * 0.05, max(0, float(werte.max())) + spanne * 0.18)
    ax.axvline(0, color="#aab0b5", lw=0.7)
    ax.set_xlabel("DB II in T€ · AC")
    ax.set_xticks([])
    ax.spines[["top", "right", "left", "bottom"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
    fig.tight_layout()
    return _bild(fig)


def diagramm_simulation(sz: dict) -> bytes:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(11.5, 4.7))
    for i, r in enumerate(sz["bruecke"]):
        von, bis = r["von_cent"] / 100000, r["bis_cent"] / 100000
        ax.bar(i, abs(bis - von), bottom=min(von, bis), width=0.55, color=FARBEN[r["typ"]])
        ax.annotate(
            de(r["wert_cent"] / 100000, 1),
            (i, max(von, bis)),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center",
            fontsize=10,
        )
    ax.set_xticks(range(len(sz["bruecke"])), [r["schritt"] for r in sz["bruecke"]], fontsize=10)
    ax.set_ylabel("EBIT in T€")
    ax.set_yticks([])
    ax.axhline(0, color="#aab0b5", lw=0.7)
    ax.spines[["top", "right", "left", "bottom"]].set_visible(False)
    ax.margins(y=0.18)
    fig.tight_layout()
    return _bild(fig)


@dateicache
def berichtseiten(
    daten: pd.DataFrame,
    jahr: int,
    sz: dict,
    bsc: pd.DataFrame,
    prozess: dict,
    kommentare: list[Kommentar],
    fakten: dict[str, Fakt],
    kontext: dict,
) -> list[dict]:
    """Ein gemeinsames Seitenmodell für PDF und PowerPoint; Freigabe immer erneut prüfen."""
    frei = freigegebene(kommentare, fakten, kontext)
    seiten = [
        {
            "titel": "Strategischer Management-Bericht",
            "untertitel": f"RheinMain Industrietechnik GmbH · Geschäftsjahr {jahr}"
            + (" · Jan–Sep" if jahr == 2026 else " · Ganzjahr"),
            "zeilen": [f.satz() for f in fakten.values()]
            + [
                "Synthetische Demo-Daten · AC = Ist · SIM = Szenario",
                "DSO: Netto-OP am Berichtsstichtag / Nettoumsatz der letzten 90 Tage × 90.",
                f"BSC: Stand {'Q3' if jahr == 2026 else 'Q4'}, gleichgewichtet und je Perspektive begrenzt.",
            ],
        },
        {
            "titel": "Kunden nach Ergebnisbeitrag",
            "untertitel": "DB II · AC · T€ · größter Beitrag oben",
            "bild": diagramm_kunden(daten),
            "zeilen": [
                "Fertigung nach Herstellkosten, Qualitätssicherung nach Demo-Servicegewicht; negative Beiträge rot."
            ],
        },
        {
            "titel": "Szenario und EBIT-Wirkung",
            "untertitel": "AC → Preis → Menge → Materialkosten → Fixkosten → SIM",
            "bild": diagramm_simulation(sz),
            "zeilen": [
                "Annahmen: "
                + " · ".join(
                    f"{k.replace('_pct', '').replace('_', ' ')}: {de(v, 0)} %" for k, v in sz["annahmen"].items()
                ),
                "Materialanteil 70 % als Demo-Annahme; Preis-Mengen-Interaktion im Mengeneffekt.",
            ],
        },
        {
            "titel": "Balanced Scorecard",
            "untertitel": f"Vier Perspektiven · Stand {'Q3' if jahr == 2026 else 'Q4'} · Demo-Ziele",
            "zeilen": [
                f"{r.perspektive}: {r.kennzahl} "
                f"{de(r.ist, 2) if pd.notna(r.ist) else 'nicht gemessen'} {r.einheit}; "
                f"Ziel {de(r.ziel, 1)} {r.einheit}; {r.ampel}."
                for r in bsc.itertuples()
            ]
            + [
                "Wirkungshypothese: Lernen → Prozesse → Kunden → Finanzen.",
                "Die Kette ist kein statistischer Kausalitätsnachweis.",
            ],
        },
        {
            "titel": "Order-to-Cash als Gesamtprozess",
            "untertitel": "Gesamtprozess · Einkaufsrechnung/P2P → FlowAudit-AI",
            "zeilen": [
                f"Fälle: {de(prozess['anzahl_faelle'])}; Varianten: {de(prozess['anzahl_varianten'])}.",
                f"Median der beobachteten Falldauer: {de(prozess['durchlaufzeit_tage']['median'], 2)} Tage.",
                f"Nacharbeitsquote: {de(prozess['nacharbeit']['quote_pct'], 2)} %.",
                "Zeitraum: " + prozess["zeitraum"]["von"] + " bis " + prozess["zeitraum"]["bis"] + ".",
                "Prozesszeitraum unabhängig vom ausgewählten Finanzjahr; offene Fälle sind rechtszensiert.",
                (
                    "Offene Nettoforderungen stammen aus denselben Faktura- und Zahlungsereignissen. Keine "
                    "automatische Zahlungsentscheidung."
                ),
            ],
        },
    ]
    if not frei:
        seiten.append(
            {
                "titel": "Freigegebene Management-Kommentare",
                "untertitel": "Namentliche Freigabe und aktueller Datenstand",
                "zeilen": ["Für diesen Daten- und Szenariostand liegen keine freigegebenen Kommentare vor."],
            }
        )
    for i, k in enumerate(frei, 1):
        seiten.append(
            {
                "titel": f"Freigegebener Management-Kommentar {i}",
                "untertitel": f"Freigabe: {k.freigeber} · {k.zeit[:10]}",
                "zeilen": [*k.text.splitlines(), "Empfehlung: " + k.empfehlung],
            }
        )
    return seiten


@dateicache
def erstelle_pptx(seiten: list[dict]) -> bytes:
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.util import Inches, Pt

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    for i, s in enumerate(seiten, 1):
        slide = prs.slides.add_slide(prs.slide_layouts[6])

        def text(x, y, w, h, inhalt, groesse, farbe="30353C", slide=slide):
            tf = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)).text_frame
            tf.word_wrap = True
            for n, zeile in enumerate(inhalt.split("\n")):
                p = tf.paragraphs[0] if n == 0 else tf.add_paragraph()
                p.text = zeile
                p.font.name, p.font.size = "Arial", Pt(groesse)
                p.font.color.rgb = RGBColor.from_string(farbe)
                p.space_after = Pt(10)

        text(0.55, 0.3, 12.2, 0.6, s["titel"], 27)
        text(0.55, 1, 12.2, 0.5, s["untertitel"], 13, "6C7177")
        if "bild" in s:
            slide.shapes.add_picture(
                io.BytesIO(s["bild"]), Inches(0.65), Inches(1.55), width=Inches(12), height=Inches(4.8)
            )
            text(0.55, 6.4, 12.2, 0.65, "\n".join(s["zeilen"]), 11)
        else:
            text(0.65, 1.7, 12, 5.1, "\n".join(s["zeilen"]), 18)
        text(0.55, 7.12, 12, 0.2, f"ControllAI · synthetische Demo · {i} / {len(seiten)}", 9, "6C7177")
    p = io.BytesIO()
    prs.save(p)
    return p.getvalue()


@dateicache
def erstelle_pdf(seiten: list[dict]) -> bytes:
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    p = io.BytesIO()
    c = canvas.Canvas(p, pagesize=(960, 540))
    c.setTitle("ControllAI Strategischer Management-Bericht")
    for i, s in enumerate(seiten, 1):
        c.setFillColorRGB(0.18, 0.2, 0.23)
        c.setFont("Helvetica-Bold", 23)
        c.drawString(40, 500, s["titel"])
        c.setFont("Helvetica", 11)
        c.drawString(40, 472, s["untertitel"])
        if "bild" in s:
            c.drawImage(ImageReader(io.BytesIO(s["bild"])), 45, 90, 865, 365, preserveAspectRatio=True, anchor="c")
            y, fs, breite = 65, 9, 170
        else:
            y, fs, breite = 425, 15, 104
        c.setFont("Helvetica", fs)
        for zeile in s["zeilen"]:
            for stueck in textwrap.wrap(zeile.replace("→", " > ").replace("−", "-"), breite):
                c.drawString(45, y, stueck)
                y -= fs * 1.45
            y -= 8
        c.setFont("Helvetica", 8)
        c.drawString(40, 20, f"ControllAI · synthetische Demo · {i} / {len(seiten)}")
        c.showPage()
    c.save()
    return p.getvalue()


@dateicache
def excel_gegenpruefung(daten: pd.DataFrame, sz: dict) -> bytes:
    """Formeln und Cache immer vorhanden; Status berechnet separat vom Ergebnis."""
    p = io.BytesIO()
    wb = xlsxwriter.Workbook(p, {"in_memory": True, "strings_to_formulas": False, "strings_to_urls": False})
    kopf = wb.add_format({"bold": True, "font_color": "#FFFFFF", "bg_color": "#3B4148", "text_wrap": True})
    geld = wb.add_format({"num_format": '#,##0.00;[Red](#,##0.00);"–"', "font_name": "Arial"})
    eingabe = wb.add_format({"num_format": '#,##0.00;[Red](#,##0.00);"–"', "font_color": "#285E9B"})
    prozent = wb.add_format({"num_format": "0.0%", "font_color": "#285E9B"})
    gruen = wb.add_format({"bg_color": "#D7EFE4", "font_color": "#176848"})
    rot = wb.add_format({"bg_color": "#FCE0E0", "font_color": "#9C2222"})
    hin = wb.add_worksheet("Hinweise")
    for r, z in enumerate(
        [
            "ControllAI · Formel-Gegenprüfung",
            "Geldwerte in Euro; Formeln und berechnete Cachewerte gespeichert.",
            ("Blaue Zellen: Quelldaten. Python-Ergebnisse separat. Statuszellen beeinflussen keine Finanzwerte."),
            "Formeln beim Öffnen neu berechnen. Status OK bei Differenz unter einem halben Cent.",
            "DB II: Fertigung 4100–4300 nach Herstellkosten, QS 4500 nach Servicegewicht 12/1; "
            "DB III: Instandhaltung 4400.",
            "SIM: 70 % Materialanteil, Reihenfolge Preis, Menge, Material, Fixkosten.",
            (
                "Alle Daten synthetisch. Drill-down und Simulation im Bericht beziehen sich "
                "auf das gewählte Geschäftsjahr."
            ),
        ]
    ):
        hin.write(r, 0, z)
    hin.set_column("A:A", 120)
    ws = wb.add_worksheet("Ergebnisrechnung")
    headers = [
        "Kunde",
        "Umsatz",
        "Variabel",
        "Produktfix",
        "Gemein",
        "DB I Excel",
        "DB II Excel",
        "DB III Excel",
        "DB I Python",
        "DB II Python",
        "DB III Python",
        "Status",
    ]
    ws.write_row(0, 0, headers, kopf)
    d = verdichte(daten, ["kunden_nr"]).sort_values("db_ii_cent", ascending=False)
    caches = []
    for r, row in enumerate(d.itertuples(), 1):
        n = r + 1
        ws.write(r, 0, NAMEN.get(row.kunden_nr, row.kunden_nr))
        for j, f in enumerate(["umsatz_eur", "variabel_eur", "produktfix_eur", "gemein_eur"], 1):
            ws.write_number(r, j, getattr(row, f), eingabe)
        calc = [
            round(row.umsatz_eur - row.variabel_eur, 2),
            round(row.umsatz_eur - row.variabel_eur - row.produktfix_eur, 2),
            round(row.umsatz_eur - row.variabel_eur - row.produktfix_eur - row.gemein_eur, 2),
        ]
        for j, (formel, wert) in enumerate(
            zip([f"=ROUND(B{n}-C{n},2)", f"=ROUND(F{n}-D{n},2)", f"=ROUND(G{n}-E{n},2)"], calc, strict=True), 5
        ):
            ws.write_formula(r, j, formel, geld, wert)
        soll = [row.db_i_eur, row.db_ii_eur, row.db_iii_eur]
        for j, wert in enumerate(soll, 8):
            ws.write_number(r, j, wert, geld)
        status = "OK" if all(abs(a - b) < 0.005 for a, b in zip(calc, soll, strict=True)) else "FEHLER"
        ws.write_formula(
            r,
            11,
            f'=IF(AND(ABS(F{n}-I{n})<0.005,ABS(G{n}-J{n})<0.005,ABS(H{n}-K{n})<0.005),"OK","FEHLER")',
            None,
            status,
        )
        caches.append(status)
    letzte = len(d) + 1
    ws.write(letzte, 0, "Gesamt", kopf)
    for j in range(1, 11):
        col = xlsxwriter.utility.xl_col_to_name(j)
        if j in range(5, 8):
            wert = float(d[["db_i_eur", "db_ii_eur", "db_iii_eur"][j - 5]].sum())
        else:
            wert = float(
                d[
                    [
                        "umsatz_eur",
                        "variabel_eur",
                        "produktfix_eur",
                        "gemein_eur",
                        "",
                        "",
                        "",
                        "db_i_eur",
                        "db_ii_eur",
                        "db_iii_eur",
                    ][j - 1]
                ].sum()
            )
        ws.write_formula(letzte, j, f"=SUM({col}2:{col}{letzte})", geld, wert)
    ws.freeze_panes(1, 1)
    ws.autofilter(0, 0, len(d), 11)
    ws.set_column("A:A", 48)
    ws.set_column("B:K", 18, geld)
    ws.set_column("L:L", 13)
    ws.set_row(0, 35)
    sim = wb.add_worksheet("Simulation")
    sim.write_row(0, 0, ["Kennzahl", "Basis / Eingabe", "Excel", "Python", "Status"], kopf)
    base = {k: int(daten[k].sum()) / 100 for k in ["umsatz_cent", "variabel_cent", "produktfix_cent", "gemein_cent"]}
    inputs = [
        ("Umsatz", base["umsatz_cent"]),
        ("Variable Kosten", base["variabel_cent"]),
        ("Produktfixkosten", base["produktfix_cent"]),
        ("Gemeinkosten", base["gemein_cent"]),
        ("Preis %", sz["annahmen"]["preis_pct"] / 100),
        ("Menge %", sz["annahmen"]["menge_pct"] / 100),
        ("Materialkosten %", sz["annahmen"]["material_pct"] / 100),
        ("Fixkosten %", sz["annahmen"]["fix_pct"] / 100),
        ("Materialanteil", 0.7),
    ]
    for r, (name, wert) in enumerate(inputs, 1):
        sim.write(r, 0, name)
        sim.write_number(r, 1, wert, prozent if r >= 5 else eingabe)
    # Excel rechnet aus Eingangszellen; Python-Zielwerte kommen aus der Engine.
    formeln = [
        ("Umsatz SIM", "=ROUND(ROUND(B2*(1+B6),2)*(1+B7),2)", sz["umsatz_cent"] / 100),
        ("Material SIM", "=ROUND(ROUND(ROUND(B3*B10,2)*(1+B7),2)*(1+B8),2)", sz["material_cent"] / 100),
        ("Sonstige variable Kosten SIM", "=ROUND((B3-ROUND(B3*B10,2))*(1+B7),2)", sz["sonstige_variabel_cent"] / 100),
        ("Produktfix SIM", "=ROUND(B4*(1+B9),2)", sz["produktfix_cent"] / 100),
        ("Gemein SIM", "=ROUND(B5*(1+B9),2)", sz["gemein_cent"] / 100),
        ("DB I SIM", "=ROUND(C12-C13-C14,2)", sz["db_i_cent"] / 100),
        ("DB II SIM", "=ROUND(C17-C15,2)", sz["db_ii_cent"] / 100),
        ("EBIT SIM", "=ROUND(C18-C16,2)", sz["ebit_cent"] / 100),
        ("Brückenwirkung", "=ROUND(SUM(B22:B25),2)", sz["wirkung_cent"] / 100),
    ]
    for r, (name, f, wert) in enumerate(formeln, 11):
        n = r + 1
        sim.write(r, 0, name)
        sim.write_formula(r, 2, f, geld, wert)
        sim.write_number(r, 3, wert, geld)
        sim.write_formula(r, 4, f'=IF(ABS(C{n}-D{n})<0.005,"OK","FEHLER")', None, "OK")
    for r, schritt in enumerate(sz["bruecke"][1:-1], 21):
        sim.write(r, 0, schritt["schritt"])
        sim.write_number(r, 1, schritt["wert_cent"] / 100, eingabe)
    sim.set_column("A:A", 34)
    sim.set_column("B:D", 20, geld)
    sim.set_column("E:E", 13)
    sim.freeze_panes(1, 1)
    pruef = wb.add_worksheet("Gegenprüfung")
    pruef.write_row(0, 0, ["Prüfung", "Fehlerzahl", "Status"], kopf)
    for r, (label, f, cache) in enumerate(
        [
            ("Ergebnisrechnung", f'=COUNTIF(Ergebnisrechnung!L2:L{letzte},"FEHLER")', caches.count("FEHLER")),
            ("Simulation", '=COUNTIF(Simulation!E12:E20,"FEHLER")', 0),
            (
                "Brücke gegen EBIT-Differenz",
                "=IF(ABS(Simulation!C20-(Simulation!C19-(Simulation!B2-Simulation!B3-"
                "Simulation!B4-Simulation!B5)))<0.005,0,1)",
                0,
            ),
        ],
        1,
    ):
        pruef.write(r, 0, label)
        pruef.write_formula(r, 1, f, None, cache)
        pruef.write_formula(r, 2, f'=IF(B{r + 1}=0,"OK","FEHLER")', None, "OK" if cache == 0 else "FEHLER")
    pruef.write(5, 0, "Gesamtstatus", kopf)
    pruef.write_formula(
        5, 2, '=IF(COUNTIF(C2:C4,"FEHLER")=0,"OK","FEHLER")', None, "OK" if "FEHLER" not in caches else "FEHLER"
    )
    pruef.set_column("A:A", 45)
    pruef.set_column("B:C", 18)
    for blatt, bereich in [(ws, f"L2:L{letzte}"), (sim, "E12:E20"), (pruef, "C2:C6")]:
        for status, fmt in [("OK", gruen), ("FEHLER", rot)]:
            blatt.conditional_format(
                bereich, {"type": "cell", "criteria": "equal to", "value": f'"{status}"', "format": fmt}
            )
    wb.close()
    return p.getvalue()


@dateicache
def powerbi_strategie(db: str | Path, bsc: pd.DataFrame, klassifikation: pd.DataFrame | None = None) -> bytes:
    d = ergebnisrechnung(db)
    for g in ["umsatz", "variabel", "produktfix", "gemein", "db_i", "db_ii", "db_iii"]:
        d[g + "_eur"] = d[g + "_cent"] / 100
    d["periode_key"] = d.geschaeftsjahr.astype(str) + "-" + d.quartal
    op = debitoren_snapshots(db)
    op["periode_key"] = op.geschaeftsjahr.astype(str) + "-" + op.quartal
    op["op_netto_eur"], op["umsatz_90t_eur"] = op.op_netto_cent / 100, op.umsatz_90t_cent / 100
    op["stichtag"] = pd.to_datetime(op.stichtag).dt.strftime("%d.%m.%Y")
    bsc = bsc.copy()
    bsc["periode_key"] = bsc.geschaeftsjahr.astype(str) + "-" + bsc.quartal
    dateien = {
        "fakt_ergebnis": d,
        "fakt_debitoren": op,
        "fakt_bsc": bsc,
        "dim_periode": d[["periode_key", "geschaeftsjahr", "quartal"]].drop_duplicates(),
        "dim_kunde": lade_tabelle(db, "kunden"),
        "dim_region": d[["region"]].drop_duplicates(),
        "dim_produktgruppe": d[["produktgruppe"]].drop_duplicates(),
        "dim_kennzahl": bsc[["kennzahl", "perspektive", "einheit", "niedriger_ist_besser"]].drop_duplicates(),
    }
    dateien["dim_region"]["regionsname"] = dateien["dim_region"].region.map(REGIONEN)
    dateien["dim_produktgruppe"]["produktgruppenname"] = dateien["dim_produktgruppe"].produktgruppe.map(GRUPPEN)
    if klassifikation is not None:
        dateien["bsc_klassifikation_separat"] = klassifikation
    anleitung = """ControllAI – strategisches Sternschema
Import: UTF-8 mit BOM, Semikolon, Gebietsschema Deutsch, Dezimalkomma, Datum TT.MM.JJJJ.
Granularität: fakt_ergebnis je Quartal × Kunde × Region × Produktgruppe;
fakt_debitoren je Quartalsstichtag × Kunde; fakt_bsc je Quartal × Kennzahl.
Beziehungen 1:n und nur einfache Filterrichtung:
dim_periode[periode_key] → alle drei Fakten[periode_key].
dim_kunde[kunden_nr] → fakt_ergebnis und fakt_debitoren[kunden_nr].
dim_region[region] → fakt_ergebnis[region].
dim_produktgruppe[produktgruppe] → fakt_ergebnis[produktgruppe].
dim_kennzahl[kennzahl] → fakt_bsc[kennzahl].
Keine Beziehungen zwischen Fakten, keine zusätzliche Region-Kunde-Verknüpfung.
BSC-Klassifikation ist eine getrennte Prüfansicht ohne automatische Beziehung.
DSO nur bei genau einer ausgewählten Periode anzeigen; OP-Snapshots nicht über Zeit summieren.
Finanzwerte ohne Ausreißer. DB III ist hier EBIT nach vollständiger Kostenallokation.
Servicegewichte und Zahlungszeitpunkte sind synthetische Annahmen; nicht für echte Steuerung übernehmen.
"""
    dax = """Umsatz = SUM(fakt_ergebnis[umsatz_eur])
DB I = [Umsatz] - SUM(fakt_ergebnis[variabel_eur])
DB II = [DB I] - SUM(fakt_ergebnis[produktfix_eur])
DB III = [DB II] - SUM(fakt_ergebnis[gemein_eur])
EBIT = [DB III]
DB II Marge = DIVIDE([DB II], [Umsatz])
DSO = IF(HASONEVALUE(dim_periode[periode_key]),
    DIVIDE(SUM(fakt_debitoren[op_netto_eur]), SUM(fakt_debitoren[umsatz_90t_eur])) * 90, BLANK())
BSC Zielerreichung = IF(HASONEVALUE(dim_periode[periode_key]) && COUNT(fakt_bsc[ist]) = 5,
    AVERAGEX(VALUES(fakt_bsc[perspektive]),
        CALCULATE(AVERAGEX(fakt_bsc, MIN(100, MAX(0, fakt_bsc[zielerreichung_pct]))))) / 100, BLANK())
"""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name, t in dateien.items():
            z.writestr(name + ".csv", t.to_csv(sep=";", decimal=",", index=False, na_rep="").encode("utf-8-sig"))
        z.writestr("LIESMICH.txt", anleitung.encode("utf-8"))
        z.writestr("Kennzahlen.dax", dax.encode("utf-8"))
        z.writestr(
            "schema.json",
            json.dumps(
                {k: {"zeilen": len(v), "spalten": list(v.columns)} for k, v in dateien.items()},
                ensure_ascii=False,
                indent=2,
            ),
        )
    return out.getvalue()
