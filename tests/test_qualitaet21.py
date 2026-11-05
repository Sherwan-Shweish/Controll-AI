"""Unabhängige Abnahme der Suite-Kalibrierung und Qualitätskorrektur 2.1."""

import ast
import hashlib
import io
import time
import zipfile
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src.agent import AgentConfig
from src.analytics import bereinige_sap_export, lade_tabelle
from src.cockpit import kpis, quartalskennzahlen
from src.demo import de, erstelle_agent
from src.kommentare import Fakt, entwurf, fingerprint, freigeben
from src.pruefpfad import pruefpfad
from src.sicherheitstest import pruefe_datentext
from src.strategie import cent
from src.ui_anzeigen import anzeigedaten
from src.zwischenspeicher import dateicache

# Einmalig aus VarianceAI 1.2 Seed 42 extrahiert; keine Ableitung aus dem Generator.
REFERENZ = {
    2024: {
        "ANT": 3478589594,
        "SEN": 1971298323,
        "STE": 2485196562,
        "NORD": 2564029010,
        "SUED": 3068698124,
        "WEST": 2302357345,
    },
    2025: {
        "ANT": 3679362656,
        "SEN": 2084448576,
        "STE": 2623495764,
        "NORD": 2706648938,
        "SUED": 3248275393,
        "WEST": 2432382665,
    },
    2026: {
        "ANT": 2663497600,
        "SEN": 1828694960,
        "STE": 1964018900,
        "NORD": 2282733460,
        "SUED": 2346316500,
        "WEST": 1827161500,
    },
}
ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("jahr", [2024, 2025, 2026])
@pytest.mark.parametrize("gruppe", ["ANT", "SEN", "STE", "NORD", "SUED", "WEST"])
def test_suite_istumsatz_gegen_feste_referenz(demo_daten, jahr, gruppe):
    d = lade_tabelle(demo_daten.db_path, "umsatz_transaktionen")
    feld = "region" if gruppe in {"NORD", "SUED", "WEST"} else "produktgruppe"
    d = d[(d.geschaeftsjahr == jahr) & (d[feld] == gruppe) & (d.ist_ausreisser == 0)]
    assert int(d.umsatz_eur.map(cent).sum()) == REFERENZ[jahr][gruppe]


def test_sap_rohexport_und_datenbank_centgleich(demo_daten):
    db = demo_daten.db_path
    roh = pd.read_csv(demo_daten.rohexport_path, sep=";", dtype=str, keep_default_na=False)
    sauber, _ = bereinige_sap_export(roh, lade_tabelle(db, "materialien"), lade_tabelle(db, "kunden"))
    tx = lade_tabelle(db, "umsatz_transaktionen")
    for feld in ["umsatz_eur", "variable_kosten_eur", "deckungsbeitrag_eur"]:
        links = sauber.set_index("faktura_nr")[feld].map(cent).sort_index()
        rechts = tx.set_index("faktura_nr")[feld].map(cent).sort_index()
        links.index = links.index.astype(str)
        rechts.index = rechts.index.astype(str)
        pd.testing.assert_series_equal(links, rechts)


def test_ytd_vergleicht_nur_januar_bis_september(demo_daten):
    d = quartalskennzahlen(str(demo_daten.db_path))
    k = kpis(d, 2026)[0]
    py = d[(d.geschaeftsjahr == 2025) & (d.quartal != "Q4")].umsatz_eur.sum()
    assert len(k.verlauf) == len(k.vergleich) == 3
    assert de(py / 1e6, 2) in k.fuss
    tx = lade_tabelle(demo_daten.db_path, "umsatz_transaktionen")
    assert pd.to_datetime(tx.buchungsdatum).max() <= pd.Timestamp("2026-09-30")
    assert set(tx.geschaeftsjahr) == {2024, 2025, 2026}


def test_suite_bezeichnungen_daten_anzeige_export(demo_daten):
    from src.bericht_export import powerbi_strategie
    from src.strategie import scorecard
    from src.suite_stammdaten import KUNDEN, MATERIALIEN, PRODUKTGRUPPEN

    db = demo_daten.db_path
    tx = lade_tabelle(db, "umsatz_transaktionen")
    assert set(tx.produktkategorie) == {v for _, v in PRODUKTGRUPPEN}
    assert set(lade_tabelle(db, "kunden").kundenname) == {v for _, v, _ in KUNDEN}
    assert set(lade_tabelle(db, "materialien").bezeichnung) == {v[1] for v in MATERIALIEN}
    assert set(lade_tabelle(db, "kostenstellen").kostenstelle) == {"4100", "4200", "4300", "4400", "4500"}
    anzeige = anzeigedaten(tx.head())
    assert not any("_" in k for k in anzeige)
    assert any(name in str(anzeige.Kunde.tolist()) for _, name, _ in KUNDEN)
    paket = powerbi_strategie(db, scorecard(db, 2026, demo_daten.eventlog_path))
    with zipfile.ZipFile(io.BytesIO(paket)) as z:
        kunden = pd.read_csv(z.open("dim_kunde.csv"), sep=";")
        assert set(kunden.kundenname) == {v for _, v, _ in KUNDEN}


def test_datentext_test_ohne_modellaufruf_und_datenaenderung(demo_daten):
    agent, _ = erstelle_agent(AgentConfig(db_path=demo_daten.db_path), demo=True)

    class KeinModell:
        def complete(self, *args):
            pytest.fail("Manipulierter Datentext darf das Modell nicht erreichen.")

    agent._llm = KeinModell()
    vorher = hashlib.sha256(demo_daten.db_path.read_bytes()).hexdigest()
    assert pruefe_datentext(agent)
    assert agent.sql.audit.eintraege[-1].schicht == "Datentext"
    assert hashlib.sha256(demo_daten.db_path.read_bytes()).hexdigest() == vorher


def test_pruefpfad_freigabe_export_und_veraltung():
    f = {"a": Fakt("a", "Umsatz", 2000, "€"), "b": Fakt("b", "Mini", 20, "€"), "c": Fakt("c", "DSO", 40, "Tage")}
    kontext = {"jahr": 2026}
    k = entwurf(f, ["a"], "Prüfen", kontext)
    p = pruefpfad(f, kontext, [], k)
    assert p["stufen"] == [3, 2, 1, 1, 0, 0]
    assert p["gruende"]["Unter Schwelle"] == 1
    assert p["gruende"]["Nicht freigegeben"] == 1
    frei = freigeben(k, "Erika Beispiel", f, kontext)
    p = pruefpfad(f, kontext, [frei], k, {"kontext": fingerprint(kontext), "ids": ["a"]})
    assert p["stufen"] == [3, 2, 1, 1, 1, 1]
    assert sum(p["gruende"].values()) == 2
    neu = pruefpfad(f, {"jahr": 2025}, [frei])
    assert neu["gruende"]["Veraltet"] == 1
    assert neu["stufen"][-1] == 0


def test_cache_trennt_funktionen_dateistand_und_schluessel(tmp_path):
    p = tmp_path / "quelle.txt"
    p.write_text("eins")
    aufrufe = []

    @dateicache
    def erster(pfad, jahr):
        aufrufe.append(1)
        return Path(pfad).read_text() + str(jahr)

    @dateicache
    def zweiter(pfad, jahr):
        return "andere Funktion"

    assert erster(p, 2026) == erster(p, 2026) == "eins2026"
    assert len(aufrufe) == 1
    assert zweiter(p, 2026) == "andere Funktion"
    p.write_text("neuer Stand")
    assert erster(p, 2026) == "neuer Stand2026"
    assert erster(p, 2025) == "neuer Stand2025"
    assert len(aufrufe) == 3


def test_keine_maskierten_markdown_ausgaben_oder_alten_ui_bausteine():
    for p in [ROOT / "app.py", *ROOT.glob("src/ui_*.py")]:
        for n in ast.walk(ast.parse(p.read_text())):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
                assert not (
                    isinstance(n.func.value, ast.Name)
                    and n.func.value.id == "st"
                    and n.func.attr in {"metric", "subheader"}
                )
                if n.func.attr == "markdown":
                    assert not any(
                        isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute) and x.func.attr == "e"
                        for x in ast.walk(n)
                    )


def test_ui_performance_tabfragen_und_deutsche_spalten(monkeypatch, demo_daten, tmp_path):
    monkeypatch.setenv("DB_PATH", str(demo_daten.db_path))
    monkeypatch.setenv("LLM_ANBIETER", "mock")
    monkeypatch.setenv("AGENT_DATENORDNER", str(tmp_path))
    monkeypatch.setenv("AGENT_LAUFZEIT", "web")
    a = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    t = time.perf_counter()
    a.run()
    dauer = time.perf_counter() - t
    assert dauer <= 3
    assert not a.exception
    assert not any("vollständig geladen" in e.value for e in a.error)
    assert a.selectbox(key="geschaeftsjahr").value == 2026
    assert len(a.tabs) == 7
    for tabelle in a.dataframe:
        assert not any("_" in k for k in tabelle.value.columns)
    a.button(key="datentext_test").click().run()
    html = "".join(x.proto.body for x in a.get("html"))
    assert "1 blockiert" in html
    a.button(key="injection_test").click().run()
    assert "2 blockiert" in "".join(x.proto.body for x in a.get("html"))
    a.session_state["haupttabs"] = "Prozesse"
    a.run()
    assert a.session_state["prozess_zaehler"] > 0
    for tab in a.tabs:
        assert sum('class="va va-leitfrage"' in h.proto.body for h in tab.get("html")) == 1
