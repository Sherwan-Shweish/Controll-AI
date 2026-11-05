"""Regressionen für SQL-Grenzen, Suite-Stammdaten, Audit, Kennzahlen und Laufzeiten."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import sqlite3
from pathlib import Path

import pandas as pd
import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

from src import ui_design as ui
from src.agent import FactChecker, ReadOnlySQLExecutor, SQLGuardError
from src.analytics import lade_tabelle
from src.audit import AuditProtokoll
from src.cockpit import jahreswerte, kpis, quartalskennzahlen
from src.laufzeit import anbieter_vorauswahl, fehlender_zugang, laufzeit
from src.suite_stammdaten import KUNDEN, MATERIALIEN

APP = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM geheim",
        "WITH x AS (SELECT * FROM geheim) SELECT * FROM x",
        "SELECT * FROM plan_ist UNION SELECT NULL,NULL,NULL,NULL,wert FROM geheim",
        "SELECT (SELECT wert FROM geheim) FROM plan_ist",
        "SELECT name FROM sqlite_master",
        "SELECT * FROM pragma_table_info('plan_ist')",
        "SELECT * FROM main.plan_ist",
        "SELECT load_extension('x')",
        "SELECT readfile('/etc/passwd')",
        "SELECT randomblob(1000000000)",
        "SELECT * FROM plan_ist; SELECT 1",
        "WITH plan_ist AS (SELECT * FROM geheim) SELECT * FROM plan_ist",
        "SELECT 1 INTO neue_tabelle",
        "SELECT * FROM plan_ist /* verborgen */",
    ],
)
def test_parser_und_tabellen_whitelist(mini_db, sql):
    ex = ReadOnlySQLExecutor(mini_db)
    with pytest.raises(SQLGuardError):
        ex.execute(sql)
    eintrag = ex.audit.eintraege[-1]
    assert eintrag.art == "ABGELEHNT" and eintrag.schicht and eintrag.grund and eintrag.sql == sql


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT intern FROM plan_ist",
        "SELECT * FROM plan_ist",
        "WITH x AS (SELECT intern AS oeffentlich FROM plan_ist) SELECT oeffentlich FROM x",
        "SELECT produktkategorie FROM plan_ist WHERE intern > 0",
        "SELECT produktkategorie FROM plan_ist ORDER BY intern",
        "SELECT COUNT(*) FROM plan_ist GROUP BY intern",
        "SELECT (SELECT intern FROM plan_ist LIMIT 1)",
    ],
)
def test_spalten_whitelist_schuetzt_auch_filter_sortierung_cte(mini_db, sql):
    with sqlite3.connect(mini_db) as conn:
        conn.execute("ALTER TABLE plan_ist ADD COLUMN intern REAL DEFAULT 99")
    ex = ReadOnlySQLExecutor(mini_db)
    assert "intern" not in ex.schema_description()
    with pytest.raises(SQLGuardError, match="Whitelist"):
        ex.execute(sql)
    assert "Spalten" in ex.audit.eintraege[-1].schicht


def test_gesperrte_spalte_in_view(mini_db):
    with sqlite3.connect(mini_db) as conn:
        conn.execute("CREATE VIEW freigegebene_view AS SELECT wert FROM geheim")
    ex = ReadOnlySQLExecutor(mini_db, erlaubte_spalten={"freigegebene_view": {"wert": "INTEGER"}})
    with pytest.raises(SQLGuardError):
        ex.execute("SELECT * FROM freigegebene_view")


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT COUNT(*) FROM plan_ist",
        "WITH q AS (SELECT produktkategorie FROM plan_ist) SELECT * FROM q",
        (
            "SELECT p.produktkategorie, SUM(p.ist_umsatz) AS gesamt FROM plan_ist p GROUP "
            "BY p.produktkategorie ORDER BY gesamt"
        ),
        "SELECT 'DELETE; -- ungefährlich' AS text FROM plan_ist",
    ],
)
def test_legitime_aliasse_ctes_und_aggregate(mini_db, sql):
    ex = ReadOnlySQLExecutor(mini_db)
    assert ex.execute(sql).row_count > 0
    assert ex.audit.eintraege[-1].art == "ZUGELASSEN"


@pytest.mark.parametrize(
    ("text", "rows", "fehler"),
    [
        ("Wert 7 €", [[90]], ["7"]),
        ("Jahr 2028", [[2025]], ["2028"]),
        ("Ergebnis 125 €", [[-125]], ["125"]),
        ("Ergebnis −125 €", [[-125]], []),
        ("Umsatz 1,25 Mio. €", [[1250000]], []),
        ("Umsatz 1,25 €", [[1250000]], ["1,25"]),
        ("Marge 12,5 %", [[12.5]], []),
        ("Marge 12,5 %", [[0.125]], ["12,5"]),
    ],
)
def test_sql_faktenpruefung_ohne_blinde_ausnahmen(text, rows, fehler):
    assert FactChecker.sql_zahlenpruefung(text, rows, 1) == fehler


def test_unbelegte_formulierung_wird_nicht_angezeigt(agent_factory):
    agent = agent_factory(
        {"sql": "SELECT SUM(ist_umsatz) AS umsatz FROM plan_ist", "erklaerung": ""}, "Der Umsatz beträgt 7 €."
    )
    antwort = agent.ask("Umsatz?")
    assert "7 €" not in antwort.antwort
    assert antwort.unverifizierte_zahlen == ["7"]
    assert agent.sql.audit.eintraege[-1].schicht == "Faktenprüfung"


def test_audit_append_only_und_hashkette():
    audit = AuditProtokoll()
    audit.ergaenze("ANALYSE", "Daten", "Start")
    vorher = audit.eintraege
    audit.ergaenze("ABGELEHNT", "Parser", "Schreibzugriff", "DELETE FROM x")
    assert audit.eintraege[:1] == vorher and len(vorher) == 1
    with pytest.raises(dataclasses.FrozenInstanceError):
        audit.eintraege[0].grund = "verändert"
    daten = json.loads(audit.exportiere())
    for i, eintrag in enumerate(daten):
        digest = eintrag.pop("hash")
        assert hashlib.sha256(json.dumps(eintrag, ensure_ascii=False, sort_keys=True).encode()).hexdigest() == digest
        assert eintrag["nummer"] == i + 1
    assert audit.eintraege[1].vorgaenger == audit.eintraege[0].hash


def test_stammschluessel_der_suite(demo_daten):
    db = demo_daten.db_path
    assert set(lade_tabelle(db, "kunden").kunden_nr) == {k[0] for k in KUNDEN}
    assert set(lade_tabelle(db, "materialien").material_nr) == {m[0] for m in MATERIALIEN}
    assert set(lade_tabelle(db, "kostenstellen").kostenstelle) == {"4100", "4200", "4300", "4400", "4500"}
    tx = lade_tabelle(db, "umsatz_transaktionen")
    assert set(tx.buchungskreis) == {"1000"}
    assert set(tx.produktgruppe) == {"ANT", "STE", "SEN"}
    assert set(tx.region) == {"NORD", "SUED", "WEST"}
    assert {"400000", "410000", "470000"} <= set(lade_tabelle(db, "plan_ist_finanzen").kostenart)


def test_kpi_gegen_unabhaengige_sql_summe(demo_daten):
    daten = quartalskennzahlen(str(demo_daten.db_path))
    ist = jahreswerte(daten, 2025)
    with sqlite3.connect(demo_daten.db_path) as conn:
        umsatz, variabel = conn.execute(
            "SELECT SUM(umsatz_eur), SUM(variable_kosten_eur) FROM umsatz_transaktionen "
            "WHERE geschaeftsjahr=2025 AND ist_ausreisser=0"
        ).fetchone()
        fix = conn.execute("SELECT SUM(fixkosten_eur) FROM produktfixkosten WHERE geschaeftsjahr=2025").fetchone()[0]
        gk = conn.execute(
            "SELECT SUM(ist_eur) FROM plan_ist_finanzen WHERE geschaeftsjahr=2025 AND kostenstelle='4400'"
        ).fetchone()[0]
        kst = conn.execute("SELECT SUM(ist_eur) FROM plan_ist_finanzen WHERE geschaeftsjahr=2025").fetchone()[0]
    assert ist["umsatz_eur"] == pytest.approx(umsatz, abs=0.01)
    assert ist["ebit_eur"] == pytest.approx(umsatz - variabel - fix - gk, abs=0.01)
    # Unabhängig von jeder Schlüsselung: EBIT = Umsatz − Herstellkosten − alle Kostenstellenkosten
    assert ist["ebit_eur"] == pytest.approx(umsatz - variabel - kst, abs=0.01)
    assert ist["db_ii_marge_pct"] == pytest.approx((umsatz - variabel - fix) / umsatz * 100)
    assert len(kpis(daten, 2025)) == 5
    assert all(len(k.verlauf) == len(k.vergleich) == 4 for k in kpis(daten, 2025))


def test_quote_gewichtung_und_guenstige_farbe():
    daten = pd.DataFrame(
        [
            dict(
                geschaeftsjahr=j,
                quartal=q,
                umsatz_eur=u,
                db_i_eur=u * 0.4,
                db_ii_eur=u * 0.3,
                ebit_eur=u * 0.1,
                variable_kosten_eur=u * 0.6,
                db_i_marge_pct=40,
                db_ii_marge_pct=30,
                variable_kostenquote_pct=60,
            )
            for j in [2024, 2025]
            for q, u in [("Q1", 100), ("Q2", 900)]
        ]
    )
    assert jahreswerte(daten, 2025)["db_ii_marge_pct"] == 30
    assert all(k.ton == "neutral" for k in kpis(daten, 2025))


@pytest.mark.parametrize(
    ("wert", "erwartet"),
    [("desktop", "desktop"), ("lokal", "lokal"), ("web", "web"), ("unbekannt", "web"), ("", "web")],
)
def test_laufzeitmodi(monkeypatch, wert, erwartet):
    monkeypatch.setenv("AGENT_LAUFZEIT", wert)
    assert laufzeit() == erwartet


@pytest.mark.parametrize("wert", ["web", "unbekannt", "lokal", "desktop"])
def test_umschalter_und_speichern_je_laufzeit(monkeypatch, tmp_path, demo_daten, wert):
    monkeypatch.setenv("AGENT_LAUFZEIT", wert)
    monkeypatch.setenv("AGENT_DATENORDNER", str(tmp_path))
    monkeypatch.setenv("DB_PATH", str(demo_daten.db_path))
    monkeypatch.setenv("LLM_ANBIETER", "mock")
    monkeypatch.setattr("src.laufzeit.lade_geheimnisse", lambda: None)
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception
    schalter = [b for b in at.get("button_group") if getattr(b, "key", None) == "darstellung_wahl"]
    assert bool(schalter) == (wert in {"lokal", "desktop"})
    if schalter:
        schalter[0].set_value("hell").run()
        assert json.loads((tmp_path / "ControllAI/einstellungen.json").read_text())["darstellung"] == "hell"
        at.button_group(key="darstellung_wahl").set_value("dunkel").run()
    else:
        assert not (tmp_path / "ControllAI/einstellungen.json").exists()


@pytest.mark.parametrize(
    ("wert", "erwartet"),
    [("mock", "mock"), ("claude", "claude"), ("anthropic", "claude"), ("gemini", "gemini"), ("kaputt", "mock")],
)
def test_anbieter_vorauswahl(monkeypatch, wert, erwartet):
    monkeypatch.setenv("LLM_ANBIETER", wert)
    assert anbieter_vorauswahl() == erwartet


def test_sdk_fehlt_mit_schluessel(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "testwert-nicht-ausgeben")
    monkeypatch.setattr("src.laufzeit.importlib.util.find_spec", lambda name: None)
    grund = fehlender_zugang("claude")
    assert "SDK" in grund and "uv sync" in grund and "testwert" not in grund


def test_html_maskierung_und_data_uri():
    html = ui.kopfzeile("<script>alert(1)</script>", "<img onerror=x>", "&", '"', [])
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "data:image/svg+xml;base64," in ui.sparkline([1, 2, 3])


def test_symbole_und_version():
    root = Path(APP).parent
    with Image.open(root / "desktop/ressourcen/icon.png") as bild:
        assert bild.size == (1024, 1024)
    with Image.open(root / "static/favicon.png") as bild:
        assert bild.size == (64, 64)
    assert (root / "desktop/ressourcen/AppIcon.icns").read_bytes().startswith(b"icns")


@pytest.mark.parametrize("modus", ["dunkel", "hell"])
def test_diagramme_und_prozesslandkarte(modus, demo_daten):
    from src import ui_diagramme as dia
    from src.analytics import analysiere_prozess, lade_event_log

    ui.setze_modus(modus)
    quartale = quartalskennzahlen(str(demo_daten.db_path))
    diagramm = dia.verlauf(quartale, 2025).to_dict()
    # Streamlit erwartet ein Padding-Objekt (numerischer Wert führt erst im Browser zum Fehler).
    assert isinstance(diagramm["padding"], dict)
    assert diagramm["layer"][0]["encoding"]["y"]["scale"]["zero"]
    pa = analysiere_prozess(lade_event_log(demo_daten.eventlog_path))
    assert "data:image/svg+xml;base64," in dia.prozesslandkarte(pa.uebergaenge)
    ui.setze_modus("dunkel")


def test_schema_beispielzeilen_umgehen_keine_whitelist(mini_db):
    with sqlite3.connect(mini_db) as conn:
        conn.execute("CREATE VIEW sicht AS SELECT wert FROM geheim")
    ex = ReadOnlySQLExecutor(mini_db, erlaubte_spalten={"sicht": {"wert": "INTEGER"}})
    with pytest.raises(sqlite3.DatabaseError):
        ex.schema_description(sample_rows=1)


def test_injection_durch_agentenpfad_ohne_datenveraenderung(demo_daten):
    from src.agent import AgentConfig
    from src.sicherheitstest import pruefe_injection

    vorher = hashlib.sha256(demo_daten.db_path.read_bytes()).hexdigest()
    audit = AuditProtokoll()
    assert pruefe_injection(AgentConfig(db_path=demo_daten.db_path), audit)
    assert audit.eintraege[-1].art == "ABGELEHNT"
    assert "DELETE" in audit.eintraege[-1].sql
    assert hashlib.sha256(demo_daten.db_path.read_bytes()).hexdigest() == vorher
