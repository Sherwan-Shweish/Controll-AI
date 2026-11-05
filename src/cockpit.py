"""Deterministische Kennzahlen und Kernaussagen für das strategische Cockpit."""

from __future__ import annotations

import pandas as pd

from src import ui_design as ui
from src.analytics import deckungsbeitragsrechnung, lade_tabelle
from src.demo import de, vz
from src.kostenstufen import gemeinkosten


def quartalskennzahlen(db: str) -> pd.DataFrame:
    tx = lade_tabelle(db, "umsatz_transaktionen")
    tx = tx[tx.ist_ausreisser == 0]
    dbs = deckungsbeitragsrechnung(tx, lade_tabelle(db, "produktfixkosten"), gruppen=["geschaeftsjahr", "quartal"])
    kosten = gemeinkosten(lade_tabelle(db, "plan_ist_finanzen"))
    out = dbs.merge(kosten, on=["geschaeftsjahr", "quartal"], validate="one_to_one")
    # EBIT = DB II − Unternehmensfixkosten (Instandhaltung) = Umsatz − HK − alle Kostenstellenkosten.
    out["ebit_eur"] = (out.db_ii_eur - out.ist_eur).round(2)
    out["variable_kostenquote_pct"] = out.variable_kosten_eur / out.umsatz_eur * 100
    return out


def jahreswerte(daten: pd.DataFrame, jahr: int) -> dict[str, float]:
    d = daten[daten.geschaeftsjahr == jahr]
    if d.empty:
        return {}
    umsatz = float(d.umsatz_eur.sum())
    return {
        "umsatz_eur": umsatz,
        "db_ii_marge_pct": float(d.db_ii_eur.sum()) / umsatz * 100,
        "ebit_eur": float(d.ebit_eur.sum()),
        "db_i_marge_pct": float(d.db_i_eur.sum()) / umsatz * 100,
        "variable_kostenquote_pct": float(d.variable_kosten_eur.sum()) / umsatz * 100,
    }


def kpis(daten: pd.DataFrame, jahr: int) -> list[ui.Kpi]:
    daten = daten[daten.quartal <= ("Q3" if jahr == 2026 else "Q4")]
    ist, vorjahr = jahreswerte(daten, jahr), jahreswerte(daten, jahr - 1)
    ergebnis = []
    for feld, name, quote, kosten in [
        ("umsatz_eur", "Umsatz · Mio. €", False, False),
        ("db_ii_marge_pct", "DB-II-Marge", True, False),
        ("ebit_eur", "EBIT · Mio. €", False, False),
        ("db_i_marge_pct", "DB-I-Marge", True, False),
        ("variable_kostenquote_pct", "Variable Kostenquote", True, True),
    ]:
        wert, basis = ist[feld], vorjahr.get(feld)
        delta = None if basis is None else wert - basis
        if quote:
            zahl = de(wert, 1) + " %"
            vergleich = de(basis, 1) + " %" if basis is not None else "nicht vorhanden"
            aenderung = vz(delta, 1) + " Pp" if delta is not None else "Kein PY"
        else:
            zahl = de(wert / 1e6, 2)
            vergleich = de(basis / 1e6, 2) + " Mio. €" if basis is not None else "nicht vorhanden"
            aenderung = vz(delta / abs(basis) * 100, 1) + " %" if basis else "Kein PY"
        ton = "neutral" if delta is None or delta == 0 else ui.ton_fuer((delta > 0) != kosten)
        ergebnis.append(
            ui.Kpi(
                name,
                zahl,
                aenderung,
                ton,
                f"PY {vergleich}",
                daten.loc[daten.geschaeftsjahr == jahr, feld].tolist(),
                daten.loc[daten.geschaeftsjahr == jahr - 1, feld].tolist(),
                feld == "ebit_eur",
            )
        )
    return ergebnis


def kernaussagen(db: str, jahr: int) -> list[str]:
    tx = lade_tabelle(db, "umsatz_transaktionen")
    tx = tx[(tx.geschaeftsjahr == jahr) & (tx.ist_ausreisser == 0)]
    d = deckungsbeitragsrechnung(tx, lade_tabelle(db, "produktfixkosten"), gruppen=["produktkategorie"])
    oben = d.sort_values("db_ii_eur", ascending=False).iloc[0]
    unten = d.sort_values("db_ii_marge_pct").iloc[0]
    return [
        f"{oben.produktkategorie} trägt mit {de(oben.db_ii_eur / 1e6, 2)} Mio. € den größten DB II.",
        (f"{unten.produktkategorie} hat mit {de(unten.db_ii_marge_pct, 1)} % die niedrigste DB-II-Marge."),
        "Plan-Ist und monatliche Abweichungszerlegung: weiter mit VarianceAI.",
    ]
