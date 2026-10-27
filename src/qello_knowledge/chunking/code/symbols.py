"""심볼 이름·매개변수 형식·시그니처·어노테이션·형식 종류·컴포넌트·테스트 판정(research R-06).

모두 노드 원문에서 결정적으로 정한다. 다른 파일을 읽거나 이름을 해석하지 않는다(spec FR-003).
"""

import re
from dataclasses import dataclass

from qello_knowledge.chunking.code import version as rules

BODY_NODES = {
    "block",
    "constructor_body",
    "function_body",
    "class_body",
    "interface_body",
    "enum_body",
    "annotation_type_body",
    "enum_class_body",
}
ANNOTATION_NODES = {"annotation", "marker_annotation"}
RECEIVER_NODES = {"user_type", "nullable_type", "function_type", "parenthesized_type"}
DECLARATORS = ("variable_declarator", "variable_declaration", "multi_variable_declaration")
_STRING = re.compile(r'"((?:[^"\\\n]|\\.)*)"')
_ANDROID_IMPORT = re.compile(r"import\s+(?:static\s+)?androidx?\.")


def text(node, src: bytes) -> str:
    return src[node.start_byte : node.end_byte].decode("utf-8")


def _slice(src: bytes, start: int, end: int, removed=()) -> str:
    """`start`~`end` 원문에서 `removed` 노드들의 원문을 뺀다."""
    parts, cursor = [], start
    for skip in sorted(removed, key=lambda n: n.start_byte):
        if cursor <= skip.start_byte and skip.end_byte <= end:
            parts.append(src[cursor : skip.start_byte])
            cursor = skip.end_byte
    parts.append(src[cursor:end])
    return b"".join(parts).decode("utf-8")


def _descendants(node, types):
    found, stack = [], list(node.children)
    while stack:
        child = stack.pop()
        if child.type in types:
            found.append(child)
        else:
            stack.extend(child.children)
    return sorted(found, key=lambda n: n.start_byte)


def body_of(node):
    if node.type == "block":
        return node  # Java 인스턴스 초기화 블록은 노드 자체가 본문이다
    return next((c for c in node.children if c.type in BODY_NODES), None)


def signature_end(node) -> int:
    """시그니처 끝 줄(0부터): 본문을 여는 줄, 본문이 없으면 선언 끝 줄(spec FR-013)."""
    body = body_of(node)
    return body.start_point[0] if body is not None else node.end_point[0]


def _modifiers(node):
    return next((c for c in node.children if c.type == "modifiers"), None)


def declaration_annotations(node):
    modifiers = _modifiers(node)
    return [c for c in modifiers.children if c.type in ANNOTATION_NODES] if modifiers is not None else []


def annotation_name(node, src: bytes) -> str:
    value = text(node, src).lstrip("@").strip()
    value = re.sub(r"^\w+\s*:\s*", "", value)  # Kotlin 사용 위치 지정(`field:` 등)
    return re.split(r"[(<\s]", value, maxsplit=1)[0].rsplit(".", 1)[-1]


def annotations(node, src: bytes) -> list[str]:
    return [annotation_name(a, src) for a in declaration_annotations(node)]


def display_name(node, src: bytes) -> str:
    """`@DisplayName` 값. 없으면 Kotlin 백틱 이름, 그것도 없으면 빈 값(spec FR-025)."""
    for annotation in declaration_annotations(node):
        if annotation_name(annotation, src) == "DisplayName":
            found = _STRING.search(text(annotation, src))
            if found:
                return found.group(1)
    name = node.child_by_field_name("name")
    raw = text(name, src) if name is not None else ""
    return raw.strip("`") if raw.startswith("`") else ""


def type_name(node, src: bytes) -> str:
    name = node.child_by_field_name("name")
    if name is None:
        name = next((c for c in node.children if c.type in ("identifier", "type_identifier")), None)
    if name is None:
        return "Companion" if node.type == "companion_object" else ""
    return text(name, src).strip("`")


def type_kind(node, src: bytes) -> str:
    fixed = {
        "interface_declaration": "interface",
        "enum_declaration": "enum",
        "record_declaration": "record",
        "annotation_type_declaration": "annotation",
        "object_declaration": "object",
        "companion_object": "object",
    }
    if node.type in fixed:
        return fixed[node.type]
    if any(c.type == "interface" for c in node.children):
        return "interface"
    words = set(type_modifiers(node, src))
    return "enum" if "enum" in words else "annotation" if "annotation" in words else "class"


def type_modifiers(node, src: bytes) -> list[str]:
    modifiers = _modifiers(node)
    if modifiers is None:
        return []
    return [text(c, src) for c in modifiers.children if c.type not in ANNOTATION_NODES]


def _clean_type(node, src: bytes) -> str:
    removed = _descendants(node, ANNOTATION_NODES | {"type_modifiers"})
    return re.sub(r"\s+", "", _slice(src, node.start_byte, node.end_byte, removed))


def parameter_types(params, src: bytes) -> list[str]:
    """매개변수 형식 목록(spec FR-020). 어노테이션·이름·기본값·수식어를 빼고 공백을 없앤다."""
    if params is None:
        return []
    types, vararg = [], False
    for child in params.children:
        if child.type == "formal_parameter":
            types.append(_clean_type(child.child_by_field_name("type"), src))
        elif child.type == "spread_parameter":
            kind = next(c for c in child.named_children if c.type not in ("modifiers", "variable_declarator"))
            types.append(_clean_type(kind, src) + "...")
        elif child.type == "parameter_modifiers":
            vararg = "vararg" in text(child, src).split()
        elif child.type == "parameter":
            colon = [i for i, c in enumerate(child.children) if c.type == ":"]
            kind = child.children[colon[0] + 1] if colon else None
            types.append((_clean_type(kind, src) if kind is not None else "") + ("..." if vararg else ""))
            vararg = False
    return types


def member_name(node, src: bytes, owner: str) -> str:
    """메서드·생성자·초기화 블록의 심볼 이름(spec FR-020)."""
    if node.type == "static_initializer":
        return "<clinit>"
    if node.type in ("block", "anonymous_initializer"):
        return "<init>"
    if node.type == "annotation_type_element_declaration":
        return type_name(node, src) + "()"
    if node.type == "compact_constructor_declaration":
        record = node.parent.parent
        return owner + "(" + ",".join(parameter_types(record.child_by_field_name("parameters"), src)) + ")"
    params = node.child_by_field_name("parameters")
    if params is None:
        params = next((c for c in node.children if c.type == "function_value_parameters"), None)
    names = "(" + ",".join(parameter_types(params, src)) + ")"
    if node.type in ("constructor_declaration", "secondary_constructor"):
        return owner + names
    name = node.child_by_field_name("name")
    receiver = next(
        (c for c in node.children if c.type in RECEIVER_NODES and c.end_byte <= name.start_byte),
        None,
    )
    prefix = _clean_type(receiver, src) + "." if receiver is not None else ""
    return prefix + text(name, src).strip("`") + names


def _first_declarator(node):
    for kind in DECLARATORS:
        found = _descendants(node, {kind})
        if found:
            return found[0]
    return None


def field_name(node, src: bytes) -> str:
    """필드·프로퍼티 묶음의 심볼 이름은 첫 이름이다."""
    declarator = _first_declarator(node)
    if declarator is None:
        return ""
    name = declarator.child_by_field_name("name")
    if name is None:
        name = next(iter(_descendants(declarator, {"identifier", "simple_identifier"})), declarator)
    return text(name, src).strip("`")


def field_name_row(node) -> int:
    """필드 선언 줄의 끝(0부터): 첫 이름이 있는 줄. 여러 줄 초기값의 나머지는 요약에 넣지 않는다."""
    declarator = _first_declarator(node)
    return declarator.start_point[0] if declarator is not None else node.start_point[0]


def signature(node, src: bytes) -> str:
    """선언 어노테이션과 본문을 뺀 선언 원문을 공백 하나로 정리한 값(spec FR-023)."""
    body = body_of(node)
    end = body.start_byte if body is not None else node.end_byte
    raw = _slice(src, node.start_byte, end, declaration_annotations(node))
    return re.sub(r"\s+", " ", raw).strip().rstrip(";").strip()


def superclasses(node, src: bytes) -> list[str]:
    """상위 클래스 단순 이름(Java `extends`, Kotlin 생성자 호출이 붙은 상위 형식, spec FR-024)."""
    names = []
    superclass = node.child_by_field_name("superclass")
    if superclass is not None:
        names.append(text(superclass, src).removeprefix("extends").strip())
    for specifiers in (c for c in node.children if c.type == "delegation_specifiers"):
        for specifier in specifiers.named_children:
            invocation = next((c for c in specifier.named_children if c.type == "constructor_invocation"), None)
            if invocation is not None:
                names.append(text(invocation.named_children[0], src))
    return [re.split(r"[<(\s]", name, maxsplit=1)[0].rsplit(".", 1)[-1] for name in names]


def component(names: list[str], android: bool) -> str:
    if not android:
        return ""
    for name in names:
        if name in rules.ANDROID_BASES:
            return rules.ANDROID_BASES[name].value
        for suffix, kind in rules.COMPONENT_SUFFIXES:
            if name.endswith(suffix):
                return kind.value
    return ""


def has_android_import(root, src: bytes) -> bool:
    imports = (c for c in root.children if c.type in ("import_declaration", "import"))
    return any(_ANDROID_IMPORT.match(text(c, src)) for c in imports)


def package_of(root, src: bytes) -> str:
    for child in root.children:
        if child.type in ("package_declaration", "package_header"):
            name = next((c for c in child.named_children if "identifier" in c.type), None)
            return re.sub(r"\s+", "", text(name, src)) if name is not None else ""
    return ""


def is_test_path(location: str) -> bool:
    return any(("/" + directory) in ("/" + location) for directory in rules.TEST_SOURCE_SETS)


def is_test_method(names: list[str]) -> bool:
    return any(name in rules.TEST_ANNOTATIONS for name in names)


@dataclass(frozen=True)
class RootAnnotation:
    """Kotlin 루트에서 식으로 잘못 읽힌 어노테이션 덩어리(인자 포함). 바로 뒤 선언에 붙인다."""

    start_byte: int
    end_byte: int
    start_row: int
    names: tuple[str, ...]


def root_annotations(tree, src: bytes) -> tuple[RootAnnotation, ...]:
    """루트 `annotated_expression` 사슬에서 어노테이션 부분만 고른다. 어노테이션 뒤의 식(삼켜진 선언)은 넣지 않는다."""
    found = []
    for node in tree.root_node.children:
        if node.type != "annotated_expression":
            continue
        names, end, current = [], node.start_byte, node
        while current is not None and current.type == "annotated_expression":
            children = current.children
            index = next((i for i, c in enumerate(children) if c.type == "annotation"), None)
            if index is None:
                break
            names.append(annotation_name(children[index], src))
            end = children[index].end_byte
            rest = children[index + 1 :]
            if rest and rest[0].type == "parenthesized_expression" and rest[0].start_byte == end:
                end = rest[0].end_byte  # `@InstallIn(..)`의 인자를 해석기가 따로 떼어 읽는다
                rest = rest[1:]
            current = rest[0] if rest else None
        found.append(RootAnnotation(node.start_byte, end, node.start_point[0], tuple(names)))
    return tuple(found)


def stray_root(tree) -> int | None:
    """Kotlin 파일 루트에 선언이 아닌 노드가 있으면 그 줄(0부터). 해석기가 잘못 읽은 곳이다."""
    return next((c.start_point[0] for c in tree.root_node.children if c.type not in rules.KOTLIN_ROOT_NODES), None)
