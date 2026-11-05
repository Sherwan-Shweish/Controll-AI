"""Referenzwerte der Suite aus VarianceAI (Seed 42) erzeugen – einmalig, reproduzierbar.

Aufruf (im Projektordner von VarianceAI 1.2, mit dessen Umgebung):

    cd /pfad/zu/VarianceAI
    uv run python /pfad/zu/ControllAI/tools/suite_referenz_erzeugen.py /pfad/zu/ControllAI/src/suite_referenz.json

Ausgabe: Ist-Umsatz und variable Standardherstellkosten je Geschäftsjahr, Quartal, Region, Produktgruppe und Kunde,
Istkosten je Kostenstelle und Kostenart sowie die Planung 2026 (Umsatz, Herstellkosten, Kostenstellen).
Die fachliche Demonstrationsdublette 9099999999 bleibt – wie in der VarianceAI-Datenprüfung – ausgeschlossen.
ControllAI liest zur Laufzeit nur die erzeugte JSON-Datei, nie VarianceAI selbst.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from src.seed_data import erzeuge_daten  # noqa: E402  (Modul aus VarianceAI)

STICHTAG = "2026-09-30"
DUBLETTE = "9099999999"
JAHRE = (2024, 2025, 2026)


def main(ziel: Path) -> None:
    d = erzeuge_daten(seed=42)
    a = d.acdoca[d.acdoca.belnr != DUBLETTE].copy()
    a["typ"] = a.racct.map(d.kostenarttyp())
    a["quartal"] = "Q" + ((a.poper - 1) // 3 + 1).astype(str)
    a["produktgruppe"] = a.matnr.map(dict(zip(d.material.matnr, d.material.prodh, strict=True)))
    ist = a[(a.version == "IST") & a.gjahr.isin(JAHRE) & ((a.gjahr < 2026) | (a.poper <= 9))]
    plan = a[(a.version == "PLAN") & (a.gjahr == 2026) & (a.poper <= 9)]

    schluessel = ["gjahr", "quartal", "regio", "produktgruppe", "kunnr"]
    umsatz = (-ist[ist.typ == "ERLOES"].groupby(schluessel).hsl_cent.sum()).rename("umsatz_cent")
    hk = ist[ist.typ == "HK"].groupby(schluessel).hsl_cent.sum().rename("hk_cent")
    zellen = umsatz.to_frame().join(hk, how="outer").fillna(0).astype("int64").reset_index()
    kosten = (
        ist[ist.typ == "KOSTEN"]
        .groupby(["gjahr", "quartal", "rcntr", "racct"])
        .hsl_cent.sum()
        .astype("int64")
        .reset_index()
    )
    plan_umsatz = (-plan[plan.typ == "ERLOES"].groupby(["quartal", "produktgruppe"]).hsl_cent.sum()).rename(
        "umsatz_cent"
    )
    plan_hk = plan[plan.typ == "HK"].groupby(["quartal", "produktgruppe"]).hsl_cent.sum().rename("hk_cent")
    plan_zellen = plan_umsatz.to_frame().join(plan_hk).astype("int64").reset_index()
    plan_kosten = (
        plan[plan.typ == "KOSTEN"].groupby(["quartal", "rcntr", "racct"]).hsl_cent.sum().astype("int64").reset_index()
    )

    summen = {}
    for jahr in JAHRE:
        z = zellen[zellen.gjahr == jahr]
        k = kosten[kosten.gjahr == jahr]
        u, h, kst = int(z.umsatz_cent.sum()), int(z.hk_cent.sum()), int(k.hsl_cent.sum())
        summen[str(jahr)] = {
            "umsatz_cent": u,
            "hk_cent": h,
            "db_i_cent": u - h,
            "kostenstellen_cent": kst,
            "ebit_cent": u - h - kst,
            "je_kostenstelle_cent": {r: int(v) for r, v in k.groupby("rcntr").hsl_cent.sum().items()},
        }

    ergebnis = {
        "seed": 42,
        "quelle": "VarianceAI 1.2, src/seed_data.erzeuge_daten(seed=42); Ist ohne Demonstrationsdublette 9099999999",
        "stichtag": STICHTAG,
        "werte": [
            {
                "geschaeftsjahr": int(r.gjahr),
                "quartal": r.quartal,
                "region": r.regio,
                "produktgruppe": r.produktgruppe,
                "kunden_nr": r.kunnr,
                "umsatz_cent": int(r.umsatz_cent),
                "hk_cent": int(r.hk_cent),
            }
            for r in zellen.itertuples()
        ],
        "kostenstellen_ist": [
            {
                "geschaeftsjahr": int(r.gjahr),
                "quartal": r.quartal,
                "kostenstelle": r.rcntr,
                "kostenart": r.racct,
                "ist_cent": int(r.hsl_cent),
            }
            for r in kosten.itertuples()
        ],
        "plan_2026": {
            "umsatz": [
                {
                    "quartal": r.quartal,
                    "produktgruppe": r.produktgruppe,
                    "umsatz_cent": int(r.umsatz_cent),
                    "hk_cent": int(r.hk_cent),
                }
                for r in plan_zellen.itertuples()
            ],
            "kosten": [
                {"quartal": r.quartal, "kostenstelle": r.rcntr, "kostenart": r.racct, "plan_cent": int(r.hsl_cent)}
                for r in plan_kosten.itertuples()
            ],
        },
        "summen": summen,
        "senx1_erster_verkauf": str(ist[(ist.matnr == "SENX1") & (ist.typ == "ERLOES")].budat.min())[:10],
    }
    ziel.write_text(json.dumps(ergebnis, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"geschrieben: {ziel} · {len(ergebnis['werte'])} Zellen · {len(ergebnis['kostenstellen_ist'])} Kostenzeilen")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Aufruf: python suite_referenz_erzeugen.py <ziel.json>  (im VarianceAI-Projektordner)")
    main(Path(sys.argv[1]))
