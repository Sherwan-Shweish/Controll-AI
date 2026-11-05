"""Deterministische What-if-Rechnung mit centgenau schließender EBIT-Brücke."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd


@dataclass(frozen=True)
class Annahmen:
    preis_pct: float = 0
    menge_pct: float = 0
    material_pct: float = 0
    fix_pct: float = 0

    def __post_init__(self):
        for wert in asdict(self).values():
            if not Decimal(str(wert)).is_finite() or not -50 <= wert <= 50:
                raise ValueError("Szenarioänderungen müssen zwischen −50 und +50 Prozent liegen.")


def skaliere(cent: int, prozent: float) -> int:
    return int((Decimal(int(cent)) * (1 + Decimal(str(prozent)) / 100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def simuliere(basis: pd.DataFrame, annahmen: Annahmen) -> dict:
    if basis.empty:
        raise ValueError("Leere Simulationsbasis.")
    u, v, p, g = [int(basis[s].sum()) for s in ["umsatz_cent", "variabel_cent", "produktfix_cent", "gemein_cent"]]
    # Materialanteil ist eine explizite Demo-Annahme, keine SAP-Kostenartenzuordnung.
    material = skaliere(v, -30)
    sonst = v - material
    u_preis = skaliere(u, annahmen.preis_pct)
    u_neu = skaliere(u_preis, annahmen.menge_pct)
    m_menge, s_neu = skaliere(material, annahmen.menge_pct), skaliere(sonst, annahmen.menge_pct)
    m_neu = skaliere(m_menge, annahmen.material_pct)
    p_neu, g_neu = skaliere(p, annahmen.fix_pct), skaliere(g, annahmen.fix_pct)
    start = u - v - p - g
    effekte = [
        ("Preis", u_preis - u),
        ("Menge", u_neu - u_preis - (m_menge + s_neu - v)),
        ("Materialkosten", m_menge - m_neu),
        ("Fixkosten", p + g - p_neu - g_neu),
    ]
    schritte = [{"schritt": "AC · Basis", "von_cent": 0, "bis_cent": start, "wert_cent": start, "typ": "AC"}]
    stand = start
    for name, wert in effekte:
        schritte.append(
            {
                "schritt": name,
                "von_cent": stand,
                "bis_cent": stand + wert,
                "wert_cent": wert,
                "typ": "günstig" if wert >= 0 else "ungünstig",
            }
        )
        stand += wert
    ende = u_neu - m_neu - s_neu - p_neu - g_neu
    if stand != ende:
        raise ArithmeticError("EBIT-Brücke schließt nicht.")
    schritte.append({"schritt": "SIM · Szenario", "von_cent": 0, "bis_cent": ende, "wert_cent": ende, "typ": "SIM"})
    return {
        "annahmen": asdict(annahmen),
        "basis_ebit_cent": start,
        "ebit_cent": ende,
        "wirkung_cent": ende - start,
        "umsatz_cent": u_neu,
        "variabel_cent": m_neu + s_neu,
        "material_cent": m_neu,
        "sonstige_variabel_cent": s_neu,
        "produktfix_cent": p_neu,
        "gemein_cent": g_neu,
        "db_i_cent": u_neu - m_neu - s_neu,
        "db_ii_cent": u_neu - m_neu - s_neu - p_neu,
        "bruecke": schritte,
    }
