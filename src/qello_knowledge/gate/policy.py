"""게이트 정책 `qk-sto-002-gate-policy/v1` 읽기·검증(QK-STO-002 contracts/gate-policy.md, research R-09).

값은 사람이 정한다. 이 모듈은 형식만 검사한다. 수치는 소수 문자열을 `Fraction`으로 읽는다.
"""

from __future__ import annotations

import hashlib
import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

from qello_knowledge.domain.retrieval import RetrievalSettings

SCHEMA = "qk-sto-002-gate-policy/v1"
POLICY_ROOT = "eval/gate_policies"
MODES = ("vector", "keyword", "hybrid")
METRICS = ("recall_at_5", "mrr")
GUARDRAILS = ("G1", "G2", "G3")
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
_NUMBER = re.compile(r"^\d+(\.\d+)?$")
_FILE = re.compile(r"^v([1-9]\d*)\.toml$")
_TOP_KEYS = {"schema", "id", "version", "mode", "tokenizers", "search", "sets", "guardrails"}
_SET_KEYS = {"id", "version", "fingerprint", "min_judged", "max_drop"}
_GUARD_KEYS = {"kind", "set", "mode", "limit"}


@dataclass(frozen=True)
class SetRule:
    id: str
    version: int
    fingerprint: str
    min_judged: int
    max_drop: Mapping[str, Fraction]


@dataclass(frozen=True)
class Guardrail:
    kind: str
    set: str
    mode: str
    limit: Fraction


@dataclass(frozen=True)
class GatePolicy:
    id: str
    version: int
    mode: str
    sets: tuple[SetRule, ...]
    guardrails: tuple[Guardrail, ...]
    baseline_tokenizer: str
    candidate_tokenizer: str
    search: Mapping[str, Any]
    path: str  # 저장소 상대 경로
    sha256: str
    extra: Mapping[str, Any] = field(default_factory=dict)


def file_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_number(value: Any) -> Fraction | None:
    if not isinstance(value, str) or not _NUMBER.fullmatch(value):
        return None
    return Fraction(value)


def _int(value: Any, minimum: int = 1) -> int | None:
    return value if type(value) is int and value >= minimum else None


def load_policy(path: Path, *, repo_path: str | None = None) -> tuple[GatePolicy | None, tuple[str, ...]]:
    """`(정책, 오류 이름들)`. 오류가 하나라도 있으면 정책은 `None`이다. `repo_path`는 저장소 상대 경로다."""
    try:
        raw = path.read_bytes()
        data = tomllib.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return None, ("policy_toml_invalid",)
    return parse_policy(data, raw=raw, repo_path=repo_path or path.as_posix())


def parse_policy(data: Mapping[str, Any], *, raw: bytes, repo_path: str) -> tuple[GatePolicy | None, tuple[str, ...]]:
    issues: list[str] = []

    def issue(name: str) -> None:
        if name not in issues:
            issues.append(name)

    if set(data) - _TOP_KEYS:
        issue("policy_unknown_key")
    if data.get("schema") != SCHEMA:
        issue("policy_schema")
    policy_id = data.get("id")
    if not isinstance(policy_id, str) or not _ID.fullmatch(policy_id):
        issue("policy_id")
    version = _int(data.get("version"))
    if version is None:
        issue("policy_version")
    parts = Path(repo_path).parts
    match = _FILE.fullmatch(parts[-1]) if parts else None
    if match is None or version is None or int(match.group(1)) != version:
        issue("policy_path_version")
    if len(parts) < 2 or parts[-2] != policy_id:
        issue("policy_id")
    mode = data.get("mode", "hybrid")
    if mode not in MODES:
        issue("policy_mode")

    tokenizers = data.get("tokenizers")
    baseline_tok = candidate_tok = None
    if not isinstance(tokenizers, Mapping) or set(tokenizers) != {"baseline", "candidate"}:
        issue("policy_tokenizer")
    else:
        baseline_tok, candidate_tok = tokenizers.get("baseline"), tokenizers.get("candidate")
        if not all(isinstance(t, str) and t.strip() for t in (baseline_tok, candidate_tok)):
            issue("policy_tokenizer")

    defaults = RetrievalSettings()
    search_raw = data.get("search", {})
    search = {"query_rule": defaults.query_rule, "candidates": defaults.candidates, "rrf_k": defaults.rrf_k}
    if not isinstance(search_raw, Mapping) or set(search_raw) - set(search):
        issue("policy_search")
    else:
        search.update(search_raw)
        numbers = (_int(search["candidates"]), _int(search["rrf_k"]))
        if not isinstance(search["query_rule"], str) or None in numbers:
            issue("policy_search")

    sets: list[SetRule] = []
    raw_sets = data.get("sets")
    if not isinstance(raw_sets, list) or not raw_sets:
        issue("policy_no_sets")
        raw_sets = []
    for entry in raw_sets:
        if not isinstance(entry, Mapping) or set(entry) - _SET_KEYS:
            issue("policy_unknown_key")
            continue
        sid, sversion, fp = entry.get("id"), _int(entry.get("version")), entry.get("fingerprint")
        if not isinstance(sid, str) or not sid or sversion is None or not isinstance(fp, str) or not fp:
            issue("policy_schema")
            continue
        min_judged = _int(entry.get("min_judged"))
        if min_judged is None:
            issue("policy_min_judged")
            continue
        drops = entry.get("max_drop")
        if not isinstance(drops, Mapping) or set(drops) != set(METRICS):
            issue("policy_number")
            continue
        parsed = {name: parse_number(drops[name]) for name in METRICS}
        if any(v is None for v in parsed.values()):
            issue("policy_number")
            continue
        if any(s.id == sid for s in sets):
            issue("policy_set_duplicate")
            continue
        sets.append(SetRule(sid, sversion, fp, min_judged, parsed))

    guardrails: list[Guardrail] = []
    raw_guards = data.get("guardrails", [])
    if not isinstance(raw_guards, list):
        issue("policy_guardrail_kind")
        raw_guards = []
    for entry in raw_guards:
        if not isinstance(entry, Mapping) or set(entry) - _GUARD_KEYS:
            issue("policy_unknown_key")
            continue
        kind = entry.get("kind")
        if kind not in GUARDRAILS:
            issue("policy_guardrail_kind")
            continue
        target_set = entry.get("set")
        if not any(s.id == target_set for s in sets):
            issue("policy_guardrail_set")
            continue
        default_mode = {"G1": mode, "G2": "keyword", "G3": "keyword"}[kind]
        guard_mode = entry.get("mode", default_mode)
        if (
            guard_mode not in MODES
            or (kind == "G1" and guard_mode != mode)
            or (kind == "G3" and guard_mode != "keyword")
        ):
            issue("policy_guardrail_mode")
            continue
        limit = parse_number(entry.get("limit"))
        if limit is None:
            issue("policy_number")
            continue
        guardrails.append(Guardrail(kind, target_set, guard_mode, limit))

    if issues:
        return None, tuple(issues)
    return (
        GatePolicy(
            id=policy_id,
            version=version,
            mode=mode,
            sets=tuple(sets),
            guardrails=tuple(guardrails),
            baseline_tokenizer=baseline_tok,
            candidate_tokenizer=candidate_tok,
            search=search,
            path=repo_path,
            sha256=file_sha256(raw),
        ),
        (),
    )
