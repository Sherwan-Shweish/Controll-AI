"""Faktengebundene Kommentare und namentliche, versionsgebundene Freigabe.

Freitext kann keine numerisch geprüfte Aussage vortäuschen: freigabefähige
Faktensätze werden ausschließlich aus benannten Fakten gerendert. Freie
Handlungsempfehlungen sind bewusst getrennt und dürfen keine Zahlen enthalten.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime

from src.demo import de


@dataclass(frozen=True)
class Fakt:
    id: str
    bezeichnung: str
    wert: float
    einheit: str
    stellen: int = 2

    def satz(self) -> str:
        return f"{self.bezeichnung}: {de(self.wert, self.stellen)} {self.einheit}."


def fingerprint(kontext: dict) -> str:
    return hashlib.sha256(json.dumps(kontext, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class Kommentar:
    fakten_ids: tuple[str, ...]
    text: str
    empfehlung: str
    kontext_hash: str
    freigeber: str = ""
    zeit: str = ""
    freigabe_hash: str = ""


def entwurf(fakten: dict[str, Fakt], ids: list[str], empfehlung: str, kontext: dict) -> Kommentar:
    if not ids or len(set(ids)) != len(ids) or any(i not in fakten for i in ids):
        raise ValueError("Mindestens eine eindeutige, bekannte Faktenreferenz auswählen.")
    if re.search(r"\d", empfehlung) or len(empfehlung) > 600:
        raise ValueError("Empfehlung ohne Zahlen und mit höchstens 600 Zeichen eingeben.")
    return Kommentar(tuple(ids), "\n".join(fakten[i].satz() for i in ids), empfehlung.strip(), fingerprint(kontext))


def pruefe(k: Kommentar, fakten: dict[str, Fakt], kontext: dict) -> bool:
    return (
        bool(k.fakten_ids)
        and len(set(k.fakten_ids)) == len(k.fakten_ids)
        and all(i in fakten for i in k.fakten_ids)
        and k.text == "\n".join(fakten[i].satz() for i in k.fakten_ids)
        and k.kontext_hash == fingerprint(kontext)
        and not re.search(r"\d", k.empfehlung)
        and len(k.empfehlung) <= 600
    )


def _inhalt_hash(k: Kommentar) -> str:
    return fingerprint({a: b for a, b in asdict(k).items() if a != "freigabe_hash"})


def freigeben(k: Kommentar, name: str, fakten: dict[str, Fakt], kontext: dict) -> Kommentar:
    name = name.strip()
    if len(name.split()) < 2 or len(name) > 100 or not any(c.isalpha() for c in name):
        raise ValueError("Vor- und Nachnamen zur nachvollziehbaren Freigabe eingeben.")
    if not pruefe(k, fakten, kontext):
        raise ValueError("Faktenprüfung fehlgeschlagen oder Datenstand verändert.")
    neu = replace(k, freigeber=name, zeit=datetime.now(UTC).isoformat(), freigabe_hash="")
    return replace(neu, freigabe_hash=_inhalt_hash(neu))


def freigegebene(kommentare: list[Kommentar], fakten: dict[str, Fakt], kontext: dict) -> list[Kommentar]:
    return [
        k
        for k in kommentare
        if k.freigeber and k.zeit and pruefe(k, fakten, kontext) and k.freigabe_hash == _inhalt_hash(k)
    ]
