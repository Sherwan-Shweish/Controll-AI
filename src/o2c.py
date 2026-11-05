"""Gemeinsame Faktura-, Zahlungs- und Ereignisbasis für Order-to-Cash."""

import hashlib
from pathlib import Path

import pandas as pd

from src.analytics import lade_tabelle
from src.strategie import cent

STICHTAG = pd.Timestamp("2026-09-30")


def belege(db):
    d = lade_tabelle(db, "umsatz_transaktionen")
    d = d[d.ist_ausreisser == 0].copy()
    d["fakturadatum"] = pd.to_datetime(d.buchungsdatum)
    d["betrag_cent"] = d.umsatz_eur.map(cent)
    d["zahlungstag"] = d.fakturadatum + pd.to_timedelta(30 + d.kunden_nr.str[-1].astype(int) * 10, unit="D")
    d["faelligkeit"] = d.fakturadatum + pd.Timedelta(days=30)
    d["variante"] = d.faktura_nr.map(lambda v: int(hashlib.sha256(("42:" + v).encode()).hexdigest()[:8], 16) % 10)
    return d


def erzeuge_log(db):
    zeilen = []
    for r in belege(db).itertuples():
        korrektur = r.variante in {0, 5}
        teil = r.variante in {1, 2}
        spaet = r.variante in {3, 4}
        lieferung = r.fakturadatum - pd.Timedelta(days=1)
        soll = lieferung - pd.Timedelta(days=3) if spaet else lieferung
        events = [("Auftrag anlegen", r.fakturadatum - pd.Timedelta(days=14), 0)]
        if korrektur:
            events += [
                ("Auftrag prüfen", r.fakturadatum - pd.Timedelta(days=12), 0),
                ("Auftrag prüfen", r.fakturadatum - pd.Timedelta(days=10), 0),
            ]
        if teil:
            events.append(("Teillieferung", lieferung - pd.Timedelta(days=4), 0))
        events += [
            ("Lieferung abschließen", lieferung, 0),
            ("Gutschrift" if r.betrag_cent < 0 else "Faktura buchen", r.fakturadatum, r.betrag_cent),
        ]
        if r.zahlungstag > r.faelligkeit and r.betrag_cent > 0:
            events.append(("Mahnung", r.faelligkeit + pd.Timedelta(days=1), 0))
        events.append(
            ("Gutschrift verrechnen" if r.betrag_cent < 0 else "Zahlungseingang", r.zahlungstag, -r.betrag_cent)
        )
        for aktivitaet, datum, bewegung in events:
            if datum > STICHTAG:
                continue
            zeilen.append(
                {
                    "case_id": r.faktura_nr,
                    "aktivitaet": aktivitaet,
                    "zeitstempel": datum,
                    "kunden_nr": r.kunden_nr,
                    "betrag_cent": r.betrag_cent,
                    "op_bewegung_cent": bewegung,
                    "liefertermin": soll,
                    "lieferung": lieferung,
                    "ressource": "O2C-Team",
                    "abteilung": "Forderungsmanagement" if aktivitaet == "Mahnung" else "Debitoren",
                    "bestellwert_eur": r.umsatz_eur,
                }
            )
    return pd.DataFrame(zeilen).sort_values(["case_id", "zeitstempel"], kind="stable")


def log_aus_db(db):
    return pd.read_csv(Path(db).parent / "sample/event_log_o2c.csv", sep=";")


def offene_posten(log, stichtag):
    d = log[pd.to_datetime(log.zeitstempel) <= pd.Timestamp(stichtag)].copy()
    d["op_bewegung_cent"] = pd.to_numeric(d.op_bewegung_cent).astype("int64")
    return d.groupby(["case_id", "kunden_nr"], as_index=False).op_bewegung_cent.sum()


def treiber(log, stichtag):
    d = log[pd.to_datetime(log.zeitstempel) <= pd.Timestamp(stichtag)].copy()
    op = offene_posten(d, stichtag)
    varianten = d.groupby("case_id").aktivitaet.agg(" → ".join).rename("variante")
    op = op.merge(varianten, on="case_id")
    datum = pd.to_datetime(d.zeitstempel)
    fakt = d[
        d.aktivitaet.isin(["Faktura buchen", "Gutschrift"]) & (datum > pd.Timestamp(stichtag) - pd.Timedelta(days=90))
    ]
    umsatz = pd.to_numeric(fakt.op_bewegung_cent).sum()
    return (
        op.groupby(["kunden_nr", "variante"], as_index=False)
        .op_bewegung_cent.sum()
        .assign(
            gebunden_eur=lambda x: x.op_bewegung_cent / 100,
            dso_beitrag_tage=lambda x: x.op_bewegung_cent / umsatz * 90 if umsatz else float("nan"),
        )
        .sort_values("op_bewegung_cent", ascending=False)
    )


def liefertreue(log, jahr, quartal):
    d = log.copy()
    d["zeitstempel"] = pd.to_datetime(d.zeitstempel)
    d = d[
        (d.aktivitaet == "Lieferung abschließen")
        & (d.zeitstempel.dt.year == jahr)
        & (d.zeitstempel.dt.quarter <= quartal)
    ]
    return (pd.to_datetime(d.lieferung) <= pd.to_datetime(d.liefertermin)).mean() * 100
