"""동기화 식별값. 본문과 원본 식별자 원값을 기록에 노출하지 않는다."""

from hashlib import sha256

METADATA_SCHEMA_VERSION = "meta-v1"
CODE_METADATA_SCHEMA_VERSION = "meta-v2"  # 코드 청크의 `locator["code"]`(QK-CHK-001 research R-11)
CONFLUENCE_METADATA_SUFFIX = "+cf1"  # Confluence 청크의 `locator["confluence"]`(QK-ING-003 research R-10)


def chunk_input_hash(content_hash: str, location: str, source_title: str | None, extra: str | None = None) -> str:
    """`extra`는 자료원 종류가 더하는 변경 판정 재료다(QK-ING-003 R-09). 없으면 기존 바이트열 그대로다."""
    material = "qk-chunk-input-v1\0" + content_hash + "\0" + location + "\0" + (source_title or "")
    if extra is not None:
        material += "\0" + extra
    return sha256(material.encode()).hexdigest()


def doc_key(source_name: str, source_kind: str, source_id: str) -> str:
    return sha256(("qk-doc-v1\0" + source_name + "\0" + source_kind + "\0" + source_id).encode()).hexdigest()


def index_version_id(
    embedding_model: str, dimension: int, chunking_version: str, metadata_schema_version: str = METADATA_SCHEMA_VERSION
) -> str:
    return (
        "iv-"
        + sha256(
            "\0".join(map(str, (embedding_model, dimension, chunking_version, metadata_schema_version))).encode()
        ).hexdigest()[:12]
    )


def metadata_schema_version(code=None, confluence: bool = False) -> str:
    """코드 청킹·Confluence가 켜졌을 때만 새 메타데이터 스키마 버전이 인덱스 버전 재료가 된다.

    근거는 QK-CHK-001 spec FR-026과 QK-ING-003 research R-10이다.
    """
    base = METADATA_SCHEMA_VERSION if code is None else CODE_METADATA_SCHEMA_VERSION
    return base + CONFLUENCE_METADATA_SUFFIX if confluence else base


def scope_key(kind, scope=None, *, repo=None, ref=None):
    extra = dict(scope.extra) if scope is not None else {}
    if scope is not None:
        repo, ref = extra.get("repo"), extra.get("ref")
    if kind == "confluence_pages":
        # 스페이스 키가 바뀌어도 같은 스페이스면 같은 범위다(QK-ING-003 FR-002a).
        if not extra.get("space_id"):
            raise ValueError("source scope requires space_id")
        return f"{kind}:{extra['space_id']}"
    if kind == "github_repo_files":
        if not repo or not ref:
            raise ValueError("source scope requires repo and ref")
        return f"{kind}:{repo}@{ref}".lower()
    # 가짜 자료원도 원본 종류 이름공간을 유지한다.
    return f"{kind}:{repo or ''}@{ref or ''}".lower()
