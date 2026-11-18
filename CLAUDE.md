# Arbeitsregeln für KI-gestützte Entwicklung (Agenten-Standard v1)

Dieses Projekt folgt `docs/STANDARD.md`. Kurzfassung für jede Änderung:

1. **Rechnen in Python, Formulieren durch das LLM.** Keine Zahl, die nicht aus einer Engine stammt und geprüft ist.
2. **Struktur einhalten:** Fachlogik in `src/`, Oberfläche in `app.py` + `src/ui_*.py`, Desktop-Schicht `desktop/`
   generisch lassen (projektspezifisch nur `desktop/app.toml`).
3. **Abhängigkeiten nur über uv:** `uv add <paket>`; `requirements.txt` synchron halten.
4. **Oberfläche:** dynamische Texte immer mit `ui.e()` maskieren; Farben nur aus `ui.FARBEN` (beide Modi testen).
5. **Keine Secrets im Code:** Schlüssel über `.env` oder macOS-Schlüsselbund (`desktop/app.toml` → `geheimnisse`).
6. **Tests zuerst bei Fachlogik**, danach `uv run pytest` und `uv run ruff check .` – beide müssen grün sein.
7. **Sprache:** Code, Kommentare und Oberfläche auf Deutsch (Portfolio-Projekte); Antworten an den Nutzer auf Arabisch.
8. **Offline-Modus** (Mock-Client) muss immer vollständig funktionieren.

Häufige Befehle:

```bash
uv sync                                   # Umgebung herstellen
uv run streamlit run app.py               # im Browser (Webmodus, festes Thema)
AGENT_LAUFZEIT=lokal uv run streamlit run app.py   # im Browser mit Umschalter hell/dunkel
uv run python -m desktop.launcher         # im Mac-Fenster
uv run python -m desktop.build_app        # ~/Applications/ControllAI.app erzeugen
uv run pytest -q && uv run ruff check .   # Qualität
uv run python run_agent.py diagnose       # Umgebung prüfen
```

ControllAI-Ausnahme: Text-to-SQL ist erlaubt, jedoch nur über Parser, Schema-/Spalten-Whitelist, read-only Verbindung und Ressourcenlimits. Fachliche Erweiterungen stehen in strategie.py, simulation.py, kommentare.py und bericht_export.py. Kostenstufen (DB II/DB III) nur in
kostenstufen.py; Suite-Abgleich mit VarianceAI über suite_abgleich.py und die Referenz aus tools/suite_referenz_erzeugen.py –
Umsatz, HK, Kostenstellen und EBIT müssen centgleich bleiben (tests/test_suite_kosten.py). Management-Exporte prüfen jede Freigabe erneut gegen den aktuellen Kontext; diese Grenze nicht umgehen.
