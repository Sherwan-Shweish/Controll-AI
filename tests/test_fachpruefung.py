"""Fachliche Absicherungen aus der Controlling-Prüfung (Version 2.3.1).

* Kostenstellenkosten sind keine reinen Fixkosten: Der beschäftigungsvariable Teil folgt in der Simulation der Menge.
* Vorjahresvergleiche laufen immer über den gleichen Zeitraum.
* Der Demo-Modus weist hinterlegte Musterantworten nicht als Leistung eines Sprachmodells aus.
"""

from __future__ import annotations

import pytest

from src.analytics import kennzahlen_bericht, lade_tabelle
from src.kostenstufen import BESCHAEFTIGUNGSVARIABEL, FERTIGUNG, GEMEIN, QUALITAET
from src.simulation import Annahmen, simuliere, skaliere
from src.strategie import cent, ergebnisrechnung


@pytest.fixture(scope="module")
def ergebnis(demo_daten):
    return ergebnisrechnung(demo_daten.db_path)


def test_variabler_teil_der_kostenstellen_stimmt_mit_den_kostenarten(ergebnis, demo_daten):
    kosten = lade_tabelle(demo_daten.db_path, "plan_ist_finanzen")
    variabel = kosten[kosten.kostenart.astype(str).isin(BESCHAEFTIGUNGSVARIABEL)]
    for spalte, stellen in [("produktvar_cent", FERTIGUNG + QUALITAET), ("gemeinvar_cent", GEMEIN)]:
        soll = variabel[variabel.kostenstelle.astype(str).isin(stellen)]
        for (jahr, quartal), teil in soll.groupby(["geschaeftsjahr", "quartal"]):
            ist = ergebnis[(ergebnis.geschaeftsjahr == jahr) & (ergebnis.quartal == quartal)][spalte].sum()
            assert int(ist) == sum(cent(v) for v in teil.ist_eur)
    assert (ergebnis.produktvar_cent >= 0).all() and (ergebnis.produktvar_cent <= ergebnis.produktfix_cent).all()
    assert (ergebnis.gemeinvar_cent >= 0).all() and (ergebnis.gemeinvar_cent <= ergebnis.gemein_cent).all()
    # Der überwiegende Teil der Fertigungskosten ist beschäftigungsvariabel – wie in der Plankostenrechnung.
    anteil = ergebnis.produktvar_cent.sum() / ergebnis.produktfix_cent.sum()
    assert 0.6 < anteil < 0.9


def test_mengenaenderung_bewegt_auch_die_variablen_kostenstellenkosten(ergebnis):
    jahr = ergebnis[ergebnis.geschaeftsjahr == 2025]
    u, v = int(jahr.umsatz_cent.sum()), int(jahr.variabel_cent.sum())
    pv, gv = int(jahr.produktvar_cent.sum()), int(jahr.gemeinvar_cent.sum())
    r = simuliere(jahr, Annahmen(menge_pct=10))
    material = skaliere(v, -30)
    erwartet = (
        (skaliere(u, 10) - u)
        - (skaliere(material, 10) + skaliere(v - material, 10) - v)
        - (skaliere(pv, 10) - pv)
        - (skaliere(gv, 10) - gv)
    )
    assert r["wirkung_cent"] == erwartet
    assert r["kst_variabel_cent"] == skaliere(pv, 10) + skaliere(gv, 10)
    assert r["kst_fix_cent"] == r["kst_fix_basis_cent"]  # Fixkosten bleiben bei reiner Mengenänderung stehen
    # Ohne die Trennung (alle Kostenstellenkosten fix) wäre die Wirkung deutlich größer.
    ohne_trennung = simuliere(jahr.drop(columns=["produktvar_cent", "gemeinvar_cent"]), Annahmen(menge_pct=10))
    assert ohne_trennung["wirkung_cent"] > 2 * r["wirkung_cent"]


def test_fixkostenregler_wirkt_nur_auf_fixe_kostenarten(ergebnis):
    jahr = ergebnis[ergebnis.geschaeftsjahr == 2025]
    r = simuliere(jahr, Annahmen(fix_pct=10))
    fix = r["kst_fix_basis_cent"]
    kst = int(jahr.produktfix_cent.sum() + jahr.gemein_cent.sum())
    assert fix == kst - int(jahr.produktvar_cent.sum() + jahr.gemeinvar_cent.sum())
    assert abs(r["wirkung_cent"] + fix // 10) <= 2  # zwei Töpfe, je auf den Cent gerundet
    assert r["kst_variabel_cent"] == r["kst_variabel_basis_cent"]


def test_vorjahresvergleich_im_gleichen_zeitraum(demo_daten):
    """2026 liegt bis Q3 vor: verglichen wird mit Q1–Q3 2025, nicht mit dem ganzen Vorjahr."""
    f = kennzahlen_bericht(demo_daten.db_path, 2026)
    tx = lade_tabelle(demo_daten.db_path, "umsatz_transaktionen")
    tx = tx[tx.ist_ausreisser == 0]
    vj = tx[(tx.geschaeftsjahr == 2025) & tx.quartal.isin(["Q1", "Q2", "Q3"])].umsatz_eur.sum()
    akt = tx[tx.geschaeftsjahr == 2026].umsatz_eur.sum()
    assert f["vorjahresvergleich_zeitraum"] == "Q1–Q3"
    assert f["umsatz_vorjahr_eur"] == pytest.approx(vj, abs=1)
    assert f["umsatz_yoy_pct"] == pytest.approx((akt - vj) / vj * 100, abs=0.05)
    assert f["umsatz_yoy_pct"] > 0  # Wachstum, kein scheinbarer Einbruch durch den Vergleich von 9 mit 12 Monaten
    voll = kennzahlen_bericht(demo_daten.db_path, 2025)
    assert voll["vorjahresvergleich_zeitraum"] == "Q1–Q4"



def test_demo_prozessbericht_passt_zu_order_to_cash(demo_daten):
    """Die Musterempfehlungen für Order-to-Cash dürfen keine Einkaufslogik (Purchase-to-Pay) enthalten."""
    from src.analytics import analysiere_prozess, lade_event_log
    from src.demo import _prozessbericht

    fakten = analysiere_prozess(lade_event_log(demo_daten.eventlog_path), prozessname="Order-to-Cash").to_facts()
    bericht = _prozessbericht(fakten)
    text = " ".join(
        bericht["kernaussagen"]
        + [f"{e['massnahme']} {e['begruendung']} {e['verantwortlich']}" for e in bericht["handlungsempfehlungen"]]
    )
    for fremd in ("Drei-Wege", "Wareneingang", "Kreditoren", "Purchase-to-Pay", "Einkauf", "Bestellung"):
        assert fremd not in text
    assert "Zahlungsziel" in text and "kein Kapazitätsengpass" in text
    assert "Forderungsmanagement" in text
    # Ein Einkaufsprozess behält die Empfehlungen zur Rechnungsfreigabe.
    p2p = _prozessbericht({**fakten, "prozess": "Purchase-to-Pay", "engpaesse": [
        {**fakten["engpaesse"][0], "uebergang": "Rechnung prüfen → Rechnung freigeben"}]})
    assert "Wertgrenzen" in p2p["handlungsempfehlungen"][0]["massnahme"]
