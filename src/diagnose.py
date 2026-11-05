"""Reproduzierbare Systemprüfung ohne Ausgabe von Schlüsselwerten."""

from __future__ import annotations

import importlib
import sys
from importlib.metadata import version

from src.laufzeit import laufzeit


def pruefungen() -> list[tuple[str, bool, str]]:
    ergebnis = [("Python", sys.version_info >= (3, 11), sys.version.split()[0])]
    for name in ("streamlit", "pyarrow", "pandas", "numpy", "sqlglot", "altair", "pydantic"):
        try:
            importlib.import_module(name)
            ergebnis.append((name, True, version(name)))
        except Exception:
            ergebnis.append((name, False, "Import fehlgeschlagen – uv sync ausführen."))
    ergebnis.append(("Laufzeit", True, laufzeit()))
    return ergebnis


def bericht() -> str:
    return "\n".join(f"{'OK' if ok else 'FEHLER'} · {name}: {detail}" for name, ok, detail in pruefungen())
