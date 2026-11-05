"""SQL-Parser und explizite Freigaben. Keine Sicherheitsentscheidung durch Textmuster."""

from __future__ import annotations

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError
from sqlglot.optimizer.scope import traverse_scope

from src.sql_schema import STANDARD_SCHEMA

# Kleine, explizite Funktionsmenge. Keine Dateizugriffe, Erweiterungen oder Speicherbomben.
FUNKTIONEN = frozenset(
    {
        "and",
        "or",
        "case",
        "abs",
        "avg",
        "cast",
        "ceil",
        "ceiling",
        "coalesce",
        "count",
        "date",
        "datetime",
        "floor",
        "if",
        "ifnull",
        "iif",
        "julianday",
        "length",
        "lower",
        "ltrim",
        "max",
        "min",
        "nullif",
        "replace",
        "round",
        "rtrim",
        "strftime",
        "substr",
        "substring",
        "sum",
        "time",
        "total",
        "trim",
        "upper",
        "row_number",
        "rank",
        "dense_rank",
        "lag",
        "lead",
        "first_value",
        "last_value",
    }
)


class Prueffehler(ValueError):
    def __init__(self, grund: str, schicht: str = "Parser") -> None:
        super().__init__(grund)
        self.schicht = schicht


def parse_lesend(sql: str) -> exp.Expression:
    if not sql or len(sql) > 30_000:
        raise Prueffehler("Leere oder zu lange SQL-Abfrage.")
    try:
        befehle = sqlglot.parse(sql, read="sqlite")
    except SqlglotError as exc:
        raise Prueffehler("SQL konnte nicht eindeutig geparst werden.") from exc
    if len(befehle) != 1 or not isinstance(befehle[0], (exp.Select, exp.SetOperation)):
        raise Prueffehler("Genau eine lesende SELECT-/WITH-Abfrage ist erlaubt.")
    baum = befehle[0]
    for knoten in baum.walk():
        if knoten.comments:
            raise Prueffehler("Kommentare sind in generierten Abfragen nicht erlaubt.")
        if isinstance(knoten, (exp.DDL, exp.DML, exp.Command, exp.Into, exp.Lock)):
            raise Prueffehler("Schreibende oder administrative SQL-Knoten sind nicht erlaubt.")
        if isinstance(knoten, exp.Func):
            name = knoten.name if isinstance(knoten, exp.Anonymous) else knoten.sql_name()
            if name.lower() not in FUNKTIONEN:
                raise Prueffehler(f"Funktion nicht freigegeben: {name}.", "Funktions-Whitelist")
    return baum


def pruefe_tabellen(baum: exp.Expression, schema: dict | None = None) -> None:
    schema = STANDARD_SCHEMA if schema is None else schema
    for scope in traverse_scope(baum):
        for quelle in scope.sources.values():
            if isinstance(quelle, exp.Table):
                if quelle.db or quelle.catalog or not isinstance(quelle.this, exp.Identifier):
                    raise Prueffehler("Fremde Schemas und Tabellenfunktionen sind gesperrt.", "Tabellen-Whitelist")
                if quelle.name.lower() not in schema:
                    raise Prueffehler(f"Tabelle nicht freigegeben: {quelle.name}.", "Tabellen-Whitelist")
