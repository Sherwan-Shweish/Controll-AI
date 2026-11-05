"""Nachvollziehbarer Berichtstrichter über dieselben aktuellen Kennzahlobjekte."""

from src.kommentare import fingerprint, freigegebene, pruefe


def wesentlich(fakt):
    """Demo-Schwelle: Geldbeträge ab 1.000 €, übrige gemessene Kennzahlen immer."""
    return abs(fakt.wert) >= 1000 if fakt.einheit == "€" else True


def pruefpfad(fakten, kontext, kommentare, entwurf=None, berichtstand=None):
    objekte = set(fakten)
    relevant = {k for k, f in fakten.items() if wesentlich(f)}
    alle = [*kommentare, *([entwurf] if entwurf else [])]
    aktuell = [k for k in alle if k.kontext_hash == fingerprint(kontext)]
    kommentiert = {i for k in aktuell for i in k.fakten_ids} & relevant
    geprueft = {i for k in aktuell if pruefe(k, fakten, kontext) for i in k.fakten_ids} & kommentiert
    frei = freigegebene(kommentare, fakten, kontext)
    freigegeben = {i for k in frei for i in k.fakten_ids} & geprueft
    berichtet = set()
    if berichtstand and berichtstand["kontext"] == fingerprint(kontext):
        berichtet = set(berichtstand["ids"]) & freigegeben
    veraltet = {i for k in alle if k.kontext_hash != fingerprint(kontext) for i in k.fakten_ids}
    gruende = {"Unter Schwelle": 0, "Nicht geprüft": 0, "Nicht freigegeben": 0, "Veraltet": 0, "Export ausstehend": 0}
    for i in objekte - berichtet:
        if i not in relevant:
            grund = "Unter Schwelle"
        elif i in veraltet and i not in geprueft:
            grund = "Veraltet"
        elif i not in geprueft:
            grund = "Nicht geprüft"
        elif i not in freigegeben:
            grund = "Nicht freigegeben"
        else:
            grund = "Export ausstehend"
        gruende[grund] += 1
    return {
        "stufen": [len(s) for s in (objekte, relevant, kommentiert, geprueft, freigegeben, berichtet)],
        "gruende": gruende,
    }
