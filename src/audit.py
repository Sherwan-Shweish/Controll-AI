"""Append-only-Sitzungsprotokoll mit unveränderlichen Einträgen und JSON-Export.

Kein revisionssicheres Archiv: Der Betreiber muss den Export extern aufbewahren.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class Ereignis:
    nummer: int
    zeit: str
    art: str
    schicht: str
    grund: str
    sql: str
    vorgaenger: str
    hash: str


class AuditProtokoll:
    def __init__(self) -> None:
        self._eintraege: tuple[Ereignis, ...] = ()

    @property
    def eintraege(self) -> tuple[Ereignis, ...]:
        return self._eintraege

    def ergaenze(self, art: str, schicht: str, grund: str, sql: str = "") -> None:
        daten = dict(
            nummer=len(self._eintraege) + 1,
            zeit=datetime.now(UTC).isoformat(),
            art=art,
            schicht=schicht,
            grund=grund,
            sql=sql,
            vorgaenger=self._eintraege[-1].hash if self._eintraege else "",
        )
        digest = hashlib.sha256(json.dumps(daten, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        self._eintraege += (Ereignis(**daten, hash=digest),)

    def exportiere(self) -> str:
        return json.dumps([asdict(e) for e in self._eintraege], ensure_ascii=False, indent=2)
