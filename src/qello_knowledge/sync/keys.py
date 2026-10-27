"""동기화 식별값. 본문과 원본 식별자 원값을 기록에 노출하지 않는다."""

from hashlib import sha256

METADATA_SCHEMA_VERSION = "meta-v1"
CODE_METADATA_SCHEMA_VERSION = "meta-v2"  # 코드 청크의 `locator["code"]`(QK-CHK-001 research R-11)


def chunk_input_hash(content_hash: str, location: str, source_title: str | None) -> str:
    return sha256(
        ("qk-chunk-input-v1\0" + content_hash + "\0" + location + "\0" + (source_title or "")).encode()
    ).hexdigest()


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


def metadata_schema_version(code=None) -> str:
    """코드 청킹이 켜졌을 때만 새 메타데이터 스키마 버전이 인덱스 버전 재료가 된다(QK-CHK-001 spec FR-026)."""
    return METADATA_SCHEMA_VERSION if code is None else CODE_METADATA_SCHEMA_VERSION


def scope_key(kind, scope=None, *, repo=None, ref=None):
    if scope is not None:
        extra = dict(scope.extra)
        repo, ref = extra.get("repo"), extra.get("ref")
    if kind == "github_repo_files":
        if not repo or not ref:
            raise ValueError("source scope requires repo and ref")
        return f"{kind}:{repo}@{ref}".lower()
    # 가짜 자료원도 원본 종류 이름공간을 유지한다.
    return f"{kind}:{repo or ''}@{ref or ''}".lower()
