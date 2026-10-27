"""경계 규칙: `domain`·`ports`·`embedding`은 표준 라이브러리와 서로만 가져온다(C-06, FR-002).

`embedding`은 외부 제공자 모듈(`adapters`)을 모른다(QK-EMB-001 SC-007).
전송 직전 검사와 재시도 대기는 생성 인자로 받는다.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "qello_knowledge"
RESTRICTED = ("domain", "ports", "embedding")
ALLOWED_INTERNAL = ("qello_knowledge.domain", "qello_knowledge.ports", "qello_knowledge.embedding")


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
    (root / "embedding" / "bad.py").write_text(
        "from qello_knowledge.adapters.workers_ai.rest import WorkersAiRestProvider\n"
        "from qello_knowledge.security.send_gate import check_outgoing\n",
        encoding="utf-8",
    )
    assert violations(root) == [
        "qello_knowledge/domain/bad.py:2: psycopg",
        "qello_knowledge/ports/bad.py:1: qello_knowledge.adapters",
        "qello_knowledge/embedding/bad.py:1: qello_knowledge.adapters.workers_ai.rest",
        "qello_knowledge/embedding/bad.py:2: qello_knowledge.security.send_gate",
    ]


def test_chunking_dependencies_are_isolated():
    assert chunking_violations(PACKAGE) == []


def test_chunking_violations_are_detected(tmp_path):
    root = tmp_path / "qello_knowledge"
    for part in (*RESTRICTED, "query", "chunking"):
        (root / part).mkdir(parents=True, exist_ok=True)
    (root / "query" / "bad.py").write_text("from qello_knowledge import chunking\nimport markdown_it\n")
    (root / "chunking" / "bad.py").write_text("from markdown_it import MarkdownIt\n")
    (root / "chunking" / "blocks.py").write_text("import markdown_it\n")
    problems = chunking_violations(root)
    assert len(problems) == 3
    assert any("query/bad.py:1" in p for p in problems)
    assert any("query/bad.py:2" in p for p in problems)
    assert any("chunking/bad.py:1" in p for p in problems)


def chunking_violations(root: Path) -> list[str]:
    problems = []
    for path in sorted(root.rglob("*.py")):
        part = path.relative_to(root).parts[0]
        for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
            modules = _imported_modules(node) if isinstance(node, (ast.Import, ast.ImportFrom)) else []
            if isinstance(node, ast.ImportFrom) and node.module == "qello_knowledge":
                modules += [(node.lineno, "qello_knowledge." + alias.name) for alias in node.names]
            # Resolve relative imports too, so the check cannot be bypassed by spelling.
            if isinstance(node, ast.ImportFrom) and node.level:
                base = ["qello_knowledge", *path.relative_to(root).parts[:-1]]
                base = base[: len(base) - node.level + 1]
                module = ".".join([*base, *([node.module] if node.module else [])])
                modules += [(node.lineno, module + "." + a.name) for a in node.names]
            for line, module in modules:
                parser = module == "markdown_it" or module.startswith("markdown_it.")
                chunker = module == "qello_knowledge.chunking" or module.startswith("qello_knowledge.chunking.")
                if (part in (*RESTRICTED, "query") and (parser or chunker)) or (
                    parser and path.relative_to(root).as_posix() != "chunking/blocks.py"
                ):
                    problems.append(f"{path.relative_to(root.parent)}:{line}: {module}")
    return problems


def test_sync_dependencies_are_isolated():
    assert sync_violations(PACKAGE) == []


@pytest.mark.parametrize(
    "statement",
    [
        "import psycopg",
        "from markdown_it import MarkdownIt",
        "from qello_knowledge.adapters import github",
        "from qello_knowledge import adapters",
        "from ..adapters import github",
        "from .. import adapters",
        "import qello_knowledge.config",
    ],
)
def test_sync_violations_are_detected(tmp_path, statement):
    root = tmp_path / "qello_knowledge"
    (root / "sync").mkdir(parents=True)
    (root / "sync" / "bad.py").write_text(statement)
    assert len(sync_violations(root)) == 1


def test_sync_allowed_imports(tmp_path):
    root = tmp_path / "qello_knowledge"
    (root / "sync").mkdir(parents=True)
    (root / "sync" / "good.py").write_text(
        "import dataclasses\nfrom ..domain import sync\nfrom . import keys\n"
        "from qello_knowledge import sources\nfrom qello_knowledge.security import screen\n"
        "from qello_knowledge.chunking.service import chunk_screened\n"
    )
    assert sync_violations(root) == []


def sync_violations(root: Path) -> list[str]:
    prefixes = (
        *ALLOWED_INTERNAL,
        "qello_knowledge.sync",
        "qello_knowledge.chunking",
        "qello_knowledge.security",
        "qello_knowledge.sources",
    )
    problems = []
    for path in sorted((root / "sync").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = ["qello_knowledge", *path.relative_to(root).parts[:-1]]
                module = node.module or ""
                if node.level:
                    module = ".".join([*base[: len(base) - node.level + 1], *([module] if module else [])])
                modules = (
                    [module + "." + alias.name for alias in node.names] if module == "qello_knowledge" else [module]
                )
            for module in modules:
                if module.split(".")[0] in sys.stdlib_module_names or any(
                    module == prefix or module.startswith(prefix + ".") for prefix in prefixes
                ):
                    continue
                problems.append(f"{path.relative_to(root.parent)}:{node.lineno}: {module}")
    return problems


# QK-RET-001: `retrieval/`은 표준 라이브러리와 domain·ports·embedding·retrieval만 가져온다(contracts/retrieval.md 6절).
RETRIEVAL_ALLOWED = (*ALLOWED_INTERNAL, "qello_knowledge.retrieval")


def retrieval_violations(root: Path) -> list[str]:
    problems = []
    for path in sorted((root / "retrieval").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    problems.append(f"{path.relative_to(root.parent)}:{node.lineno}: 상대 경로 가져오기")
                    continue
                module = node.module or ""
                modules = (
                    [module + "." + alias.name for alias in node.names] if module == "qello_knowledge" else [module]
                )
            for module in modules:
                if module.split(".")[0] in sys.stdlib_module_names or module == "__future__":
                    continue
                if any(module == prefix or module.startswith(prefix + ".") for prefix in RETRIEVAL_ALLOWED):
                    continue
                problems.append(f"{path.relative_to(root.parent)}:{node.lineno}: {module}")
    return problems


def test_retrieval_dependencies_are_isolated():
    assert retrieval_violations(PACKAGE) == []


@pytest.mark.parametrize(
    "statement",
    [
        "import psycopg",
        "import markdown_it",
        "from qello_knowledge.adapters.postgres.store import PostgresStore",
        "from qello_knowledge import security",
        "from qello_knowledge.chunking import header",
        "from ..adapters import fake",
        "from . import fusion",
    ],
)
def test_retrieval_violations_are_detected(tmp_path, statement):
    root = tmp_path / "qello_knowledge"
    (root / "retrieval").mkdir(parents=True)
    (root / "retrieval" / "bad.py").write_text(statement)
    assert len(retrieval_violations(root)) == 1


def test_retrieval_allowed_imports(tmp_path):
    root = tmp_path / "qello_knowledge"
    (root / "retrieval").mkdir(parents=True)
    (root / "retrieval" / "good.py").write_text(
        "from __future__ import annotations\nimport fractions\nfrom qello_knowledge.domain.retrieval import X\n"
        "from qello_knowledge.ports.retrieval import RetrievalStore\nfrom qello_knowledge.embedding import estimate\n"
        "from qello_knowledge.retrieval.fusion import fuse\n"
    )
    assert retrieval_violations(root) == []


def test_domain_must_not_import_retrieval(tmp_path):
    root = tmp_path / "qello_knowledge"
    for part in RESTRICTED:
        (root / part).mkdir(parents=True)
    (root / "domain" / "bad.py").write_text("from qello_knowledge.retrieval import service\n")
    assert violations(root) == ["qello_knowledge/domain/bad.py:1: qello_knowledge.retrieval"]


# QK-GEN-001: `generation/`은 표준 라이브러리와 domain·ports·generation만 가져온다(contracts 6절, research R-13).
# RESTRICTED에는 넣지 않는다. 넣으면 `generation` 안의 서로 가져오기가 기존 검사에 걸린다.
GENERATION_ALLOWED = ("qello_knowledge.domain", "qello_knowledge.ports", "qello_knowledge.generation")


@pytest.mark.parametrize(
    ("part", "filename", "statement"),
    [
        ("discord", "bad.py", "from qello_knowledge.adapters import discord"),
        ("discord", "bad.py", "from qello_knowledge import security"),
        ("discord", "bad.py", "import qello_knowledge.retrieval"),
        ("discord", "bad.py", "import qello_knowledge.generation"),
        ("discord", "bad.py", "import psycopg"),
        ("discord", "bad.py", "import urllib.request"),
        ("discord", "render.py", "import cryptography"),
        ("discord", "bad.py", "from . import notices"),
        ("adapters/discord", "bad.py", "import qello_knowledge.discord"),
        ("adapters/discord", "bad.py", "from .. import http"),
    ],
)
def test_bot_discord_import_violations(tmp_path, part, filename, statement):
    root = tmp_path / "qello_knowledge"
    (root / part).mkdir(parents=True)
    (root / part / filename).write_text(statement)
    assert len(bot_discord_violations(root)) == 1


def test_bot_discord_import_allowances(tmp_path):
    root = tmp_path / "qello_knowledge"
    (root / "discord").mkdir(parents=True)
    (root / "adapters/discord").mkdir(parents=True)
    (root / "discord/signature.py").write_text(
        "from cryptography.exceptions import InvalidSignature\n"
        "from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey\n"
        "from qello_knowledge.domain import discord\nfrom qello_knowledge.discord import notices\n"
    )
    (root / "adapters/discord/webhook.py").write_text(
        "import urllib.request\nfrom qello_knowledge.domain.discord import RenderedReply\n"
    )
    assert bot_discord_violations(root) == []


def test_bot_discord_dependencies_are_isolated():
    assert bot_discord_violations(PACKAGE) == []


def bot_discord_violations(root: Path) -> list[str]:
    problems = []
    for part in ("discord", "adapters/discord"):
        prefixes = ("qello_knowledge.domain",)
        if part == "discord":
            prefixes += ("qello_knowledge.discord",)
        for path in sorted((root / part).rglob("*.py")):
            relative = path.relative_to(root).as_posix()
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                modules = []
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    if node.level:
                        problems.append(f"{relative}:{node.lineno}: 상대 경로 가져오기")
                        continue
                    module = node.module or ""
                    modules = [module + "." + a.name for a in node.names] if module == "qello_knowledge" else [module]
                for module in modules:
                    top = module.split(".")[0]
                    stdlib = top in sys.stdlib_module_names or top == "__future__"
                    if part == "discord" and top in {"urllib", "http", "socket", "httpx"}:
                        stdlib = False
                    backend = relative == "discord/signature.py" and module in {
                        "cryptography.exceptions",
                        "cryptography.hazmat.primitives.asymmetric.ed25519",
                    }
                    if stdlib or backend or any(module == p or module.startswith(p + ".") for p in prefixes):
                        continue
                    problems.append(f"{relative}:{node.lineno}: {module}")
    return problems


def generation_violations(root: Path) -> list[str]:
    problems = []
    for path in sorted((root / "generation").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=str(path))):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    problems.append(f"{path.relative_to(root.parent)}:{node.lineno}: 상대 경로 가져오기")
                    continue
                module = node.module or ""
                modules = (
                    [module + "." + alias.name for alias in node.names] if module == "qello_knowledge" else [module]
                )
            for module in modules:
                if module.split(".")[0] in sys.stdlib_module_names or module == "__future__":
                    continue
                if any(module == prefix or module.startswith(prefix + ".") for prefix in GENERATION_ALLOWED):
                    continue
                problems.append(f"{path.relative_to(root.parent)}:{node.lineno}: {module}")
    return problems


def test_generation_dependencies_are_isolated():
    assert generation_violations(PACKAGE) == []


@pytest.mark.parametrize(
    "statement",
    [
        "import psycopg",
        "from qello_knowledge.adapters.workers_ai.rest import API_BASE",
        "from qello_knowledge import security",
        "from qello_knowledge.retrieval import service",
        "from qello_knowledge.indexer import cli",
        "from qello_knowledge.embedding import estimate",
        "from ..adapters import fake",
        "from . import render",
    ],
)
def test_generation_violations_are_detected(tmp_path, statement):
    root = tmp_path / "qello_knowledge"
    (root / "generation").mkdir(parents=True)
    (root / "generation" / "bad.py").write_text(statement, encoding="utf-8")
    assert len(generation_violations(root)) == 1


def test_generation_allowed_imports(tmp_path):
    root = tmp_path / "qello_knowledge"
    (root / "generation").mkdir(parents=True)
    (root / "generation" / "good.py").write_text(
        "from __future__ import annotations\nimport re\nfrom qello_knowledge.domain.generation import X\n"
        "from qello_knowledge.ports.generator import GenerationProvider\n"
        "from qello_knowledge.ports.embedder import OutgoingCheck\n"
        "from qello_knowledge.generation.render import render\n",
        encoding="utf-8",
    )
    assert generation_violations(root) == []


@pytest.mark.parametrize("part", ["domain", "ports"])
def test_domain_and_ports_must_not_import_generation(tmp_path, part):
    root = tmp_path / "qello_knowledge"
    for name in RESTRICTED:
        (root / name).mkdir(parents=True)
    (root / part / "bad.py").write_text("from qello_knowledge.generation import service\n", encoding="utf-8")
    found = [problem.replace("\\", "/") for problem in violations(root)]  # Windows 경로 구분자도 같게 본다
    assert found == [f"qello_knowledge/{part}/bad.py:1: qello_knowledge.generation"]


# QK-CHK-001: 구문 해석기는 `chunking/code/parse.py`에서만 가져오고, 질의·도메인 쪽은 코드 청커를 모른다(research R-15).
CODE_PARSERS = ("tree_sitter", "tree_sitter_java", "tree_sitter_kotlin")
CODE_CHUNKER_FORBIDDEN = ("domain", "ports", "embedding", "query", "retrieval", "generation")


def code_chunker_violations(root: Path) -> list[str]:
    problems = []
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root).as_posix()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=str(path))):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level:
                    base = ["qello_knowledge", *relative.split("/")[:-1]]
                    module = ".".join([*base[: len(base) - node.level + 1], *([module] if module else [])])
                packages = ("qello_knowledge", "qello_knowledge.chunking")
                modules = [module + "." + a.name for a in node.names] if module in packages else [module]
            for module in modules:
                parser = module.split(".")[0] in CODE_PARSERS
                chunker = module == "qello_knowledge.chunking.code" or module.startswith(
                    "qello_knowledge.chunking.code."
                )
                if (parser and relative != "chunking/code/parse.py") or (
                    chunker and relative.split("/")[0] in CODE_CHUNKER_FORBIDDEN
                ):
                    problems.append(f"{relative}:{node.lineno}: {module}")
    return problems


def test_code_chunker_dependencies_are_isolated():
    assert code_chunker_violations(PACKAGE) == []


def test_code_chunker_violations_are_detected(tmp_path):
    root = tmp_path / "qello_knowledge"
    for part in ("query", "domain", "chunking/code"):
        (root / part).mkdir(parents=True)
    (root / "query" / "bad.py").write_text("from qello_knowledge.chunking import code\n", encoding="utf-8")
    (root / "domain" / "bad.py").write_text("from ..chunking.code.version import X\n", encoding="utf-8")
    (root / "chunking" / "code" / "units.py").write_text("import tree_sitter_java\n", encoding="utf-8")
    (root / "chunking" / "code" / "parse.py").write_text(
        "def load():\n    import tree_sitter\n    from tree_sitter_kotlin import language\n", encoding="utf-8"
    )
    assert code_chunker_violations(root) == [
        "chunking/code/units.py:1: tree_sitter_java",
        "domain/bad.py:1: qello_knowledge.chunking.code.version",
        "query/bad.py:1: qello_knowledge.chunking.code",
    ]
