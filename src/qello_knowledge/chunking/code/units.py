"""해석기 노드를 원문 청크 단위와 요약 청크로 바꾼다(spec FR-010~015, FR-020, FR-023~025, research R-05).

원문 청크는 단위 시작 줄만 정하고, 끝 줄은 다음 단위 시작 바로 앞까지다. 그래서 멤버에 붙지 않은 주석,
형식 닫는 줄, 표에 없는 노드는 앞 청크에 붙고 공백 아닌 줄이 정확히 한 원문 청크에 든다.
"""

from dataclasses import dataclass, field
from pathlib import PurePosixPath

from qello_knowledge.chunking.code import symbols
from qello_knowledge.domain.chunking import AndroidComponent
from qello_knowledge.domain.chunking import CodeChunkKind as Kind


@dataclass(frozen=True)
class Spec:
    types: frozenset[str]
    methods: frozenset[str]
    constructors: frozenset[str]
    inits: frozenset[str]
    fields: frozenset[str]
    head_items: frozenset[str]


SPECS = {
    "java": Spec(
        types=frozenset(
            {
                "class_declaration",
                "interface_declaration",
                "enum_declaration",
                "record_declaration",
                "annotation_type_declaration",
            }
        ),
        methods=frozenset({"method_declaration", "annotation_type_element_declaration"}),
        constructors=frozenset({"constructor_declaration", "compact_constructor_declaration"}),
        inits=frozenset({"static_initializer", "block"}),
        fields=frozenset({"field_declaration", "constant_declaration"}),
        head_items=frozenset({"enum_constant"}),
    ),
    "kotlin": Spec(
        types=frozenset({"class_declaration", "object_declaration", "companion_object"}),
        methods=frozenset({"function_declaration"}),
        constructors=frozenset({"secondary_constructor"}),
        inits=frozenset({"anonymous_initializer"}),
        fields=frozenset({"property_declaration"}),
        head_items=frozenset({"enum_entry"}),
    ),
}
COMMENTS = {"line_comment", "block_comment"}
CONTAINERS = {"enum_body_declarations"}  # Java 열거형 상수 뒤의 멤버 묶음


@dataclass
class Unit:
    kind: Kind
    path: tuple[str, ...]
    meta: dict
    start: int = -1  # 원문 청크 첫 줄(0부터, 붙은 주석 포함)
    end: int = -1  # 원문 청크 끝 줄(포함)
    context: tuple[tuple[str, ...], ...] = ()  # 맥락 줄 묶음, 바깥 형식부터(spec FR-021)
    repeat: tuple[str, ...] = ()  # 나뉜 뒤 조각에 붙일 반복 줄(spec FR-017)
    breaks: frozenset[int] = frozenset()  # 나누기 후보: 최상위 문장이 끝나는 줄
    groups: tuple[tuple[int, ...], ...] = ()  # 요약 청크: 멤버별 원문 줄 번호
    span: tuple[int, int] = (0, 0)  # 요약 청크 위치(0부터, 양 끝 포함)
    last: int = -1  # 원문 청크: 선언이 끝나는 줄. 다음 단위가 이 줄에서 시작하면 이 단위에 합친다


@dataclass(frozen=True)
class Owner:
    path: tuple[str, ...]
    kind: str
    modifiers: tuple[str, ...]
    component: str
    context: tuple[tuple[str, ...], ...]  # 이 형식 안 멤버에 붙는 맥락 줄(자기 선언 줄 포함)


@dataclass
class Builder:
    tree: object
    src: bytes
    lines: list[str]
    location: str
    language: str
    measure: object  # (단위, 첫 줄, 끝 줄) -> 예상 토큰
    target: int
    extra: tuple = ()  # 다시 해석하며 지운 루트 어노테이션(symbols.RootAnnotation). 바로 뒤 선언에 붙인다
    spec: Spec = field(init=False)

    def __post_init__(self):
        root = self.tree.root_node
        self.spec = SPECS[self.language]
        self.package = symbols.package_of(root, self.src)
        self.android = symbols.has_android_import(root, self.src)
        self.test_code = symbols.is_test_path(self.location)
        self.file = PurePosixPath(self.location).name
        decls = [c for c in root.children if self.is_member(c)]
        self.attached = {}
        for span in self.extra:
            following = next((d for d in decls if d.start_byte >= span.end_byte), None)
            if following is not None:
                self.attached[following.start_byte] = span

    def first_row(self, node):
        """선언 첫 줄. 루트 어노테이션을 붙인 선언은 그 어노테이션 줄부터다."""
        span = self.attached.get(node.start_byte)
        return span.start_row if span else node.start_point[0]

    def names(self, node):
        span = self.attached.get(node.start_byte)
        return [*(span.names if span else ()), *symbols.annotations(node, self.src)]

    def meta(self, kind, path=(), owner=None, *, signature="", annotations=(), node=None, component=""):
        test_method = (
            node is not None
            and self.test_code
            and kind in (Kind.METHOD, Kind.TOP_FUNCTION)
            and symbols.is_test_method(list(annotations))
        )
        return {
            "language": self.language,
            "package": self.package,
            "symbol": path[-1] if path else "",
            "signature": signature,
            "chunk_kind": kind.value,
            "type_kind": owner.kind if owner else "",
            "type_modifiers": list(owner.modifiers) if owner else [],
            "annotations": list(annotations),
            "test_code": self.test_code,
            "test_method": test_method,
            "display_name": symbols.display_name(node, self.src) if test_method else "",
            "component": component,
            "summary": kind in (Kind.TYPE_SUMMARY, Kind.FILE_SUMMARY),
        }

    def rows(self, first, last):
        return tuple(self.lines[first : last + 1])

    def lead(self, siblings, index):
        """멤버 바로 앞에 빈 줄 없이 이어 붙은 주석부터 단위가 시작한다(research R-05)."""
        node = siblings[index]
        floor = max((s.end_point[0] for s in siblings[:index] if s.type not in COMMENTS), default=-1)
        start = self.first_row(node)
        for comment in reversed(siblings[:index]):
            if comment.type not in COMMENTS or comment.end_point[0] + 1 < start or comment.start_point[0] <= floor:
                break
            start = comment.start_point[0]
        return start

    def is_member(self, node):
        spec = self.spec
        return node.type in spec.types | spec.methods | spec.constructors | spec.inits | spec.fields

    def items(self, body):
        """형식 본문의 (노드, 형제 목록, 위치)를 원문 순서로. 열거형 상수 같은 머리 항목도 포함한다."""
        if body is None:
            return []
        found = []
        for index, child in enumerate(body.children):
            if child.type in CONTAINERS:
                found += [(c, child.children, i) for i, c in enumerate(child.children) if self.is_member(c)]
            elif self.is_member(child) or child.type in self.spec.head_items:
                found.append((child, body.children, index))
        return found

    def breaks(self, node):
        body = symbols.body_of(node)
        if body is not None and body.type == "function_body":
            body = next((c for c in body.named_children if c.type == "block"), None)
        return frozenset(c.end_point[0] for c in body.named_children) if body is not None else frozenset()

    def member(self, node, start, owner, kind):
        name = symbols.member_name(node, self.src, owner.path[-1] if owner else "")
        path = (owner.path if owner else (self.file,)) + (name,)
        names = self.names(node)
        inherited = owner.component if owner else ""
        composable = self.android and "Composable" in names and kind in (Kind.METHOD, Kind.TOP_FUNCTION)
        signature = symbols.signature(node, self.src) if kind != Kind.INITIALIZER else ""
        meta = self.meta(
            kind,
            path,
            owner,
            signature=signature,
            annotations=names,
            node=node,
            component=AndroidComponent.COMPOSABLE.value if composable else inherited,
        )
        return Unit(
            kind,
            path,
            meta,
            start,
            context=owner.context if owner else (),
            repeat=self.rows(self.first_row(node), symbols.signature_end(node)),
            breaks=self.breaks(node),
            last=node.end_point[0],
        )

    def fields_unit(self, nodes, start, owner, kind, context, repeat):
        path = (owner.path if owner else (self.file,)) + (symbols.field_name(nodes[0], self.src),)
        names = dict.fromkeys(name for node in nodes for name in self.names(node))
        meta = self.meta(kind, path, owner, annotations=names, component=owner.component if owner else "")
        return Unit(kind, path, meta, start, context=context, repeat=repeat, last=nodes[-1].end_point[0])

    def group_fields(self, items, i, start, owner, kind, context, repeat, extend=None):
        """연속한 필드를 목표 크기까지 탐욕으로 묶는다(spec FR-010). `extend`가 있으면 그 단위에 더한다."""
        unit = extend
        nodes = []
        while i < len(items) and items[i][0].type in self.spec.fields:
            node = items[i][0]
            probe = unit or self.fields_unit([node], start, owner, kind, context, repeat)
            if (nodes or extend) and self.measure(probe, start, node.end_point[0]) > self.target:
                break
            nodes.append(node)
            unit = probe
            i += 1
        if extend is None and nodes:
            unit = self.fields_unit(nodes, start, owner, kind, context, repeat)
        elif nodes:
            unit.last = nodes[-1].end_point[0]
        return unit, nodes, i

    def walk_type(self, node, siblings, index, outer):
        src = self.src
        name = symbols.type_name(node, src)
        path = (outer.path if outer else ()) + (name,)
        body = symbols.body_of(node)
        declared = symbols.signature_end(node)
        decl = self.rows(self.first_row(node), declared)
        outer_context = outer.context if outer else ()
        owner = Owner(
            path,
            symbols.type_kind(node, src),
            tuple(symbols.type_modifiers(node, src)),
            symbols.component(symbols.superclasses(node, src), self.android),
            outer_context + (decl,),
        )
        start = self.lead(siblings, index)
        type_meta = self.meta(
            Kind.TYPE_HEAD,
            path,
            owner,
            signature=symbols.signature(node, src),
            annotations=self.names(node),
            component=owner.component,
        )
        head = Unit(Kind.TYPE_HEAD, path, type_meta, start, context=outer_context, repeat=decl, last=declared)
        units, items = [head], self.items(body)
        members = [item for item in items if self.is_member(item[0])]
        i = 0
        if members and members[0][0].type in self.spec.fields:
            first = self.lead(members[0][1], members[0][2])
            if self.measure(head, start, first - 1) < self.target:  # 머리만으로 목표 이상이면 합치지 않는다
                _, _, i = self.group_fields(members, 0, start, owner, Kind.FIELDS, (), (), extend=head)
        groups = [tuple(range(start, declared + 1))]
        has_body = False
        for item, _, _ in items:
            if item.type in self.spec.head_items:
                groups.append(tuple(range(item.start_point[0], symbols.signature_end(item) + 1)))
            elif item.type in self.spec.fields:
                groups.append(tuple(range(item.start_point[0], symbols.field_name_row(item) + 1)))
            else:
                groups.append(tuple(range(item.start_point[0], symbols.signature_end(item) + 1)))
                has_body = has_body or item.type in self.spec.types or symbols.signature_end(item) < item.end_point[0]
        while i < len(members):
            member, sibs, position = members[i]
            member_start = self.lead(sibs, position)
            if member.type in self.spec.fields:
                unit, _, i = self.group_fields(members, i, member_start, owner, Kind.FIELDS, owner.context, decl)
                units.append(unit)
                continue
            i += 1
            if member.type in self.spec.types:
                units += self.walk_type(member, sibs, position, owner)
            elif member.type in self.spec.constructors:
                units.append(self.member(member, member_start, owner, Kind.CONSTRUCTOR))
            elif member.type in self.spec.inits:
                units.append(self.member(member, member_start, owner, Kind.INITIALIZER))
            else:
                units.append(self.member(member, member_start, owner, Kind.METHOD))
        if has_body:  # 본문 있는 멤버가 없으면 요약을 만들지 않는다(spec FR-013)
            summary_meta = {**type_meta, "chunk_kind": Kind.TYPE_SUMMARY.value, "summary": True}
            summary = Unit(
                Kind.TYPE_SUMMARY,
                path,
                summary_meta,
                context=outer_context,
                repeat=decl,
                groups=_dedupe(groups),
                span=(start, node.end_point[0]),
            )
            units.insert(0, summary)
        return units

    def units(self):
        root = self.tree.root_node
        spec = self.spec
        children = root.children
        decls = [(c, i) for i, c in enumerate(children) if c.type in spec.types | spec.methods | spec.fields]
        units = []
        first = self.lead(children, decls[0][1]) if decls else len(self.lines)
        if first > 0:
            units.append(Unit(Kind.FILE_HEAD, (), self.meta(Kind.FILE_HEAD), 0))
        groups, has_body, k = [], False, 0
        while k < len(decls):
            node, index = decls[k]
            start = self.lead(children, index)
            if node.type in spec.types:
                units += self.walk_type(node, children, index, None)
                k += 1
            elif node.type in spec.methods:
                units.append(self.member(node, start, None, Kind.TOP_FUNCTION))
                groups.append(tuple(range(self.first_row(node), symbols.signature_end(node) + 1)))
                has_body = has_body or symbols.signature_end(node) < node.end_point[0]
                k += 1
            else:
                run = [(n, children, i) for n, i in decls[k:]]
                unit, nodes, taken = self.group_fields(run, 0, start, None, Kind.TOP_PROPERTIES, (), ())
                units.append(unit)
                groups += [tuple(range(self.first_row(n), symbols.field_name_row(n) + 1)) for n in nodes]
                k += taken
        if has_body:  # 블록 본문 최상위 함수가 있는 Kotlin 파일만 파일 요약을 둔다(spec FR-014)
            filled = [row for row, line in enumerate(self.lines) if line.strip()]
            summary = Unit(
                Kind.FILE_SUMMARY,
                (self.file,),
                self.meta(Kind.FILE_SUMMARY, (self.file,)),
                groups=_dedupe(groups),
                span=(filled[0], filled[-1]),
            )
            units.insert(1 if units and units[0].kind == Kind.FILE_HEAD else 0, summary)
        return _assign_ranges(units, self.lines)

    def fallback(self, ranges):
        meta = self.meta(Kind.FALLBACK)
        return [Unit(Kind.FALLBACK, (), dict(meta), start, end) for start, end in ranges]


def _dedupe(groups):
    """요약 줄은 한 번씩만 넣는다. 한 줄에 여러 선언이 있으면 앞 묶음에 남긴다."""
    seen, result = set(), []
    for group in groups:
        rows = tuple(row for row in group if row not in seen)
        seen.update(rows)
        if rows:
            result.append(rows)
    return tuple(result)


def _assign_ranges(units, lines):
    """원문 청크 끝 줄을 다음 단위 시작 바로 앞으로 정하고 앞뒤 빈 줄을 뺀다.

    앞 단위의 시작 줄이나 선언 끝 줄에서 시작한 단위(한 줄에 선언 여럿)는 앞 단위에 합친다.
    """
    sources = []
    for unit in units:
        if unit.groups:
            continue
        if sources and unit.start <= max(sources[-1].start, sources[-1].last):
            unit.start = -1
            continue
        sources.append(unit)
    for unit, after in zip(sources, [*sources[1:], None], strict=True):
        unit.end = after.start - 1 if after else len(lines) - 1
        while unit.start <= unit.end and not lines[unit.start].strip():
            unit.start += 1
        while unit.end >= unit.start and not lines[unit.end].strip():
            unit.end -= 1
    return [u for u in units if u.groups or (u.start >= 0 and u.start <= u.end)]
