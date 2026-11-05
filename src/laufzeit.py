"""Laufzeit, Benutzerdaten und sichere Schlüsselauflösung."""

from __future__ import annotations

import importlib.util
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv

from desktop.konfiguration import lade_konfiguration
from desktop.launcher import schluessel_aus_schluesselbund


def laufzeit() -> str:
    wert = os.getenv("AGENT_LAUFZEIT", "web").strip().lower()
    return wert if wert in {"desktop", "lokal"} else "web"


def datenordner() -> Path:
    if os.getenv("AGENT_DATENORDNER") or laufzeit() != "web":
        return lade_konfiguration().datenordner / "daten-v2.2.1"
    return Path(tempfile.gettempdir()) / "ControllAI-demo-v2.2.1" / "daten-v2.2.1"


def lade_geheimnisse() -> None:
    """Bestehende Umgebung gewinnt; Schlüsselbund nur beim lokalen Betrieb."""
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
    if laufzeit() in {"desktop", "lokal"}:
        for name in lade_konfiguration().geheimnisse:
            if not os.getenv(name):
                wert = schluessel_aus_schluesselbund("ControllAI", name)
                if wert:
                    os.environ[name] = wert


def anbieter_vorauswahl() -> str:
    wert = os.getenv("LLM_ANBIETER", os.getenv("LLM_PROVIDER", "mock")).strip().lower()
    return {"anthropic": "claude", "claude": "claude", "gemini": "gemini"}.get(wert, "mock")


def fehlender_zugang(anbieter: str) -> str | None:
    if anbieter == "mock":
        return None
    schluessel, modul = {"claude": ("ANTHROPIC_API_KEY", "anthropic"), "gemini": ("GEMINI_API_KEY", "google.genai")}[
        anbieter
    ]
    try:
        vorhanden = importlib.util.find_spec(modul) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        vorhanden = False
    gruende = []
    if not os.getenv(schluessel):
        gruende.append(f"{schluessel} fehlt. In der Umgebung, .env oder lokal im macOS-Schlüsselbund hinterlegen.")
    if not vorhanden:
        gruende.append(f"SDK {modul} fehlt. Mit uv sync installieren.")
    return " ".join(gruende) or None
