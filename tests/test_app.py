"""AppTest: fachliche Wege und Sicherheitsgrenzen der Standardmigration."""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def html(app):
    return "\n".join(h.proto.body for h in app.get("html"))


@pytest.fixture
def app(monkeypatch, demo_daten, tmp_path) -> AppTest:
    monkeypatch.setenv("CONTROLLAI_DEMO", "1")
    monkeypatch.setenv("LLM_ANBIETER", "mock")
    monkeypatch.setenv("AGENT_DATENORDNER", str(tmp_path))
    monkeypatch.setenv("DB_PATH", str(demo_daten.db_path))
    monkeypatch.delenv("AGENT_LAUFZEIT", raising=False)
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception, [e.value for e in at.exception]
    assert not [e for e in at.error if "vollständig geladen" in e.value]
    return at


def test_app_startet_im_demo_modus(app):
    assert len(app.tabs) == 7
    assert app.tabs[-1].label == "Agent & Audit"
    assert "BI-Copilot" in html(app)
    for label in ("Umsatz · Mio. €", "DB-II-Marge", "EBIT · Mio. €", "DSO · Tage", "BSC-Zielerreichung"):
        assert label in html(app)
    assert html(app).count('class="va-kpi-label"') == 5
    assert "Pp" in html(app) and "data:image/svg+xml;base64," in html(app)
    assert any("Demo-Modus" in e.value for e in app.info)


def test_jeder_tab_nennt_seine_leitfrage(app):
    assert html(app).count('class="va va-leitfrage"') == 6
    app.session_state["haupttabs"] = "Prozesse"
    app.run()
    assert html(app).count('class="va va-leitfrage"') == 7
    exp = next(e for e in app.expander if e.label == "So ist die App aufgebaut")
    assert exp.proto.expanded is False
    assert any(e.label == "So ist die App aufgebaut" for e in app.tabs[0].expander)


def test_engpass_wird_hervorgehoben(app):
    app.session_state["haupttabs"] = "Prozesse"
    app.run()
    assert any("Engpass: Faktura buchen → Mahnung" in e.value for e in app.error)
    assert any("Einkaufsrechnungen und P2P → FlowAudit-AI" in c.value for c in app.caption)


def test_executive_summary_und_bpmn(app):
    app.button(key="btn_bericht").click().run()
    app.session_state["haupttabs"] = "Prozesse"
    app.run()
    app.button(key="btn_bpmn").click().run()
    assert not app.exception
    assert not [e for e in app.error if "vollständig geladen" in e.value]
    assert any("Faktenprüfung bestanden" in s.value for s in app.success)
    assert "Management-Bericht Geschäftsjahr 2026" in html(app)


def test_bsc_human_in_the_loop(app):
    app.button(key="btn_bsc").click().run()
    assert not app.exception
    assert len(app.metric) == 0
    import re

    werte = {
        titel: wert for wert, titel in re.findall(r'<b style="color:[^"]+">(.*?)</b><small>(.*?)</small>', html(app))
    }
    assert werte["Projekte"] == "11"
    assert werte["Zitate belegt"] == "10 / 11"
    assert werte["Zur Prüfung markiert"] == "3"
    assert werte["Offen"] == "11"
    import json

    editor = next(d for d in app.dataframe if "text_id" in d.value.columns)
    spalten = json.loads(editor.proto.columns)
    assert all("_" not in c["label"] for c in spalten.values() if not c.get("hidden"))
    assert editor.value.ki_konfidenz.str.fullmatch(r"\d+,\d %").all()


def test_text_to_sql_beispielfrage(app):
    app.button(key="bsp_marge").click().run()
    assert not app.exception
    assert "DB-I-Marge" in html(app)
    assert any("Faktenprüfung bestanden" in s.value for s in app.success)
    assert any("umsatz_transaktionen" in c.value for c in app.code)
    assert any(e.art == "ZUGELASSEN" for e in app.session_state["audit_protokoll"].eintraege)


def test_sicherheitstest_wird_blockiert(app):
    app.button(key="bsp_angriff").click().run()
    assert any("Vom SQL-Guard blockiert" in e.value for e in app.error)
    assert any("DELETE FROM umsatzplanung" in c.value for c in app.code)
    assert "1 blockiert" in html(app)


def test_freie_frage_im_demo_modus(app):
    app.text_input(key="frage").input("Wie viele Mitarbeitende hat das Unternehmen?")
    app.button(key="FormSubmitter:frageformular-Frage stellen").click().run()
    assert not app.exception
    assert "nicht beantwortbar" in html(app)


def test_geschaeftsjahr_wechsel(app):
    app.selectbox(key="geschaeftsjahr").select(2024).run()
    assert not app.exception
    assert "Kein PY" in html(app)
    assert any("Geschäftsjahr 2024" in c.value for c in app.caption)


@pytest.mark.parametrize("anbieter", ["claude", "gemini"])
def test_anbieter_immer_sichtbar_und_rueckfall(app, monkeypatch, anbieter):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    auswahl = app.selectbox(key="ki_anbieter")
    assert auswahl.options == ["Offline (Mock)", "Anthropic Claude", "Google Gemini"]
    auswahl.select(anbieter).run()
    assert app.warning and any("Offline-Modus arbeitet weiter" in w.value for w in app.warning)
    assert any("mock:deterministisch" in c.value for c in app.caption)
    app.button(key="bsp_marge").click().run()
    assert any("Faktenprüfung bestanden" in e.value for e in app.success)


def test_injection_test_zaehler_im_selben_lauf(app):
    app.button(key="injection_test").click().run()
    assert "1 blockiert" in html(app)
    vorher = app.session_state["audit_protokoll"].eintraege
    app.button(key="injection_test").click().run()
    nachher = app.session_state["audit_protokoll"].eintraege
    assert nachher[: len(vorher)] == vorher
    assert "2 blockiert" in html(app)


def test_fehlergrenze_schuetzt_andere_tabs(app, monkeypatch):
    import src.analytics

    def fehler(*args, **kwargs):
        raise ValueError("Testfehler")

    monkeypatch.setattr(src.analytics, "analysiere_prozess", fehler)
    import streamlit as st

    st.cache_data.clear()
    app.session_state["haupttabs"] = "Prozesse"
    app.run()
    assert not app.exception
    assert any("Process Mining konnte nicht vollständig geladen" in e.value for e in app.error)
    app.button(key="bsp_marge").click().run()
    assert any("Faktenprüfung bestanden" in e.value for e in app.success)


def test_szenario_speichern_und_vergleichen(app):
    app.slider(key="sim_preis").set_value(5).run()
    app.button(key="sim_speichern").click().run()
    s = list(app.session_state["szenarien"].values())[0]
    assert s["annahmen"]["preis_pct"] == 5
    assert s["wirkung_cent"] > 0
    assert not [e for e in app.error if "vollständig geladen" in e.value]


def test_management_freigabe_und_veraltung(app):
    app.button(key="kommentar_erstellen").click().run()
    app.text_input(key="freigeber").input("Erika Beispiel")
    app.checkbox(key="freigabe_bestaetigt").check().run()
    app.button(key="kommentar_freigeben").click().run()
    assert len(app.session_state["management_kommentare"]) == 1
    app.slider(key="sim_menge").set_value(-5).run()
    assert any("alte Freigabe ist nicht exportfähig" in w.value for w in app.warning)
    assert app.button(key="kommentar_freigeben").disabled


def test_export_und_drilldown(app):
    app.selectbox(key="region_filter").select("NORD").run()
    app.selectbox(key="produkt_filter").select("ANT").run()
    assert not [e for e in app.error if "vollständig geladen" in e.value]
    app.button(key="management_export").click().run()
    assert not [e for e in app.error if "vollständig geladen" in e.value]
    labels = [d.label for d in app.get("download_button")]
    assert "Excel mit Formel-Gegenprüfung" in labels
    assert "Management-Bericht PDF" in labels
