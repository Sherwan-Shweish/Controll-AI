"""Belegidentität, Stichtagsabgrenzung und centgenaue OP-Abstimmung."""

import pandas as pd
import pytest

from src.analytics import lade_event_log, lade_tabelle
from src.o2c import erzeuge_log, offene_posten, treiber
from src.strategie import debitoren_snapshots, scorecard, scorecard_stand


@pytest.mark.parametrize("stichtag", ["2024-03-31", "2024-12-31", "2025-09-30", "2025-12-31", "2026-09-30"])
def test_op_eventlog_gleich_debitoren_auf_cent(demo_daten, stichtag):
    log = lade_event_log(demo_daten.eventlog_path)
    op = offene_posten(log, stichtag).groupby("kunden_nr").op_bewegung_cent.sum()
    snap = debitoren_snapshots(demo_daten.db_path)
    soll = snap[snap.stichtag == stichtag].set_index("kunden_nr").op_netto_cent
    assert op.to_dict() == soll.to_dict()
    assert treiber(log, stichtag).op_bewegung_cent.sum() == soll.sum()


def test_fakturaereignisse_gleich_belegen_ohne_zukunft(demo_daten):
    log = lade_event_log(demo_daten.eventlog_path)
    tx = lade_tabelle(demo_daten.db_path, "umsatz_transaktionen")
    tx = tx[tx.ist_ausreisser == 0]
    assert set(log.case_id) == set(tx.faktura_nr)
    assert log.zeitstempel.max() <= pd.Timestamp("2026-09-30")
    fakt = log[log.aktivitaet.isin(["Faktura buchen", "Gutschrift"])].set_index("case_id")
    from src.strategie import cent

    assert pd.to_numeric(fakt.op_bewegung_cent).to_dict() == tx.set_index("faktura_nr").umsatz_eur.map(cent).to_dict()
    a = erzeuge_log(demo_daten.db_path)
    b = erzeuge_log(demo_daten.db_path)
    pd.testing.assert_frame_equal(a, b)
    assert {"Teillieferung", "Gutschrift", "Mahnung", "Auftrag prüfen", "Zahlungseingang"} <= set(log.aktivitaet)


def test_o2c_bsc_alle_perspektiven_gemessen(demo_daten):
    d = scorecard(demo_daten.db_path, 2026, demo_daten.eventlog_path)
    stand, wert = scorecard_stand(d, 2026)
    assert stand.ist.notna().all() and len(stand) == 5
    assert {"DSO", "Liefertreue YTD"} == set(stand[stand.perspektive == "Kunden"].kennzahl)
    assert 0 <= wert <= 100
