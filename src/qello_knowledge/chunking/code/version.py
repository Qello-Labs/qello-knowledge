"""코드 청킹 규칙 버전과 규칙 상수(research R-08). 청크를 바꾸는 규칙을 고치면 해당 판수를 올린다.

해석기 버전은 고정 상수다. 모듈을 불러와 읽지 않으므로 버전 계산이 네이티브 해석기를 불러오지 않는다.
"""

import hashlib
import json
import re

from qello_knowledge.domain.chunking import (
    WORST_BYTES_PER_TOKEN,
    AndroidComponent,
    ChunkingSettings,
    CodeChunkingSettings,
)

RULES_REVISION = 1
HEADER_FORMAT = 1
SEARCH_TEXT_FORMAT = 1
EMBEDDING_INPUT_FORMAT = 1
CONTEXT_OMISSION_REVISION = 1
FALLBACK_REVISION = 1
SUMMARY_SKIP_REVISION = 1
PARSER_VERSIONS = {"tree-sitter": "0.26.0", "tree-sitter-java": "0.23.5", "tree-sitter-kotlin": "1.1.0"}

# Kotlin 해석용 같은 길이 사본(research R-01). 문장 맨 앞 `suspend { … }` 람다를 함수 수식어로 읽는 문법 결함을 피한다.
KOTLIN_PARSE_COPY_RULE = "suspend-lambda-v1"
KOTLIN_PARSE_COPY = re.compile(rb"\bsuspend(?=\s*\{)")
KOTLIN_PARSE_COPY_WITH = b"run    "
# 해석기가 루트의 어노테이션(+ `private` 같은 수식어)을 식으로 잘못 읽는 결함을 피한다.
# 어노테이션 부분을 같은 길이 공백으로 바꿔 다시 해석하고, 지운 어노테이션은 바로 뒤 선언에 붙인다.
# 그래도 루트에 아래 밖의 노드가 남으면 해석 실패다(spec FR-019).
KOTLIN_ROOT_ANNOTATION_RULE = "root-annotation-v1"
KOTLIN_ROOT_NODES = (
    "package_header",
    "import",
    "import_list",
    "import_header",
    "file_annotation",
    "shebang_line",
    "line_comment",
    "block_comment",
    "type_alias",
    "class_declaration",
    "object_declaration",
    "function_declaration",
    "property_declaration",
)

ANDROID_BASES = {
    "Activity": AndroidComponent.ACTIVITY,
    "AppCompatActivity": AndroidComponent.ACTIVITY,
    "ComponentActivity": AndroidComponent.ACTIVITY,
    "FragmentActivity": AndroidComponent.ACTIVITY,
    "Fragment": AndroidComponent.FRAGMENT,
    "DialogFragment": AndroidComponent.FRAGMENT,
    "BottomSheetDialogFragment": AndroidComponent.FRAGMENT,
    "ViewModel": AndroidComponent.VIEW_MODEL,
    "AndroidViewModel": AndroidComponent.VIEW_MODEL,
    "Service": AndroidComponent.SERVICE,
    "BroadcastReceiver": AndroidComponent.BROADCAST_RECEIVER,
    "ContentProvider": AndroidComponent.CONTENT_PROVIDER,
    "Application": AndroidComponent.APPLICATION,
}
COMPONENT_SUFFIXES = (
    ("Activity", AndroidComponent.ACTIVITY),
    ("Fragment", AndroidComponent.FRAGMENT),
    ("ViewModel", AndroidComponent.VIEW_MODEL),
    ("Service", AndroidComponent.SERVICE),
    ("BroadcastReceiver", AndroidComponent.BROADCAST_RECEIVER),
    ("ContentProvider", AndroidComponent.CONTENT_PROVIDER),
    ("Application", AndroidComponent.APPLICATION),
)
TEST_SOURCE_SETS = ("src/test/", "src/integrationTest/", "src/androidTest/", "src/testFixtures/")
TEST_ANNOTATIONS = ("Test", "ParameterizedTest", "RepeatedTest", "TestFactory", "TestTemplate")


def code_chunking_version(code: CodeChunkingSettings, settings: ChunkingSettings) -> str:
    material = {
        "rules_revision": RULES_REVISION,
        "header_format": HEADER_FORMAT,
        "search_text_format": SEARCH_TEXT_FORMAT,
        "embedding_input_format": EMBEDDING_INPUT_FORMAT,
        "context_omission_revision": CONTEXT_OMISSION_REVISION,
        "fallback_revision": FALLBACK_REVISION,
        "summary_skip_revision": SUMMARY_SKIP_REVISION,
        "settings": {
            "limit_tokens": code.limit_tokens,
            "target_tokens": code.target_tokens,
            "model_version": code.model_version,
            "worst_bytes_per_token": WORST_BYTES_PER_TOKEN,
        },
        "keyword_text_rule": settings.keyword_text_rule,
        "parsers": PARSER_VERSIONS,
        "kotlin_parse_copy": KOTLIN_PARSE_COPY_RULE,
        "kotlin_root_annotation": KOTLIN_ROOT_ANNOTATION_RULE,
        "kotlin_root_nodes": list(KOTLIN_ROOT_NODES),
        "android_bases": {name: str(kind) for name, kind in ANDROID_BASES.items()},
        "component_suffixes": [[suffix, str(kind)] for suffix, kind in COMPONENT_SUFFIXES],
        "test_source_sets": list(TEST_SOURCE_SETS),
        "test_annotations": list(TEST_ANNOTATIONS),
    }
    payload = json.dumps(material, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "chk-code-" + hashlib.sha256(payload).hexdigest()[:12]
