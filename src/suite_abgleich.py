"""Centgenauer Abgleich mit der Suite-Referenz aus VarianceAI (Seed 42).

Kalibriert werden je Geschäftsjahr, Quartal, Region, Produktgruppe und Kunde:

* Ist-Umsatz (VarianceAI: Erlöskonto 800000),
* variable Standardherstellkosten (VarianceAI: Konto 700000 „HK“).

Außerdem wird die Markteinführung des Smart Sensor X1 (SENX1) auf das Datum in VarianceAI gelegt;
frühere SENX1-Positionen werden den etablierten Sensoren zugeordnet (gleiche Produktgruppe SEN).
Die Referenzdatei erzeugt ``tools/suite_referenz_erzeugen.py``; zur Laufzeit wird VarianceAI nie gelesen.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

import pandas as pd

from src.strategie import cent

SENX1 = "SENX1"
SENSOR_ERSATZ = ("SEN01", "SEN02", "SEN03")


@cache
def referenz() -> dict[str, Any]:
    return json.loads(Path(__file__).with_name("suite_referenz.json").read_text(encoding="utf-8"))


def _skaliere_centgenau(basis: pd.Series, ziel: int) -> pd.Series:
    """Proportional auf ``ziel`` Cent skalieren; Rundungsrest auf die größte Position."""
    summe = int(basis.sum())
    if summe == 0:
        raise ValueError("Leere Basis für die Kalibrierung.")
    neu = (basis * (ziel / summe)).round().astype("int64")
    neu.loc[basis.idxmax()] += ziel - int(neu.sum())
    return neu


def ordne_senx1_zu(daten: pd.DataFrame, listenpreise: dict[str, float]) -> pd.DataFrame:
    """SENX1-Positionen vor der Markteinführung deterministisch auf SEN01–SEN03 umschlüsseln."""
    d = daten.copy()
    start = pd.Timestamp(referenz()["senx1_erster_verkauf"])
    maske = (d.material_nr == SENX1) & (pd.to_datetime(d.buchungsdatum) < start)
    ersatz = d.loc[maske, "faktura_nr"].astype("int64").mod(len(SENSOR_ERSATZ)).map(dict(enumerate(SENSOR_ERSATZ)))
    d.loc[maske, "material_nr"] = ersatz
    preis = ersatz.map(listenpreise)
    betrag = d.loc[maske, "umsatz_eur"]
    d.loc[maske, "menge"] = (betrag.abs() / preis).round().clip(lower=1) * betrag.gt(0).map({True: 1, False: -1})
    return d


ZELLE = ["geschaeftsjahr", "quartal", "region", "produktgruppe", "kunden_nr"]


def ergaenze_kundenzellen(daten: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Referenzzellen ohne Beleg füllen: eine Position eines anderen Kunden derselben Zelle umschlüsseln.

    Spender ist der Kunde mit den meisten positiven, nicht stornierten Positionen in Geschäftsjahr, Quartal, Region
    und Produktgruppe (bei Gleichstand die kleinste Kundennummer); umgeschlüsselt wird seine Position mit der
    kleinsten Fakturanummer. Deterministisch und protokolliert.
    """
    d = daten.copy()
    umschluesselungen = []
    steuerung = d[d.ist_ausreisser == 0]
    vorhanden = set(steuerung.groupby(ZELLE).groups)
    je_gruppe = steuerung[(steuerung.ist_storno == 0) & (steuerung.umsatz_eur > 0)].groupby(ZELLE[:-1]).groups
    for r in referenz()["werte"]:
        schluessel = tuple(r[s] for s in ZELLE)
        if schluessel in vorhanden:
            continue
        kandidaten = d.loc[je_gruppe.get(schluessel[:-1], [])]
        anzahl = kandidaten.groupby("kunden_nr").size()
        anzahl = anzahl[anzahl >= 2]
        if anzahl.empty:
            raise ValueError(f"Keine Spenderposition für Referenzzelle {schluessel}.")
        spender = sorted(anzahl.index, key=lambda k: (-int(anzahl[k]), k))[0]
        zeile = kandidaten[kandidaten.kunden_nr == spender].sort_values("faktura_nr").index[0]
        d.loc[zeile, "kunden_nr"] = r["kunden_nr"]
        umschluesselungen.append(
            {"faktura_nr": str(d.loc[zeile, "faktura_nr"]), "von": spender, "nach": r["kunden_nr"], "zelle": schluessel}
        )
    return d, umschluesselungen


def kalibriere(daten: pd.DataFrame, listenpreise: dict[str, float] | None = None) -> pd.DataFrame:
    """Umsatz und variable Herstellkosten centgenau auf die VarianceAI-Referenz legen (je Zelle inkl. Kunde).

    Zur Prüfung markierte Ausreißer sind nicht Teil der Referenz: ihr Umsatz bleibt unverändert,
    ihre variablen Kosten erhalten den Kostensatz der Referenzzelle.
    """
    d = daten[pd.to_datetime(daten.buchungsdatum) <= pd.Timestamp(referenz()["stichtag"])].copy()
    if listenpreise is not None:
        d = ordne_senx1_zu(d, listenpreise)
    d, _ = ergaenze_kundenzellen(d)
    zellen = d.groupby(ZELLE).groups
    for r in referenz()["werte"]:
        alle = zellen[tuple(r[s] for s in ZELLE)]
        zelle = d.index.isin(alle)
        ind = d.index[zelle & (d.ist_ausreisser == 0)]
        umsatz = _skaliere_centgenau(d.loc[ind, "umsatz_eur"].map(cent), r["umsatz_cent"])
        basis_hk = d.loc[ind, "variable_kosten_eur"].map(cent)
        hk = _skaliere_centgenau(basis_hk, r["hk_cent"])
        d.loc[ind, "umsatz_eur"] = umsatz / 100
        d.loc[ind, "variable_kosten_eur"] = hk / 100
        auffaellig = d.index[zelle & (d.ist_ausreisser == 1)]
        if len(auffaellig):
            faktor = r["hk_cent"] / int(basis_hk.sum())
            d.loc[auffaellig, "variable_kosten_eur"] = (d.loc[auffaellig, "variable_kosten_eur"] * faktor).round(2)
    return d


def kostenstellen_ist() -> pd.DataFrame:
    """Istkosten je Geschäftsjahr, Quartal, Kostenstelle und Kostenart (Euro)."""
    k = pd.DataFrame(referenz()["kostenstellen_ist"])
    return k.assign(ist_eur=k.pop("ist_cent") / 100)


def plan_2026() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Planung 2026 aus VarianceAI: Umsatz/HK je Quartal und Produktgruppe sowie Kostenstellenbudget."""
    p = referenz()["plan_2026"]
    umsatz = pd.DataFrame(p["umsatz"])
    umsatz = umsatz.assign(plan_umsatz_eur=umsatz.pop("umsatz_cent") / 100, plan_hk_eur=umsatz.pop("hk_cent") / 100)
    kosten = pd.DataFrame(p["kosten"])
    return umsatz, kosten.assign(plan_eur=kosten.pop("plan_cent") / 100)
