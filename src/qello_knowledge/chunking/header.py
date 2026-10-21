"""검색·임베딩 입력 형식(research R-09)."""


def search_header(location, title, heading_path):
    path = heading_path[1:] if heading_path and heading_path[0] == title else heading_path
    return location + "\n" + " > ".join((title, *path))


def search_text(header, body):
    return header + "\n\n" + body


def embedding_text(header, prefix, body):
    return header + "\n\n" + (prefix + "\n" if prefix else "") + body
