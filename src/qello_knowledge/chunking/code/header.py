"""코드 청크의 검색 헤더·임베딩 입력·키워드 텍스트(contracts/chunker.md 8절, research R-07).

임베딩 입력과 키워드 텍스트는 Markdown과 같은 `chunking.header` 함수를 그대로 쓴다.
"""

from qello_knowledge.chunking.header import embedding_text, search_text


def search_header(location: str, language: str, package: str, path, kind: str, display: str = "") -> str:
    first = location + " " + language
    if package and "/" + package.replace(".", "/") + "/" not in "/" + location:
        first += " " + package  # 경로 구성 요소에 이미 있는 패키지는 뺀다(spec FR-021)
    second = (" > ".join(path) + " " if path else "") + "[" + kind + "]"
    return first + "\n" + second + (" " + display if display else "")


def chunk_texts(header: str, context, repeat, body: str, rule: str) -> tuple[str, str]:
    """(임베딩 입력, 키워드 검색 텍스트). `context`는 맥락 줄, `repeat`는 뒤 조각의 반복 줄이다."""
    prefix = "\n".join([*context, *repeat])
    keyword_body = "\n".join(context) + "\n" + body if context else body
    return embedding_text(header, prefix, body), search_text(header, keyword_body, rule)
