"""Nachweisdatei docs/demolauf.json aus einem frischen Demo-Lauf (Seed 42) erzeugen.

Aufruf im Projektordner:

    uv run python tools/demolauf_erzeugen.py [docs/demolauf.json]

Alle Werte stammen aus den Fachfunktionen; nichts wird von Hand eingetragen.
"""

from __future__ import annotations

import json
import sys
import tempfile
import tomllib
from dataclasses import asdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analytics import analysiere_prozess, lade_event_log, lade_tabelle  # noqa: E402
from src.cockpit import quartalskennzahlen  # noqa: E402
from src.kostenstufen import FERTIGUNG, GEMEIN, QUALITAET  # noqa: E402
from src.seed_data import erzeuge_alles  # noqa: E402
from src.simulation import Annahmen, simuliere  # noqa: E402
from src.strategie import (  # noqa: E402
    abc_analyse,
    dso_zeitreihe,
    ergebnisrechnung,
    prozess_kapital,
    scorecard,
    scorecard_stand,
    verdichte,
)
from src.suite_abgleich import referenz  # noqa: E402

JAHR = 2026
WURZEL = Path(__file__).resolve().parents[1]


def _zeilen(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.to_json(orient="records", force_ascii=False))


def main(ziel: Path) -> None:
    with tempfile.TemporaryDirectory() as ordner:
        lauf = erzeuge_alles(ordner, seed=42)
        db = lauf.db_path
        s = ergebnisrechnung(db)
        jahr = s[s.geschaeftsjahr == JAHR]
        abc, pareto = abc_analyse(jahr)
        log = lade_event_log(lauf.eventlog_path)
        bsc, bsc_gesamt = scorecard_stand(scorecard(db, JAHR, lauf.eventlog_path), JAHR)
        q = quartalskennzahlen(str(db))
        kosten = lade_tabelle(db, "plan_ist_finanzen")

        abgleich = []
        for j in (2024, 2025, 2026):
            ref = referenz()["summen"][str(j)]
            teil = s[s.geschaeftsjahr == j]
            k = kosten[kosten.geschaeftsjahr == j]
            ist = {
                "umsatz_cent": int(teil.umsatz_cent.sum()),
                "hk_cent": int(teil.variabel_cent.sum()),
                "db_i_cent": int(teil.db_i_cent.sum()),
                "kostenstellen_cent": int(k.ist_eur.map(lambda v: round(v * 100)).sum()),
                "ebit_cent": int(teil.db_iii_cent.sum()),
            }
            abgleich.append(
                {
                    "geschaeftsjahr": j,
                    "controllai": ist,
                    "varianceai": {f: ref[f] for f in ist},
                    "differenz_cent": {f: ist[f] - ref[f] for f in ist},
                    "ebit_cockpit_cent": round(float(q[q.geschaeftsjahr == j].ebit_eur.sum()) * 100),
                }
            )

        ergebnis = {
            "version": tomllib.loads((WURZEL / "pyproject.toml").read_text())["project"]["version"],
            "seed": 42,
            "jahr": JAHR,
            "stichtag": "2026-09-30",
            "kostenstufen": {
                "db_ii_fertigung": list(FERTIGUNG),
                "db_ii_qualitaet": list(QUALITAET),
                "db_iii_unternehmen": list(GEMEIN),
            },
            "suite_abgleich": abgleich,
            "summen": _zeilen(verdichte(jahr, []))[0],
            "jahre": _zeilen(verdichte(s, ["geschaeftsjahr"])),
            "quartale": _zeilen(verdichte(s, ["geschaeftsjahr", "quartal"])),
            "produktgruppen": _zeilen(verdichte(s, ["geschaeftsjahr", "produktgruppe"])),
            "regionen": _zeilen(verdichte(s, ["geschaeftsjahr", "region"])),
            "kunden": _zeilen(abc),
            "pareto": pareto,
            "dso": _zeilen(dso_zeitreihe(db)),
            "bsc": _zeilen(bsc),
            "bsc_gesamt": bsc_gesamt,
            "prozess": analysiere_prozess(log, prozessname="Order-to-Cash").to_facts(),
            "kapital": prozess_kapital(log),
            "simulation": {"annahmen": asdict(Annahmen()), **simuliere(jahr, Annahmen())},
            "datenqualitaet": lauf.bereinigung.model_dump(),
            "transaktionen": lauf.anzahl_transaktionen,
            "negative_kunden": _zeilen(abc.loc[abc.db_ii_cent < 0, ["kunden_nr", "db_ii_eur"]]),
        }
    ziel.write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"geschrieben: {ziel}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else WURZEL / "docs" / "demolauf.json")
