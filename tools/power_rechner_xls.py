#!/usr/bin/env python3
"""Prompt -> PowerRechner (.xls) im "Purple Cow"-Niveau.

Highlights:
- Akzeptiert klassische Zuweisungen (`x = ...`) und natürliche Prompt-Sätze.
- Erlaubt Rechenoperatoren + ausgewählte Funktionen: min, max, round, abs.
- Löst Abhängigkeiten automatisch (Reihenfolge im Prompt ist egal).
- Exportiert ein formatiertes Excel-2003-XML (`.xls`) mit KPI-Übersicht.

Beispiele für natürliche Prompts:
- "setze preis auf 199"
- "berechne brutto als preis * (1 + mwst)"
- "rabatt ist 15"
"""

from __future__ import annotations

import argparse
import ast
import html
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set

ASSIGNMENT_PATTERN = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*$")
SET_PATTERN = re.compile(
    r"^\s*(?:setze|set|define|definiere)\s+([A-Za-z_][A-Za-z0-9_]*)\s+(?:auf|to)\s+(.+?)\s*$",
    re.IGNORECASE,
)
IS_PATTERN = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s+(?:ist|is)\s+(.+?)\s*$", re.IGNORECASE
)
CALC_PATTERN = re.compile(
    r"^\s*(?:berechne|calculate|calc)\s+([A-Za-z_][A-Za-z0-9_]*)\s+(?:als|as)\s+(.+?)\s*$",
    re.IGNORECASE,
)

ALLOWED_FUNCTIONS: Dict[str, Any] = {
    "min": min,
    "max": max,
    "round": round,
    "abs": abs,
}


class SafeEvalVisitor(ast.NodeVisitor):
    """Sehr eingeschränkter AST-Checker für sichere Rechenausdrücke."""

    allowed_nodes = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Pow,
        ast.Mod,
        ast.USub,
        ast.UAdd,
        ast.Load,
        ast.Name,
        ast.Constant,
        ast.FloorDiv,
        ast.Call,
    )

    def __init__(self, allowed_functions: Set[str]):
        self.allowed_functions = allowed_functions

    def generic_visit(self, node: ast.AST) -> None:
        if not isinstance(node, self.allowed_nodes):
            raise ValueError(f"Nicht erlaubter Ausdruck: {type(node).__name__}")
        super().generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if not isinstance(node.func, ast.Name):
            raise ValueError("Nur direkte Funktionsnamen sind erlaubt.")
        if node.func.id not in self.allowed_functions:
            raise ValueError(f"Funktion nicht erlaubt: {node.func.id}")
        self.generic_visit(node)


@dataclass
class Assignment:
    variable: str
    expression: str
    source_line: int


@dataclass
class CalcRow:
    variable: str
    expression: str
    value: float
    row_type: str


def parse_prompt(prompt: str) -> List[Assignment]:
    raw_lines: List[tuple[int, str]] = []
    for line_no, line in enumerate(prompt.splitlines(), start=1):
        chunks = [chunk.strip() for chunk in line.split(";") if chunk.strip()]
        raw_lines.extend((line_no, chunk) for chunk in chunks)

    assignments: List[Assignment] = []

    for line_no, line in raw_lines:
        match = (
            ASSIGNMENT_PATTERN.match(line)
            or SET_PATTERN.match(line)
            or CALC_PATTERN.match(line)
            or IS_PATTERN.match(line)
        )
        if match:
            assignments.append(
                Assignment(
                    variable=match.group(1),
                    expression=normalize_expression(match.group(2)),
                    source_line=line_no,
                )
            )

    return assignments


def normalize_expression(expression: str) -> str:
    # Hilft bei natürlicher Sprache wie "plus", "mal", "hoch".
    replacements = {
        r"\bplus\b": "+",
        r"\bminus\b": "-",
        r"\bmal\b": "*",
        r"\bgeteilt durch\b": "/",
        r"\bhoch\b": "**",
    }
    normalized = expression.strip()
    for pattern, repl in replacements.items():
        normalized = re.sub(pattern, repl, normalized, flags=re.IGNORECASE)
    return normalized


def variable_dependencies(expression: str) -> Set[str]:
    tree = ast.parse(expression, mode="eval")
    deps: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id not in ALLOWED_FUNCTIONS:
            deps.add(node.id)
    return deps


def safe_eval(expr: str, variables: Dict[str, float]) -> float:
    tree = ast.parse(expr, mode="eval")
    SafeEvalVisitor(set(ALLOWED_FUNCTIONS)).visit(tree)
    compiled = compile(tree, "<expr>", "eval")
    context = {**ALLOWED_FUNCTIONS, **variables}
    value = eval(compiled, {"__builtins__": {}}, context)  # noqa: S307
    if not isinstance(value, (int, float)):
        raise ValueError(f"Ausdruck liefert keinen numerischen Wert: {expr}")
    return float(value)


def build_rows(assignments: List[Assignment]) -> List[CalcRow]:
    remaining: Dict[str, Assignment] = {a.variable: a for a in assignments}
    variables: Dict[str, float] = {}
    rows: List[CalcRow] = []

    # Letzte Definition gewinnt
    for a in assignments:
        remaining[a.variable] = a

    progress = True
    while remaining and progress:
        progress = False
        for variable in list(remaining.keys()):
            assignment = remaining[variable]
            deps = variable_dependencies(assignment.expression)
            if deps.issubset(variables.keys()):
                value = safe_eval(assignment.expression, variables)
                variables[variable] = value
                row_type = "Input" if not deps else "Formel"
                rows.append(
                    CalcRow(
                        variable=assignment.variable,
                        expression=assignment.expression,
                        value=value,
                        row_type=row_type,
                    )
                )
                del remaining[variable]
                progress = True

    if remaining:
        unresolved = ", ".join(
            f"{name} (Zeile {remaining[name].source_line})" for name in sorted(remaining)
        )
        raise ValueError(
            "Nicht auflösbare Variablen (z. B. Kreisbezug oder fehlende Eingaben): "
            f"{unresolved}"
        )

    return rows


def escape(value: Any) -> str:
    return html.escape(str(value))


def xml_row(cells: List[tuple[str, str, str]]) -> str:
    rendered = ["   <Row>"]
    for style_id, cell_type, data in cells:
        style_attr = f' ss:StyleID="{style_id}"' if style_id else ""
        rendered.append(
            f'    <Cell{style_attr}><Data ss:Type="{cell_type}">{escape(data)}</Data></Cell>'
        )
    rendered.append("   </Row>")
    return "\n".join(rendered)


def to_spreadsheet_xml(rows: List[CalcRow], source_prompt: str) -> str:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

    lines: List[str] = [
        '<?xml version="1.0"?>',
        '<?mso-application progid="Excel.Sheet"?>',
        '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"',
        ' xmlns:o="urn:schemas-microsoft-com:office:office"',
        ' xmlns:x="urn:schemas-microsoft-com:office:excel"',
        ' xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"',
        ' xmlns:html="http://www.w3.org/TR/REC-html40">',
        " <Styles>",
        '  <Style ss:ID="Default" ss:Name="Normal"><Alignment ss:Vertical="Center"/></Style>',
        '  <Style ss:ID="PurpleHeader"><Font ss:Bold="1" ss:Color="#FFFFFF"/><Interior ss:Color="#6F2DBD" ss:Pattern="Solid"/></Style>',
        '  <Style ss:ID="InputRow"><Interior ss:Color="#F3E8FF" ss:Pattern="Solid"/></Style>',
        '  <Style ss:ID="FormulaRow"><Interior ss:Color="#E9D5FF" ss:Pattern="Solid"/></Style>',
        '  <Style ss:ID="KPI"><Font ss:Bold="1" ss:Color="#4C1D95"/></Style>',
        " </Styles>",
        ' <Worksheet ss:Name="PowerRechner">',
        "  <Table>",
        xml_row([
            ("PurpleHeader", "String", "Typ"),
            ("PurpleHeader", "String", "Variable"),
            ("PurpleHeader", "String", "Ausdruck"),
            ("PurpleHeader", "String", "Wert"),
        ]),
    ]

    for row in rows:
        style = "InputRow" if row.row_type == "Input" else "FormulaRow"
        lines.append(
            xml_row(
                [
                    (style, "String", row.row_type),
                    (style, "String", row.variable),
                    (style, "String", row.expression),
                    (style, "Number", row.value),
                ]
            )
        )

    lines.extend([
        "  </Table>",
        " </Worksheet>",
        ' <Worksheet ss:Name="KPI">',
        "  <Table>",
        xml_row([("PurpleHeader", "String", "Kennzahl"), ("PurpleHeader", "String", "Wert")]),
        xml_row([("KPI", "String", "Anzahl Berechnungen"), ("", "Number", len(rows))]),
        xml_row([("KPI", "String", "Summe Werte"), ("", "Number", sum(r.value for r in rows))]),
        xml_row([("KPI", "String", "Max Wert"), ("", "Number", max((r.value for r in rows), default=0))]),
        xml_row([("KPI", "String", "Min Wert"), ("", "Number", min((r.value for r in rows), default=0))]),
        xml_row([("KPI", "String", "Erzeugt am (UTC)"), ("", "String", timestamp)]),
        "  </Table>",
        " </Worksheet>",
        ' <Worksheet ss:Name="Prompt">',
        "  <Table>",
        xml_row([("PurpleHeader", "String", "Original-Prompt")]),
        xml_row([("", "String", source_prompt)]),
        "  </Table>",
        " </Worksheet>",
        "</Workbook>",
    ])

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Erzeugt aus einem Rechen-Prompt eine .xls-Datei im Power-Layout."
    )
    parser.add_argument("--prompt", help="Prompt-Text mit Zuweisungen/Formeln")
    parser.add_argument("--prompt-file", help="Datei mit Prompt-Text")
    parser.add_argument("--out", default="power_rechner.xls", help="Ziel-Datei (.xls)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.prompt and not args.prompt_file:
        raise SystemExit("Bitte --prompt oder --prompt-file angeben.")

    prompt_text = args.prompt or Path(args.prompt_file).read_text(encoding="utf-8")
    assignments = parse_prompt(prompt_text)

    if not assignments:
        raise SystemExit(
            "Keine Formeln erkannt. Beispiel: preis=100; mwst=0.19; brutto=preis*(1+mwst)"
        )

    try:
        rows = build_rows(assignments)
    except Exception as exc:
        raise SystemExit(f"Fehler beim Bauen des PowerRechners: {exc}") from exc

    xml_content = to_spreadsheet_xml(rows, prompt_text)
    output = Path(args.out)
    output.write_text(xml_content, encoding="utf-8")
    print(f"Fertig: {output} ({len(rows)} Berechnungen, Purple-Cow-Layout aktiv)")


if __name__ == "__main__":
    main()
