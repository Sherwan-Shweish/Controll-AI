"""Kostenabgleich der Suite: DB I, Kostenstellen und EBIT centgenau wie in VarianceAI 1.2 (Seed 42)."""

from __future__ import annotations

import pandas as pd
import pytest

from src.analytics import lade_tabelle, plan_ist_abweichung
from src.cockpit import quartalskennzahlen
from src.kostenstufen import FERTIGUNG, GEMEIN, QUALITAET, STUFE_JE_KOSTENSTELLE, produktfixkosten
from src.strategie import ZIEL_DB_II_MARGE_PCT, cent, ergebnisrechnung
from src.suite_abgleich import plan_2026, referenz

# Feste Werte aus VarianceAI 1.2 (Ist, ohne Demonstrationsdublette), unabhängig von der JSON-Datei.
VARIANCEAI = {
    2024: {"umsatz": 7935084479, "hk": 3539594118, "kst": 3600815031, "ebit": 794675330},
    2025: {"umsatz": 8387306996, "hk": 3741107445, "kst": 3774155395, "ebit": 872044156},
    2026: {"umsatz": 6456211460, "hk": 2848534000, "kst": 3044751500, "ebit": 562925960},
}
# Umsatz und HK 2025 je Kunde wie im Universal Journal von VarianceAI (Cent).
KUNDEN_2025 = {
    "K101": (948671497, 423031039), "K102": (758523105, 338265689), "K103": (591834078, 263895241),
    "K104": (407620258, 181802991), "K201": (1135588287, 506864840), "K202": (910892062, 406338497),
    "K203": (715739775, 319234547), "K204": (486055269, 216673102), "K301": (852785335, 380434192),
    "K302": (679278858, 302944864), "K303": (534712298, 238673989), "K304": (365606174, 162948454),
}
KST_2025 = {"4100": 1556547339, "4200": 1121263145, "4300": 606288114, "4400": 293257515, "4500": 196799282}


@pytest.fixture(scope="module")
def tabellen(demo_daten):
    db = demo_daten.db_path
    return {
        name: lade_tabelle(db, name)
        for name in ("umsatz_transaktionen", "plan_ist_finanzen", "produktfixkosten", "umsatzplanung")
    }


@pytest.mark.parametrize("jahr", [2024, 2025, 2026])
def test_db_i_kostenstellen_und_ebit_wie_varianceai(demo_daten, tabellen, jahr):
    soll = VARIANCEAI[jahr]
    tx = tabellen["umsatz_transaktionen"]
    tx = tx[(tx.geschaeftsjahr == jahr) & (tx.ist_ausreisser == 0)]
    kosten = tabellen["plan_ist_finanzen"]
    assert int(tx.umsatz_eur.map(cent).sum()) == soll["umsatz"]
    assert int(tx.variable_kosten_eur.map(cent).sum()) == soll["hk"]
    assert int(kosten[kosten.geschaeftsjahr == jahr].ist_eur.map(cent).sum()) == soll["kst"]

    q = quartalskennzahlen(str(demo_daten.db_path))
    assert cent(q[q.geschaeftsjahr == jahr].ebit_eur.sum()) == soll["ebit"]
    s = ergebnisrechnung(demo_daten.db_path)
    assert int(s[s.geschaeftsjahr == jahr].db_iii_cent.sum()) == soll["ebit"]
    assert int(s[s.geschaeftsjahr == jahr].db_i_cent.sum()) == soll["umsatz"] - soll["hk"]


def test_kostenstellen_je_stelle_2025(tabellen):
    k = tabellen["plan_ist_finanzen"]
    ist = k[k.geschaeftsjahr == 2025].assign(c=lambda d: d.ist_eur.map(cent)).groupby("kostenstelle").c.sum()
    assert ist.to_dict() == KST_2025


def test_referenzdatei_passt_zu_festen_werten():
    for jahr, soll in VARIANCEAI.items():
        summe = referenz()["summen"][str(jahr)]
        assert (summe["umsatz_cent"], summe["hk_cent"], summe["kostenstellen_cent"], summe["ebit_cent"]) == (
            soll["umsatz"],
            soll["hk"],
            soll["kst"],
            soll["ebit"],
        )


def test_jede_kostenstelle_hat_genau_eine_stufe(demo_daten):
    stellen = set(lade_tabelle(demo_daten.db_path, "kostenstellen").kostenstelle)
    assert stellen == set(STUFE_JE_KOSTENSTELLE)
    assert not set(FERTIGUNG + QUALITAET) & set(GEMEIN)


def test_produktfixkosten_centgenau_und_reproduzierbar(tabellen):
    tabelle = tabellen["produktfixkosten"]
    neu = produktfixkosten(tabellen["umsatz_transaktionen"], tabellen["plan_ist_finanzen"])
    for feld in ("fertigung", "qualitaet", "fixkosten"):
        assert tabelle[feld + "_eur"].map(cent).tolist() == neu[feld + "_cent"].tolist()
    k = tabellen["plan_ist_finanzen"].assign(c=lambda d: d.ist_eur.map(cent))
    pool = k[k.kostenstelle.isin(FERTIGUNG + QUALITAET)].groupby(["geschaeftsjahr", "quartal"]).c.sum()
    verteilt = neu.groupby(["geschaeftsjahr", "quartal"]).fixkosten_cent.sum()
    pd.testing.assert_series_equal(verteilt, pool, check_names=False)


def test_senx1_erst_ab_markteinfuehrung(tabellen):
    tx = tabellen["umsatz_transaktionen"]
    senx1 = tx[tx.material_nr == "SENX1"]
    assert not senx1.empty
    assert senx1.buchungsdatum.min() >= referenz()["senx1_erster_verkauf"] == "2026-04-04"
    assert (tx.menge != 0).all()


def test_planung_2026_aus_varianceai(tabellen):
    umsatz, kosten = plan_2026()
    plan = tabellen["umsatzplanung"]
    plan = plan[plan.geschaeftsjahr == 2026]
    assert cent(plan.plan_umsatz_eur.sum()) == int(umsatz.plan_umsatz_eur.map(cent).sum()) == 6505891500
    assert cent(plan.plan_variable_kosten_eur.sum()) == int(umsatz.plan_hk_eur.map(cent).sum())
    k = tabellen["plan_ist_finanzen"]
    assert cent(k[k.geschaeftsjahr == 2026].plan_eur.sum()) == int(kosten.plan_eur.map(cent).sum())


def test_ungeplante_kosten_sind_rot(tabellen):
    k = tabellen["plan_ist_finanzen"]
    ungeplant = plan_ist_abweichung(k[(k.plan_eur == 0) & (k.ist_eur > 0)])
    assert len(ungeplant) == 1
    assert ungeplant.iloc[0][["kostenstelle", "kostenart"]].tolist() == ["4400", "481000"]
    assert (ungeplant.ampel == "rot").all()


def test_bsc_ziel_entspricht_geplanter_db_ii_marge():
    umsatz, kosten = plan_2026()
    erzeugnisfix = kosten[~kosten.kostenstelle.isin(GEMEIN)].plan_eur.sum()
    marge = (umsatz.plan_umsatz_eur.sum() - umsatz.plan_hk_eur.sum() - erzeugnisfix) / umsatz.plan_umsatz_eur.sum()
    assert round(marge * 100, 1) == ZIEL_DB_II_MARGE_PCT


def test_umsatz_und_hk_je_kunde_wie_varianceai(tabellen):
    tx = tabellen["umsatz_transaktionen"]
    tx = tx[(tx.geschaeftsjahr == 2025) & (tx.ist_ausreisser == 0)]
    ist = tx.assign(u=tx.umsatz_eur.map(cent), h=tx.variable_kosten_eur.map(cent))
    ist = ist.groupby("kunden_nr")[["u", "h"]].sum()
    assert {k: (int(r.u), int(r.h)) for k, r in ist.iterrows()} == KUNDEN_2025


def test_jede_referenzzelle_hat_belege(tabellen):
    from src.suite_abgleich import ZELLE

    tx = tabellen["umsatz_transaktionen"]
    vorhanden = set(tx[tx.ist_ausreisser == 0].groupby(ZELLE).groups)
    assert {tuple(r[s] for s in ZELLE) for r in referenz()["werte"]} <= vorhanden
