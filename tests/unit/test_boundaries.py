"""경계 규칙: `domain`과 `ports`는 표준 라이브러리와 서로만 가져온다(C-06, FR-002)."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "qello_knowledge"
RESTRICTED = ("domain", "ports")
ALLOWED_INTERNAL = ("qello_knowledge.domain", "qello_knowledge.ports")


def _imported_modules(tree: ast.AST) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [(node.lineno, alias.name) for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.append((node.lineno, node.module))
    return found


def _allowed(module: str) -> bool:
    top = module.split(".")[0]
    if top in sys.stdlib_module_names or top == "__future__":
        return True
    return any(module == prefix or module.startswith(prefix + ".") for prefix in ALLOWED_INTERNAL)


def violations(root: Path) -> list[str]:
    problems = []
    for part in RESTRICTED:
        for path in sorted((root / part).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for line, module in _imported_modules(tree):
                if not _allowed(module):
                    problems.append(f"{path.relative_to(root.parent)}:{line}: {module}")
    return problems


def test_domain_and_ports_import_only_stdlib_and_each_other() -> None:
    assert violations(PACKAGE) == []


def test_violation_is_detected(tmp_path: Path) -> None:
    root = tmp_path / "qello_knowledge"
    for part in RESTRICTED:
        (root / part).mkdir(parents=True)
    (root / "domain" / "bad.py").write_text("import json\nfrom psycopg import Connection\n", encoding="utf-8")
    (root / "ports" / "bad.py").write_text("from qello_knowledge.adapters import x\n", encoding="utf-8")
    assert violations(root) == [
        "qello_knowledge/domain/bad.py:2: psycopg",
        "qello_knowledge/ports/bad.py:1: qello_knowledge.adapters",
    ]
