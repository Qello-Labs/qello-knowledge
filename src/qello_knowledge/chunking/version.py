"""규칙 코드를 바꾸면 해당 판수를 올린다(research R-07). 경고 규칙은 제외한다."""

import hashlib
import json

from qello_knowledge.chunking.blocks import PARSER_VERSION
from qello_knowledge.domain.chunking import WORST_BYTES_PER_TOKEN, ChunkingSettings
from qello_knowledge.domain.keyword_rules import INDEX_BASELINE

RULES_REVISION = 1
HEADER_FORMAT = 1
SEARCH_TEXT_FORMAT = 1
EMBEDDING_INPUT_FORMAT = 1


def chunking_version(settings: ChunkingSettings) -> str:
    material = {
        "rules_revision": RULES_REVISION,
        "header_format": HEADER_FORMAT,
        "search_text_format": SEARCH_TEXT_FORMAT,
        "embedding_input_format": EMBEDDING_INPUT_FORMAT,
        "settings": {
            "limit_tokens": settings.limit_tokens,
            "target_tokens": settings.target_tokens,
            "model_version": settings.model_version,
            "worst_bytes_per_token": WORST_BYTES_PER_TOKEN,
        },
        "parser": {"enable": ["table"], "name": "markdown-it-py", "preset": "commonmark", "version": PARSER_VERSION},
    }
    if settings.keyword_text_rule != INDEX_BASELINE:
        # 기준선은 재료에 넣지 않아 기존 버전 값이 그대로다(QK-RET-001 research R-04, spec SC-010).
        material["keyword_text_rule"] = settings.keyword_text_rule
    payload = json.dumps(material, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "chk-md-" + hashlib.sha256(payload).hexdigest()[:12]
