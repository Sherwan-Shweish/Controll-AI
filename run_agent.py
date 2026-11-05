"""ControllAI: Diagnose und reproduzierbare Demo-Daten."""

from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(description="ControllAI – Enterprise-BI-Copilot")
    parser.add_argument("befehl", choices=["diagnose", "demo"])
    args = parser.parse_args()
    if args.befehl == "diagnose":
        from src.diagnose import bericht, pruefungen

        print(bericht())
        return int(not all(ok for _, ok, _ in pruefungen()))
    from src.laufzeit import datenordner
    from src.seed_data import erzeuge_alles

    ergebnis = erzeuge_alles(datenordner())
    print(f"Demo erzeugt: {ergebnis.db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
