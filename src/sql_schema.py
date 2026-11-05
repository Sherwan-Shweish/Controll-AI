"""Explizite Tabellen- und Spaltenfreigabe für Text-to-SQL. Änderungen fachlich prüfen."""

STANDARD_SCHEMA = {
    "kostenstellen": {"kostenstelle": "TEXT", "bezeichnung": "TEXT", "bereich": "TEXT", "verantwortlich": "TEXT"},
    "produktkategorien": {"produktkategorie": "TEXT", "produktbereich": "TEXT", "fixkosten_quartal_eur": "REAL"},
    "materialien": {
        "material_nr": "TEXT",
        "bezeichnung": "TEXT",
        "produktkategorie": "TEXT",
        "listenpreis_eur": "REAL",
    },
    "kunden": {"kunden_nr": "TEXT", "kundenname": "TEXT", "branche": "TEXT", "region": "TEXT"},
    "umsatz_transaktionen": {
        "faktura_nr": "TEXT",
        "position": "INTEGER",
        "buchungsdatum": "TEXT",
        "geschaeftsjahr": "INTEGER",
        "quartal": "TEXT",
        "kunden_nr": "TEXT",
        "material_nr": "TEXT",
        "produktkategorie": "TEXT",
        "region": "TEXT",
        "menge": "REAL",
        "umsatz_eur": "REAL",
        "variable_kosten_eur": "REAL",
        "deckungsbeitrag_eur": "REAL",
        "ist_storno": "INTEGER",
        "ist_ausreisser": "INTEGER",
        "ausreisser_score": "REAL",
        "ausreisser_grund": "TEXT",
    },
    "umsatzplanung": {
        "geschaeftsjahr": "INTEGER",
        "quartal": "TEXT",
        "produktkategorie": "TEXT",
        "plan_umsatz_eur": "REAL",
        "plan_variable_kosten_eur": "REAL",
    },
    "plan_ist_finanzen": {
        "geschaeftsjahr": "INTEGER",
        "quartal": "TEXT",
        "kostenstelle": "TEXT",
        "kostenart": "TEXT",
        "plan_eur": "REAL",
        "ist_eur": "REAL",
    },
    "produktfixkosten": {
        "geschaeftsjahr": "INTEGER",
        "quartal": "TEXT",
        "produktkategorie": "TEXT",
        "fertigung_eur": "REAL",
        "qualitaet_eur": "REAL",
        "fixkosten_eur": "REAL",
    },
    "v_plan_ist_umsatz": {
        "geschaeftsjahr": "INTEGER",
        "quartal": "TEXT",
        "produktkategorie": "TEXT",
        "plan_umsatz_eur": "REAL",
        "ist_umsatz_eur": "TEXT",
        "abweichung_eur": "TEXT",
        "abweichung_pct": "TEXT",
    },
}

STANDARD_SCHEMA["materialien"]["produktgruppe"] = "TEXT"
STANDARD_SCHEMA["umsatz_transaktionen"].update(buchungskreis="TEXT", produktgruppe="TEXT")
