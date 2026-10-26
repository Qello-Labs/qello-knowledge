"""QK-CHK-001 plan 측정(research R-01~R-04, R-09, R-12, R-14).

대상 저장소 로컬 사본의 한 커밋을 읽어 집계만 출력한다. 원문, 경로, 심볼 이름은 출력하지 않는다.
청크 나누기는 spec FR-010·013·020·021을 거칠게 흉내 낸 것이다.
상한 초과 나누기와 맥락 줄 생략(FR-017·018)은 하지 않고 크기만 센다.

실행(저장소 루트):
    uv run --with tree-sitter==0.26.0 --with tree-sitter-java==0.23.5 --with tree-sitter-kotlin==1.1.0 \
        --with tokenizers==0.23.3 python specs/QK-CHK-001-code-chunker/measurement/measure_code.py \
        --repo <대상 저장소 로컬 사본> --commit <커밋> [--tokenizer <bge-m3 tokenizer.json>]

`--tokenizer`를 빼면 실제 토큰 비교는 건너뛴다. 분위수는 정렬한 값의 `index = min(n - 1, floor(n * q))` 원소다.
"""

import argparse
import hashlib
import json
import math
import re
import subprocess
import time
from collections import Counter
from pathlib import Path, PurePosixPath

import tree_sitter_java
import tree_sitter_kotlin
from tree_sitter import Language, Parser

from qello_knowledge.domain.exclusions import excluded_by
from qello_knowledge.domain.secret_rules import find_secrets

BYTES_PER_TOKEN = 3.5  # embedding/estimate.py estimated_tokens
NEURON_BYTES_PER_TOKEN = 1.4  # domain/embedding.py neuron_bytes_per_token
NEURONS_PER_M_TOKENS = 1075
TARGET = 512
COMPACT = False
MERGE_HEAD = False
SKIP_TRIVIAL_SUMMARY = False
PARSE_COPY = True
LIMITS = (1200, 1500, 1800, 2000)
SUSPEND_LAMBDA = re.compile(rb"\bsuspend(?=\s*\{)")
TEST_DIRS = ("src/test/", "src/integrationTest/", "src/androidTest/", "src/testFixtures/")
TEST_ANNOTATIONS = {"Test", "ParameterizedTest", "RepeatedTest", "TestFactory", "TestTemplate"}
ANDROID_BASES = {
    "Activity": "Activity", "AppCompatActivity": "Activity", "ComponentActivity": "Activity",
    "FragmentActivity": "Activity",
    "Fragment": "Fragment", "DialogFragment": "Fragment", "BottomSheetDialogFragment": "Fragment",
    "ViewModel": "ViewModel", "AndroidViewModel": "ViewModel", "Service": "Service",
    "BroadcastReceiver": "BroadcastReceiver", "ContentProvider": "ContentProvider", "Application": "Application",
}  # fmt: skip
COMPONENT_KINDS = (
    "Activity",
    "Fragment",
    "ViewModel",
    "Service",
    "BroadcastReceiver",
    "ContentProvider",
    "Application",
)

JAVA = {
    "types": {"class_declaration", "interface_declaration", "enum_declaration", "record_declaration",
              "annotation_type_declaration"},
    "bodies": {"class_body", "interface_body", "enum_body", "annotation_type_body", "enum_body_declarations"},
    "methods": {"method_declaration", "constructor_declaration", "compact_constructor_declaration",
                "annotation_type_element_declaration"},
    "inits": {"static_initializer", "block"},
    "fields": {"field_declaration", "constant_declaration"},
    "comments": {"line_comment", "block_comment"},
    "head_items": {"enum_constant"},
}  # fmt: skip
KOTLIN = {
    "types": {"class_declaration", "object_declaration", "companion_object"},
    "bodies": {"class_body", "enum_class_body"},
    "methods": {"function_declaration", "secondary_constructor"},
    "inits": {"anonymous_initializer"},
    "fields": {"property_declaration"},
    "comments": {"line_comment", "block_comment"},
    "head_items": {"enum_entry"},
}  # fmt: skip


def est(text: str) -> int:
    return math.ceil(len(text.encode("utf-8")) / BYTES_PER_TOKEN)


def quantile(values, q):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.floor(len(ordered) * q))] if ordered else None


def dist(values):
    return {"n": len(values), "p50": quantile(values, 0.5), "p90": quantile(values, 0.9),
            "p99": quantile(values, 0.99), "max": max(values) if values else None}  # fmt: skip


def node_text(node, src: bytes) -> str:
    return src[node.start_byte : node.end_byte].decode("utf-8", "replace")


def body_of(node, spec):
    return next((c for c in node.children if c.type in spec["bodies"]), None)


def name_of(node, src):
    for c in node.children:
        if c.type in ("identifier", "type_identifier", "simple_identifier"):
            return node_text(c, src)
    return "Companion" if node.type == "companion_object" else ""


def annotations(node, src):
    names = []
    for c in node.children:
        if c.type in ("modifiers",):
            for a in c.children:
                if a.type in ("annotation", "marker_annotation"):
                    text = node_text(a, src).lstrip("@")
                    names.append(re.split(r"[(\s]", text, maxsplit=1)[0].rsplit(".", 1)[-1])
    return names


def signature_end(node, src):
    """본문을 여는 줄. 본문이 없으면 선언 끝 줄."""
    for c in node.children:
        if c.type in ("block", "constructor_body", "function_body", "class_body", "interface_body", "enum_body",
                      "annotation_type_body", "enum_class_body"):  # fmt: skip
            return c.start_point[0]
    return node.end_point[0]


def supertypes(node, src, lang):
    if lang == "java":
        sup = next((c for c in node.children if c.type == "superclass"), None)
        return (
            [re.sub(r"<.*", "", node_text(sup, src).replace("extends", "").strip()).rsplit(".", 1)[-1]] if sup else []
        )
    out = []
    for c in node.children:
        if c.type == "delegation_specifiers":
            for d in c.children:
                if d.type == "delegation_specifier" and any(x.type == "constructor_invocation" for x in d.children):
                    out.append(re.split(r"[<(]", node_text(d, src), maxsplit=1)[0].strip().rsplit(".", 1)[-1])
    return out


def component(names, has_android):
    if not has_android:
        return None
    for n in names:
        if n in ANDROID_BASES:
            return ANDROID_BASES[n]
        for kind in COMPONENT_KINDS:
            if n.endswith(kind):
                return kind
    return None


class FileStats:
    def __init__(self, path, lang, src, lines, package, has_android, is_test):
        self.path, self.lang, self.src, self.lines = path, lang, src, lines
        self.package, self.has_android, self.is_test = package, has_android, is_test
        self.chunks = []  # (kind, body, header, context)

    def header(self, symbols, kind):
        if COMPACT:  # 패키지가 경로에 이미 들어 있으면 뺀다(research R-09 후보)
            package = "" if f"/{self.package.replace('.', '/')}/" in f"/{self.path}" else f" {self.package}"
            return f"{self.path} {self.lang}{package}\n{' > '.join(symbols)} [{kind}]\n"
        return f"{self.path}\n{self.lang} {self.package}\n{' > '.join(symbols)} [{kind}]\n"

    def add(self, kind, start, end, symbols, context, body=None):
        text = body if body is not None else "\n".join(self.lines[start : end + 1])
        if text.strip():
            self.chunks.append((kind, text, self.header(symbols, kind), "\n".join(context)))


def walk_type(fs, node, spec, symbols, context, counters):
    src, lines = fs.src, fs.lines
    name = name_of(node, src)
    syms = [*symbols, name]
    decl_lines = lines[node.start_point[0] : signature_end(node, src) + 1]
    comp = component(supertypes(node, src, fs.lang), fs.has_android)
    if comp:
        counters["component"][comp] += 1
    elif any(s.endswith(k) for s in supertypes(node, src, fs.lang) for k in COMPONENT_KINDS):
        counters["component_missed_no_android_import"] += 1
    body = body_of(node, spec)
    members = []
    if body is not None:
        pending = []
        for child in body.children:
            if child.type in spec["comments"]:
                pending.append(child)
                continue
            if child.type in spec["bodies"]:  # enum_body_declarations
                members.extend((pending, c) for c in child.children if c.is_named)
                pending = []
                continue
            if child.is_named:
                members.append((pending, child))
            pending = []
    member_nodes = [(p, m) for p, m in members if m.type not in spec["head_items"] and m.type not in spec["comments"]]
    first = (
        member_nodes[0][0][0] if member_nodes and member_nodes[0][0] else (member_nodes[0][1] if member_nodes else None)
    )
    head_end = (first.start_point[0] - 1) if first else node.end_point[0]
    head_tokens = est("\n".join(lines[node.start_point[0] : head_end + 1]))
    head_merged = bool(
        MERGE_HEAD and member_nodes and member_nodes[0][1].type in spec["fields"] and head_tokens < TARGET
    )
    if not head_merged:  # 후보: 머리가 바로 필드 묶음으로 이어지면 한 청크로 합친다(research R-04)
        fs.add("type_head", node.start_point[0], head_end, syms, context)
    summary = list(decl_lines)
    field_group, field_start = [], (node.start_point[0] if head_merged else None)
    merged_open = head_merged  # 형식 머리와 합칠 첫 묶음이 아직 열려 있다(research R-05)
    has_body_member = False
    inner_context = [*context, *decl_lines]

    def flush():
        nonlocal field_group, field_start, merged_open
        if field_group:
            merged = merged_open  # 형식 머리와 합친 첫 묶음(spec FR-010): 종류는 형식 머리, 맥락은 바깥만
            merged_open = False
            fs.add(
                "type_head" if merged else "fields",
                field_start,
                field_group[-1].end_point[0],
                syms if merged else [*syms, name_of(field_group[0], src)],
                context if merged else inner_context,
            )
        field_group, field_start = [], None

    for pending, m in member_nodes:
        start = pending[0].start_point[0] if pending else m.start_point[0]
        if m.type in spec["types"]:
            flush()
            has_body_member = True  # 중첩 형식도 본문 있는 멤버로 센다(spec FR-013, 2026-10-26 사용자 결정 M1)
            summary.append(lines[m.start_point[0]])
            walk_type(fs, m, spec, syms, inner_context, counters)
            continue
        if m.type in spec["fields"]:
            summary.extend(lines[m.start_point[0] : m.end_point[0] + 1][:1])
            size = sum(est("\n".join(lines[f.start_point[0] : f.end_point[0] + 1])) for f in field_group)
            size += head_tokens if merged_open else 0  # 합칠 첫 묶음은 머리 줄도 센다(research R-05)
            if field_group and size > TARGET:
                flush()
            if not field_group and field_start is None:
                field_start = start
            field_group.append(m)
            continue
        flush()
        has_body_member = has_body_member or signature_end(m, src) < m.end_point[0]
        kind = "method" if m.type in spec["methods"] else ("init" if m.type in spec["inits"] else "other")
        summary.extend(lines[m.start_point[0] : signature_end(m, src) + 1])
        anns = annotations(m, src)
        if fs.is_test and TEST_ANNOTATIONS & set(anns):
            counters["test_methods"] += 1
            counters["test_display_name"] += "DisplayName" in anns
            counters["test_backtick_name"] += "`" in (name_of(m, src) or node_text(m, src).split("(")[0])
        if kind == "method" and any(a == "Composable" for a in anns):
            counters["component"]["Composable"] += 1
        fs.add(kind, start, m.end_point[0], [*syms, name_of(m, src)], inner_context)
        counters["methods_by_name"][(fs.path, tuple(syms), name_of(m, src))] += 1
    flush()
    if not (SKIP_TRIVIAL_SUMMARY and not has_body_member):  # 후보: 본문 있는 멤버가 없으면 요약 생략(research R-04)
        fs.add("summary", 0, 0, syms, context, body="\n".join(summary))


def analyse(path, text, parsers, counters):
    lang = "java" if path.endswith(".java") else "kotlin"
    spec = JAVA if lang == "java" else KOTLIN
    src = text.encode("utf-8")
    parse_src = src
    if (
        lang == "kotlin" and PARSE_COPY
    ):  # 해석용 같은 길이 사본(research R-01). 위치는 그대로이고 청크 본문은 원문에서 자른다
        parse_src = SUSPEND_LAMBDA.sub(b"run    ", src)
        counters["kotlin_parse_copy_files"] += parse_src != src
    tree = parsers[lang].parse(parse_src)
    lines = text.split("\n")
    package = next((ln.split()[1].rstrip(";") for ln in lines if ln.startswith("package ")), "")
    has_android = any(re.match(r"import\s+(android|androidx)\.", ln) for ln in lines)
    is_test = any(d in f"/{path}" for d in (f"/{t}" for t in TEST_DIRS))
    fs = FileStats(path, lang, src, lines, package, has_android, is_test)
    root = tree.root_node
    if root.has_error:
        counters["parse_error_files"][f"{lang}-{'test' if is_test else 'main'}"] += 1
        fs.add("fallback", 0, len(lines) - 1, [], [])
        return fs
    decls = [
        c for c in root.children if c.type in spec["types"] or c.type in spec["methods"] or c.type in spec["fields"]
    ]
    head_end = decls[0].start_point[0] - 1 if decls else len(lines) - 1
    fs.add("file_head", 0, head_end, [], [])
    top_funcs = []
    for c in decls:
        if c.type in spec["types"]:
            walk_type(fs, c, spec, [], [], counters)
        else:
            top_funcs.append(c)
            if c.type in spec["methods"] and "Composable" in annotations(c, src):
                counters["component"]["Composable"] += 1
            fs.add("top_function" if c.type in spec["methods"] else "top_properties", c.start_point[0], c.end_point[0],
                   [PurePosixPath(path).name, name_of(c, src)], [])  # fmt: skip
    has_body = any(c.type in spec["methods"] and signature_end(c, src) < c.end_point[0] for c in top_funcs)
    if top_funcs and (has_body or not SKIP_TRIVIAL_SUMMARY):  # 파일 요약에도 생략 규칙(spec FR-014, M1)
        sig = [ln for c in top_funcs for ln in lines[c.start_point[0] : signature_end(c, src) + 1]]
        fs.add("file_summary", 0, 0, [PurePosixPath(path).name], [], body="\n".join(sig))
    return fs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--commit", required=True)
    ap.add_argument("--tokenizer")
    ap.add_argument("--compact-header", action="store_true")
    ap.add_argument("--merge-small-heads", action="store_true")
    ap.add_argument("--skip-trivial-summary", action="store_true")
    ap.add_argument("--no-parse-copy", action="store_true")
    args = ap.parse_args()
    global COMPACT, MERGE_HEAD, SKIP_TRIVIAL_SUMMARY, PARSE_COPY
    COMPACT, MERGE_HEAD, SKIP_TRIVIAL_SUMMARY = args.compact_header, args.merge_small_heads, args.skip_trivial_summary
    PARSE_COPY = not args.no_parse_copy
    git = ["git", "-C", args.repo]
    files = subprocess.run(  # noqa: S603
        [*git, "ls-tree", "-r", "--name-only", args.commit], check=True, capture_output=True, text=True
    )
    paths = [p for p in files.stdout.splitlines() if p.endswith((".java", ".kt"))]
    parsers = {
        "java": Parser(Language(tree_sitter_java.language())),
        "kotlin": Parser(Language(tree_sitter_kotlin.language())),
    }
    tokenizer = None
    if args.tokenizer:
        from tokenizers import Tokenizer

        tokenizer = Tokenizer.from_file(args.tokenizer)
    counters = {"parse_error_files": Counter(), "component": Counter(), "component_missed_no_android_import": 0,
                "test_methods": 0, "test_display_name": 0, "test_backtick_name": 0, "methods_by_name": Counter(),
                "kotlin_parse_copy_files": 0}  # fmt: skip
    variant = [
        k for k in ("compact_header", "merge_small_heads", "skip_trivial_summary", "no_parse_copy") if getattr(args, k)
    ]
    # 줄 바꿈 변환(core.autocrlf)과 관계없이 같은 값이 나오게 LF로 바꾼 뒤 해시한다
    script_sha = hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:12]
    out = {"commit": args.commit, "script_sha256_12": script_sha, "variant": variant, "files": Counter(),
           "bytes": Counter(), "default_excluded": 0, "secret_blocked_files": Counter(),
           "secret_rules": Counter()}  # fmt: skip
    all_files, parse_seconds = [], 0.0
    for path in paths:
        is_test = any(f"/{d}" in f"/{path}" for d in TEST_DIRS)
        group = f"{'java' if path.endswith('.java') else 'kotlin'}-{'test' if is_test else 'main'}"
        if excluded_by(path) is not None:
            out["default_excluded"] += 1
            continue
        text = subprocess.run([*git, "show", f"{args.commit}:{path}"], check=True, capture_output=True).stdout  # noqa: S603
        text = text.decode("utf-8").replace("\r\n", "\n").removeprefix("﻿")
        out["files"][group] += 1
        out["bytes"][group] += len(text.encode("utf-8"))
        hits = find_secrets(text)
        if hits:
            out["secret_blocked_files"][group] += 1
            out["secret_rules"].update({h.rule for h in hits})
            continue
        started = time.perf_counter()
        fs = analyse(path, text, parsers, counters)
        parse_seconds += time.perf_counter() - started
        all_files.append((group, fs))
    sizes, bodies, kinds, small = [], [], Counter(), Counter()
    emb_bytes, src_bytes, hdr_bytes, ctx_bytes = Counter(), Counter(), Counter(), Counter()
    over = Counter()
    ratios, real_total, est_total = [], 0, 0
    long_line_files = Counter()
    for group, fs in all_files:
        max_line = max((len(ln.encode("utf-8")) for ln in fs.lines), default=0)
        for limit in LIMITS:
            if math.ceil((max_line + 200) / BYTES_PER_TOKEN) > limit:
                long_line_files[limit] += 1
        for kind, body, header, context in fs.chunks:
            emb = header + (context + "\n" if context else "") + body
            tokens = est(emb)
            sizes.append(tokens)
            bodies.append(est(body))
            kinds[kind] += 1
            if est(body) < 32:
                small[kind] += 1
            for limit in LIMITS:
                over[limit] += tokens > limit
            b = len(emb.encode("utf-8"))
            emb_bytes[group] += b
            src_bytes[group] += len(body.encode("utf-8"))
            hdr_bytes[group] += len(header.encode("utf-8"))
            ctx_bytes[group] += len(context.encode("utf-8"))
            if tokenizer is not None:
                real = len(tokenizer.encode(emb).ids)
                ratios.append(real / tokens)
                real_total += real
                est_total += tokens
    neurons = {g: round(b / NEURON_BYTES_PER_TOKEN * NEURONS_PER_M_TOKENS / 1_000_000) for g, b in emb_bytes.items()}
    overloads = sum(1 for n in counters["methods_by_name"].values() if n > 1)
    out.update(
        {
            "parse_error_files": counters["parse_error_files"],
            "kotlin_parse_copy_files": counters["kotlin_parse_copy_files"],
            "parse_seconds": round(parse_seconds, 2),
            "chunks_by_kind": kinds,
            "chunks_total": sum(kinds.values()),
            "small_body_lt32_by_kind": small,
            "embedding_tokens_estimated": dist(sizes),
            "body_tokens_estimated": dist(bodies),
            "chunks_over_limit_before_split": {str(k): v for k, v in over.items()},
            "files_with_line_plus_header_over_limit": {str(k): v for k, v in long_line_files.items()},
            "embedding_bytes": emb_bytes,
            "source_bytes_in_chunks": src_bytes,
            "header_bytes": hdr_bytes,
            "context_bytes": ctx_bytes,
            "neurons_estimate": neurons,
            "android_components": counters["component"],
            "component_candidates_without_android_import": counters["component_missed_no_android_import"],
            "test_methods": counters["test_methods"],
            "test_with_display_name": counters["test_display_name"],
            "test_backtick_name": counters["test_backtick_name"],
            "same_name_member_groups": overloads,
        }
    )
    if tokenizer is not None:
        out["real_over_estimated_tokens"] = {
            "p50": round(quantile(ratios, 0.5), 3),
            "p99": round(quantile(ratios, 0.99), 3),
            "max": round(max(ratios), 3),
            "total": round(real_total / est_total, 3),
        }
    print(json.dumps(out, ensure_ascii=False, indent=1, default=lambda o: dict(o)))


if __name__ == "__main__":
    main()
