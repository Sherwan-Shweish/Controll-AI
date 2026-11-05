"""Fachliche Invarianten, Freigabegrenzen und Exportverträge für Schritt B."""

from __future__ import annotations

import io
import itertools
import zipfile
from dataclasses import replace

import pandas as pd
import pytest
from openpyxl import load_workbook
from pptx import Presentation

from src.analytics import deckungsbeitragsrechnung, lade_event_log, lade_tabelle
from src.bericht_export import berichtseiten, erstelle_pdf, erstelle_pptx, excel_gegenpruefung, powerbi_strategie
from src.kommentare import Fakt, entwurf, freigeben, freigegebene, pruefe
from src.simulation import Annahmen, simuliere
from src.strategie import (
    abc_analyse,
    cent,
    debitoren_snapshots,
    dso_zeitreihe,
    ergebnisrechnung,
    prozess_kapital,
    scorecard,
    scorecard_stand,
    verdichte,
    verteile,
)


@pytest.fixture(scope="module")
def strategie(demo_daten):
    d = ergebnisrechnung(demo_daten.db_path)
    return d[d.geschaeftsjahr == 2025].copy()


@pytest.mark.parametrize("betrag,gewichte", [(1, [1, 1, 1]), (-10001, [4, 1, 7]), (0, [1]), (99999991, [1, 12] * 20)])
def test_allokation_centgenau(betrag, gewichte):
    r = verteile(betrag, gewichte)
    assert sum(r) == betrag
    assert r == verteile(betrag, gewichte)
    assert max(abs(v - betrag * w / sum(gewichte)) for v, w in zip(r, gewichte, strict=True)) < 1


@pytest.mark.parametrize("gewichte", [[], [0, 0], [-1, 5]])
def test_unzulaessige_allokation(gewichte):
    with pytest.raises(ValueError):
        verteile(100, gewichte)


@pytest.mark.parametrize("dimension", ["kunden_nr", "region", "produktgruppe", "quartal"])
def test_drilldown_additiv(strategie, dimension):
    t = verdichte(strategie, [dimension])
    for feld in [
        "umsatz_cent",
        "variabel_cent",
        "produktfix_cent",
        "gemein_cent",
        "db_i_cent",
        "db_ii_cent",
        "db_iii_cent",
    ]:
        assert int(t[feld].sum()) == int(strategie[feld].sum())
    for obj in strategie[dimension].unique():
        teil = strategie[strategie[dimension] == obj]
        assert int(verdichte(teil, []).db_iii_cent.iloc[0]) == int(t.loc[t[dimension] == obj, "db_iii_cent"].iloc[0])


def test_bisherige_gesamtrechnung_unveraendert(strategie, demo_daten):
    tx = lade_tabelle(demo_daten.db_path, "umsatz_transaktionen")
    tx = tx[(tx.geschaeftsjahr == 2025) & (tx.ist_ausreisser == 0)]
    alt = deckungsbeitragsrechnung(tx, lade_tabelle(demo_daten.db_path, "produktfixkosten"), gruppen=[]).iloc[0]
    kosten = lade_tabelle(demo_daten.db_path, "plan_ist_finanzen")
    kosten = kosten[kosten.geschaeftsjahr == 2025]
    assert int(strategie.db_i_cent.sum()) == cent(alt.db_i_eur)
    assert int(strategie.db_ii_cent.sum()) == cent(alt.db_ii_eur)
    assert int(strategie.db_iii_cent.sum()) == cent(alt.db_ii_eur) - sum(
        kosten[kosten.kostenstelle == "4400"].ist_eur.map(cent)
    )
    assert int(strategie.db_iii_cent.sum()) == cent(alt.db_i_eur) - sum(kosten.ist_eur.map(cent))


def test_abc_und_negative_kunden(strategie):
    abc, f = abc_analyse(strategie)
    # Serviceintensive Kunden (Endziffer 4, Servicegewicht 12) tragen die niedrigsten DB-II-Margen.
    assert set(abc.nsmallest(3, "db_ii_marge_pct").kunden_nr) == {"K104", "K204", "K304"}
    assert f["schwaechster_kunde"] in {"K104", "K204", "K304"}
    assert f["schwaechste_marge_pct"] < f["portfolio_marge_pct"] / 2
    assert f["top_kunden"] == 3
    assert f["kunden"] == 12
    assert abc.kumuliert_pct.iloc[-1] == pytest.approx(100)
    assert (abc.loc[abc.db_ii_cent < 0, "abc"] == "C").all()
    assert f["db_anteil_pct"] == pytest.approx(abc.head(3).db_ii_cent.sum() / abc.db_ii_cent.sum() * 100)


def test_abc_nichtpositives_portfolio(strategie):
    d = strategie.copy()
    d["db_ii_cent"] = -10
    abc, f = abc_analyse(d)
    assert f["db_anteil_pct"] is None
    assert abc.anteil_pct.eq(0).all()


@pytest.mark.parametrize("werte", list(itertools.product([-50, 0, 50], repeat=4)))
def test_simulationsbruecke_invariante(strategie, werte):
    r = simuliere(strategie, Annahmen(*werte))
    assert sum(s["wert_cent"] for s in r["bruecke"][1:-1]) == r["wirkung_cent"]
    assert r["basis_ebit_cent"] + r["wirkung_cent"] == r["ebit_cent"]
    assert r["db_ii_cent"] - r["gemein_cent"] == r["ebit_cent"]
    assert r == simuliere(strategie, Annahmen(*werte))


@pytest.mark.parametrize("wert", [-51, 51, float("nan"), float("inf")])
def test_simulation_unzulaessige_eingabe(wert):
    with pytest.raises(ValueError):
        Annahmen(preis_pct=wert)


def test_simulation_unveraendert_und_interaktion(strategie):
    null = simuliere(strategie, Annahmen())
    assert null["wirkung_cent"] == 0
    r = simuliere(strategie, Annahmen(10, 10))
    assert r["umsatz_cent"] == pytest.approx(int(strategie.umsatz_cent.sum()) * 1.21, abs=1)
    assert r["bruecke"][2]["wert_cent"] > 0


def test_dso_unabhaengiger_stichtagsabgleich(demo_daten):
    tx = lade_tabelle(demo_daten.db_path, "umsatz_transaktionen")
    tx = tx[tx.ist_ausreisser == 0].copy()
    daten = pd.to_datetime(tx.buchungsdatum)
    stichtag = pd.Timestamp("2025-12-31")
    zahlungen = daten + pd.to_timedelta(30 + tx.kunden_nr.str[-1].astype(int) * 10, unit="D")
    offen = tx[(daten <= stichtag) & (zahlungen > stichtag)].umsatz_eur.sum()
    umsatz = tx[(daten > stichtag - pd.Timedelta(days=90)) & (daten <= stichtag)].umsatz_eur.sum()
    d = dso_zeitreihe(demo_daten.db_path)
    assert d[(d.geschaeftsjahr == 2025) & (d.quartal == "Q4")].iloc[0].dso_tage == pytest.approx(offen / umsatz * 90)
    assert not debitoren_snapshots(demo_daten.db_path).duplicated(["stichtag", "kunden_nr"]).any()


def test_scorecard_fehlende_werte_keine_scheinmessung(demo_daten):
    d = scorecard(demo_daten.db_path, 2025, demo_daten.eventlog_path)
    stand, gesamt = scorecard_stand(d, 2025)
    assert len(stand) == 5 and stand.ist.notna().all()
    assert 0 <= gesamt <= 100
    assert gesamt == pytest.approx(
        stand.assign(erfolg=stand.zielerreichung_pct.clip(0, 100)).groupby("perspektive").erfolg.mean().mean()
    )
    _, alt = scorecard_stand(d, 2024)
    assert 0 <= alt <= 100
    p = d[(d.geschaeftsjahr == 2024) & (d.perspektive == "Interne Prozesse")]
    assert p.ist.notna().all()
    assert not p.ampel.eq("nicht gemessen").any()


def test_wertzeit_exposition_unabhaengig(demo_daten):
    log = lade_event_log(demo_daten.eventlog_path)
    r = prozess_kapital(log)
    assert r["faelle"] == 3244
    assert r["kalkulatorische_kosten_eur"] == pytest.approx(r["werttage_eur"] / 365 * 0.06)
    assert r["durchschnitt_exposition_eur"] * r["beobachtung_tage"] == pytest.approx(r["werttage_eur"])


@pytest.fixture
def kommentar():
    f = {"ebit": Fakt("ebit", "EBIT", -1.25, "€"), "dso": Fakt("dso", "DSO", 52.5, "Tage", 1)}
    ctx = {"jahr": 2025, "datenstand": "eins"}
    return f, ctx, entwurf(f, ["ebit", "dso"], "Ursachen prüfen.", ctx)


def test_freigabe_mit_identitaet_und_datenstand(kommentar):
    f, ctx, k = kommentar
    assert pruefe(k, f, ctx)
    assert not freigegebene([k], f, ctx)
    frei = freigeben(k, "Erika Beispiel", f, ctx)
    assert freigegebene([frei], f, ctx) == [frei]
    assert not freigegebene([frei], f, {**ctx, "datenstand": "zwei"})
    assert not freigegebene([replace(frei, empfehlung="Geändert")], f, ctx)
    assert not freigegebene([frei], {**f, "ebit": replace(f["ebit"], wert=1.25)}, ctx)


@pytest.mark.parametrize(
    "aenderung",
    [
        {"text": "EBIT: 1,25 €."},
        {"text": "DSO: -1,25 €."},
        {"empfehlung": "Gewinn verdoppelt auf 2 €."},
        {"fakten_ids": ("geheim",)},
    ],
)
def test_manipulierte_kommentare_abgelehnt(kommentar, aenderung):
    f, ctx, k = kommentar
    with pytest.raises(ValueError):
        freigeben(replace(k, **aenderung), "Erika Beispiel", f, ctx)


@pytest.mark.parametrize("name", ["", "Test", "123 456"])
def test_freigabe_braucht_namen(kommentar, name):
    f, ctx, k = kommentar
    with pytest.raises(ValueError):
        freigeben(k, name, f, ctx)


def test_excel_formeln_cache_und_status(strategie):
    sz = simuliere(strategie, Annahmen(7, -11, 13, -9))
    blob = excel_gegenpruefung(strategie, sz)
    formeln = load_workbook(io.BytesIO(blob), data_only=False)
    cache = load_workbook(io.BytesIO(blob), data_only=True)
    assert formeln["Simulation"]["C19"].value.startswith("=")
    assert formeln["Simulation"]["B6"].number_format == "0.0%"
    assert cache["Simulation"]["B6"].value == 0.07
    assert cache["Simulation"]["C19"].value == sz["ebit_cent"] / 100
    assert cache["Gegenprüfung"]["C6"].value == "OK"
    assert len(formeln["Gegenprüfung"].conditional_formatting) > 0
    for ws in formeln:
        for row in ws:
            for cell in row:
                if cell.data_type == "f":
                    assert cache[ws.title][cell.coordinate].value is not None


def test_powerbi_sternschema_csv_und_dax(demo_daten):
    bsc = scorecard(demo_daten.db_path, 2025, demo_daten.eventlog_path)
    blob = powerbi_strategie(demo_daten.db_path, bsc)
    with zipfile.ZipFile(io.BytesIO(blob)) as z:

        def lese(name):
            raw = z.read(name + ".csv")
            assert raw.startswith(b"\xef\xbb\xbf")
            return pd.read_csv(io.BytesIO(raw), sep=";", decimal=",")

        fakt = lese("fakt_ergebnis")
        for dim, key in [
            ("kunde", "kunden_nr"),
            ("region", "region"),
            ("produktgruppe", "produktgruppe"),
            ("periode", "periode_key"),
        ]:
            d = lese("dim_" + dim)
            assert d[key].is_unique
            assert set(fakt[key]) <= set(d[key])
        assert lese("fakt_debitoren").stichtag.str.fullmatch(r"\d{2}\.\d{2}\.\d{4}").all()
        assert "HASONEVALUE" in z.read("Kennzahlen.dax").decode()


def test_berichte_nur_aktuelle_freigaben(strategie, demo_daten, kommentar):
    from src.analytics import analysiere_prozess

    f, ctx, k = kommentar
    frei = freigeben(k, "Erika Beispiel", f, ctx)
    d = scorecard(demo_daten.db_path, 2025, demo_daten.eventlog_path)
    stand, _ = scorecard_stand(d, 2025)
    pf = analysiere_prozess(lade_event_log(demo_daten.eventlog_path)).to_facts()
    seiten = berichtseiten(strategie, 2025, simuliere(strategie, Annahmen()), stand, pf, [k, frei], f, ctx)
    assert len([s for s in seiten if s["titel"].startswith("Freigegebener Management-Kommentar")]) == 1
    pptx = erstelle_pptx(seiten)
    prs = Presentation(io.BytesIO(pptx))
    assert len(prs.slides) == len(seiten)
    assert b"%PDF" == erstelle_pdf(seiten)[:4]
    veraltet = berichtseiten(strategie, 2025, simuliere(strategie, Annahmen()), stand, pf, [frei], f, {"jahr": 2024})
    assert "keine freigegebenen" in veraltet[-1]["zeilen"][0]
