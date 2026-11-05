"""Desktop-Schicht nach Agenten-Standard v1: Konfiguration, Einstellungen, Launcher, App-Bundle."""

from __future__ import annotations

import json
import os
import plistlib
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from desktop import build_app, launcher, praeferenzen
from desktop.konfiguration import PROJEKT_ORDNER, lade_konfiguration


@pytest.fixture()
def konfig(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DATENORDNER", str(tmp_path))
    return lade_konfiguration()


def test_konfiguration_aus_app_toml(konfig, tmp_path):
    assert konfig.name == "ControllAI" and konfig.bundle_id == "de.shweish.controllai"
    assert konfig.einstieg_pfad == PROJEKT_ORDNER / "app.py" and konfig.einstieg_pfad.exists()
    assert konfig.datenordner == tmp_path / "ControllAI"  # nie im Projekt- oder Git-Ordner
    assert "ANTHROPIC_API_KEY" in konfig.geheimnisse
    assert konfig.logo == "Σ" and konfig.version == "2.2.1"


def test_praeferenzen_speichern_und_laden(konfig):
    assert praeferenzen.lade(konfig) == {"darstellung": "dunkel"}
    praeferenzen.speichere({"darstellung": "hell"}, konfig)
    assert praeferenzen.lade(konfig)["darstellung"] == "hell"
    with pytest.raises(ValueError):
        praeferenzen.speichere({"darstellung": "lila"}, konfig)


def test_beschaedigte_einstellungen_fallen_auf_standard_zurueck(konfig):
    datei = konfig.datenordner / "einstellungen.json"
    datei.parent.mkdir(parents=True)
    datei.write_text("{kaputt", encoding="utf-8")
    assert praeferenzen.lade(konfig) == {"darstellung": "dunkel"}
    datei.write_text(json.dumps({"darstellung": "<script>"}), encoding="utf-8")
    assert praeferenzen.lade(konfig) == {"darstellung": "dunkel"}  # nur erlaubte Werte


def test_einzelinstanz(tmp_path):
    erste, zweite = launcher.Einzelinstanz(tmp_path / "x.lock"), launcher.Einzelinstanz(tmp_path / "x.lock")
    assert erste.erwerben()
    assert not zweite.erwerben()
    erste.freigeben()
    assert zweite.erwerben()
    zweite.freigeben()


def test_server_nur_lokal_und_mit_waechter(konfig):
    befehl = launcher.streamlit_befehl(konfig, 8999, "dunkel")
    assert "--server.address=127.0.0.1" in befehl and "--server.port=8999" in befehl
    assert befehl[1:3] == ["-m", "desktop.server"] and "--eltern-pid" in befehl


def test_thema_argumente_je_darstellung(konfig):
    hell = launcher.thema_argumente(konfig, "hell")
    assert "--theme.base=light" in hell and "--theme.backgroundColor=#F7F6F3" in hell
    assert "--theme.base=dark" in launcher.thema_argumente(konfig, "dunkel")


def test_geheimnisse_vorrang_umgebung_env_schluesselbund(konfig, monkeypatch, tmp_path):
    abgefragt: list[str] = []

    def schluesselbund(dienst: str, konto: str) -> str | None:
        abgefragt.append(konto)
        return f"aus-schluesselbund-{konto}"

    monkeypatch.setenv("ANTHROPIC_API_KEY", "aus-umgebung")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(launcher, "_env_datei", lambda projekt: {})
    env = launcher.umgebung(konfig, schluesselbund)
    assert env["ANTHROPIC_API_KEY"] == "aus-umgebung"  # Umgebung gewinnt
    assert env["GEMINI_API_KEY"] == "aus-schluesselbund-GEMINI_API_KEY"
    assert abgefragt == ["GEMINI_API_KEY"]
    abgefragt.clear()  # Wert in .env: Schlüsselbund wird nicht gefragt
    monkeypatch.setattr(launcher, "_env_datei", lambda projekt: {"GEMINI_API_KEY": "aus-env-datei"})
    launcher.umgebung(konfig, schluesselbund)
    assert abgefragt == []


def test_ladeseite_maskiert_und_zeigt_fehler(konfig, tmp_path):
    seite = launcher.ladeseite(konfig, "hell", fehler="<b>boom</b>", logdatei=tmp_path / "server.log")
    assert "&lt;b&gt;boom&lt;/b&gt;" in seite and "#F7F6F3" in seite
    assert '<div class="logo">Σ</div>' in seite  # Glyphe aus app.toml (Feld „logo“)


def test_logo_optional_mit_standard(tmp_path):
    """desktop/ ist in allen Agenten identisch – die Logo-Glyphe kommt aus app.toml, Standard „Δ“."""
    toml = tmp_path / "app.toml"
    toml.write_text('[app]\nname = "X"\nbundle_id = "de.x"\n', encoding="utf-8")
    assert lade_konfiguration(toml).logo == "Δ"
    toml.write_text('[app]\nname = "X"\nbundle_id = "de.x"\nlogo = "§"\n', encoding="utf-8")
    assert lade_konfiguration(toml).logo == "§"


def _port_belegt(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def test_server_endet_mit_dem_launcher(tmp_path):
    """Ende-zu-Ende ohne Fenster: Server startet, antwortet – und stirbt mit dem Launcher (kein Waisenprozess)."""
    env = {**os.environ, "AGENT_DATENORDNER": str(tmp_path)}
    prozess = subprocess.Popen(
        [sys.executable, "-m", "desktop.launcher", "--nur-server"],
        cwd=PROJEKT_ORDNER,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        url = prozess.stdout.readline().strip()  # type: ignore[union-attr]
        assert url.startswith("http://127.0.0.1:"), url
        with urllib.request.urlopen(f"{url}/_stcore/health", timeout=5) as antwort:
            assert antwort.status == 200
        port = int(url.rsplit(":", 1)[1])
    finally:
        prozess.kill()  # harter Abbruch wie bei einem Absturz – atexit läuft nicht
        prozess.wait(timeout=10)
    for _ in range(40):  # Wächter beendet den Server binnen Sekunden
        if not _port_belegt(port):
            break
        time.sleep(0.25)
    assert not _port_belegt(port)


def test_app_bundle(konfig, tmp_path):
    app = build_app.baue_app(konfig, tmp_path)
    assert app.name == "ControllAI.app"
    info = plistlib.loads((app / "Contents" / "Info.plist").read_bytes())
    assert info["CFBundleIdentifier"] == "de.shweish.controllai" and info["CFBundleExecutable"] == "ControllAI"
    starter = app / "Contents" / "MacOS" / "ControllAI"
    assert starter.stat().st_mode & 0o111  # ausführbar
    text = starter.read_text(encoding="utf-8")
    assert str(PROJEKT_ORDNER) in text and "python -m desktop.launcher" in text and "uv" in text
    assert subprocess.run(["bash", "-n", str(starter)], check=False).returncode == 0  # Syntax gültig
    assert (app / "Contents" / "Resources" / "AppIcon.icns").stat().st_size > 10_000


def test_app_hell_dunkel_umschalten(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("AGENT_DATENORDNER", str(tmp_path))
    monkeypatch.setenv("AGENT_LAUFZEIT", "desktop")
    at = AppTest.from_file(str(PROJEKT_ORDNER / "app.py"), default_timeout=180).run()
    assert not at.exception

    def stil() -> str:
        return "\n".join(h.proto.body for h in at.get("html"))

    assert "--va-flaeche:#0E0E0D" in stil()
    at.button_group(key="darstellung_wahl").set_value("hell").run()
    assert not at.exception
    assert "--va-flaeche:#F7F6F3" in stil() and "--va-flaeche:#0E0E0D" not in stil()
    gespeichert = json.loads((Path(tmp_path) / "ControllAI" / "einstellungen.json").read_text(encoding="utf-8"))
    assert gespeichert == {"darstellung": "hell"}
    at.button_group(key="darstellung_wahl").set_value("dunkel").run()  # zurück, damit andere Tests dunkel starten


def test_webmodus_ohne_umschalter_und_ohne_speichern(tmp_path, monkeypatch):
    """Streamlit Cloud: alle Besucher teilen einen Server – kein serverweites Umschalten, nichts gespeichert."""
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("AGENT_DATENORDNER", str(tmp_path))
    monkeypatch.delenv("AGENT_LAUFZEIT", raising=False)
    at = AppTest.from_file(str(PROJEKT_ORDNER / "app.py"), default_timeout=180).run()
    assert not at.exception
    assert not [b for b in at.get("button_group") if getattr(b, "key", None) == "darstellung_wahl"]
    assert "BI-Copilot" in "\n".join(h.proto.body for h in at.get("html"))
    assert not (tmp_path / "ControllAI" / "einstellungen.json").exists()


def test_launcher_markiert_desktop_laufzeit(konfig, monkeypatch):
    monkeypatch.delenv("AGENT_LAUFZEIT", raising=False)
    assert launcher.umgebung(konfig, lambda d, k: None)["AGENT_LAUFZEIT"] == "desktop"
