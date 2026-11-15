"""tests/unit/test_architecture.py

AST-based architectural boundary tests (Foundation Lock 2: Layering).
Enforces:
1. app/agents contains ZERO SQL keywords in string literals (SELECT, INSERT, UPDATE, DELETE).
2. app/agents imports NOTHING from app.data, psycopg2, or sqlalchemy.
3. AnswerWriterAgent has strictly ZERO tools (tools = []).
"""

import ast
from pathlib import Path
import pytest
from app.agents.answer_writer import AnswerWriterAgent

AGENTS_DIR = Path(__file__).resolve().parent.parent.parent / "app" / "agents"
FORBIDDEN_IMPORTS = ["app.data", "psycopg", "psycopg2", "sqlalchemy"]
SQL_PATTERNS = ["SELECT ", "INSERT INTO ", "UPDATE ", "DELETE FROM ", "DROP TABLE", "CREATE TABLE"]


def test_answer_writer_has_zero_tools():
    """Foundation Lock 2: AnswerWriterAgent must have strictly zero tools."""
    agent = AnswerWriterAgent()
    assert len(agent.tools) == 0, f"AnswerWriterAgent must have 0 tools, found {len(agent.tools)}"


def test_agents_no_forbidden_imports():
    """Foundation Lock 2: app/agents must never import database drivers or DAL modules."""
    py_files = list(AGENTS_DIR.glob("*.py"))
    assert len(py_files) >= 4, f"Expected at least 4 agent files in {AGENTS_DIR}"

    violations = []
    for f in py_files:
        tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for forbidden in FORBIDDEN_IMPORTS:
                        if alias.name.startswith(forbidden):
                            violations.append(f"{f.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for forbidden in FORBIDDEN_IMPORTS:
                        if node.module.startswith(forbidden):
                            violations.append(f"{f.name}: from {node.module} import ...")

    assert not violations, f"Architectural boundary violations found in app/agents:\n" + "\n".join(violations)


def test_agents_no_sql_string_literals():
    """Foundation Lock 2: app/agents must contain zero SQL keywords in string literals."""
    py_files = list(AGENTS_DIR.glob("*.py"))
    violations = []

    for f in py_files:
        tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                val_upper = node.value.upper()
                for sql_kw in SQL_PATTERNS:
                    if sql_kw in val_upper:
                        violations.append(f"{f.name} line {node.lineno}: string contains '{sql_kw}'")

    assert not violations, f"SQL string literals detected inside app/agents:\n" + "\n".join(violations)

