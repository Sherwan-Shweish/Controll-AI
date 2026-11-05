"""Deterministische Daten und Exporte; Funktions- und Dateistand trennen Cacheeinträge."""

from functools import wraps
from hashlib import sha256
from inspect import getsource
from pathlib import Path

import streamlit as st


def dateistand(pfad):
    p = Path(pfad)
    return (str(p.resolve()), p.stat().st_mtime_ns, p.stat().st_size) if p.exists() else (str(p), 0, 0)


def dateicache(funktion):
    kennung = (funktion.__module__, funktion.__qualname__, sha256(getsource(funktion).encode()).hexdigest())

    @st.cache_data(show_spinner=False, max_entries=64)
    def gespeichert(funktionsstand, stand, args, kwargs):
        return funktion(*args, **kwargs)

    @wraps(funktion)
    def aufruf(*args, **kwargs):
        dateien = []
        for wert in (*args, *kwargs.values()):
            if isinstance(wert, (str, Path)):
                try:
                    if Path(wert).is_file():
                        dateien.append(dateistand(wert))
                except OSError:
                    pass  # Ein langer Freitext ist kein Dateipfad.
        return gespeichert(kennung, tuple(dateien), args, kwargs)

    return aufruf
