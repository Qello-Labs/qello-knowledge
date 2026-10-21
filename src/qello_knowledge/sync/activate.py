"""첫 인덱스 버전 활성화. 검사와 변경의 배타성은 저장 경계가 보장한다."""


def activate_first_index(store, version):
    return store.activate(version)
