# Contract: 보안 필터

색인 진입점(`qk-index`, Workers 밖)에서만 쓴다. 타입은 [data-model.md](../data-model.md)를 따른다. 모든 함수는 원본에 쓰지 않고 외부 API를 부르지 않는다(FR-005).

## 조립 함수 (QK-SYN-001이 부른다)

```python
def screen_source(
    adapter: SourceAdapter,
    config: SourceConfig,
    session: DefaultSourceSession,
    policy: SecurityPolicy,
) -> ScreenResult: ...
```

1. `list_all(adapter, config, session)` (QK-ING-001)
2. `screen_items(listing.items, config, policy)` → 목록 단계 판정
3. 목록 단계를 통과한 항목만 `fetch_contents(adapter, config, session, replace(listing, items=passed_items))` (QK-ING-001).
   튜플을 넘기지 않는다. 원래 목록의 `complete`·`stop`을 보존해야 한다(R-11a)
4. `fetch_result.items` 중 `SUCCEEDED`가 아닌 자료 → `ERROR`, `stage=FETCH`(R-11b)
5. `screen_contents(fetched, items_by_id, config, policy)` → 본문 단계 판정
6. `ScreenResult(passed, verdicts, summary, fetch=replace(fetch_result, contents=()))`

규칙:
- 2단계에서 빠진 자료의 본문 조회 요청은 0건이다(FR-002). "추가 본문 조회"는 3단계 요청만 뜻한다. 어댑터가 1단계에서 변경 판별값을 채우려고
  받은 본문(QK-ING-001 계약 6항)은 필터로 넘어오지 않는다.
- 본문 조회에 실패하거나 멈춤으로 건너뛴 자료는 `ERROR`(판정 실패)다. `error_type`은 `fetch:<ItemStatus>:<FailureType 또는 none>`이다.
- 목록에 나온 자료마다 판정 기록이 정확히 하나이고, 요약의 결과별 합은 목록 자료 수와 같다.
- `fetch.contents`는 항상 비어 있다. 다음 단계는 `passed`만 쓴다(R-11).
- 판정 하나가 예외를 내면 그 자료는 `ERROR`이고, 나머지 자료는 계속 판정한다(FR-004).

## 단계 함수

```python
def screen_items(
    items: Iterable[SourceItem], config: SourceConfig, policy: SecurityPolicy
) -> tuple[tuple[SourceItem, ...], tuple[SecurityVerdict, ...]]: ...
```

자료마다 차례로 판정한다. 앞에서 걸리면 뒤 단계를 하지 않는다.

| 순서 | 판정 | 걸리면 |
| --- | --- | --- |
| 1 | 기본 제외(`excluded_by(location)`) | `PATH_EXCLUDED`, `rule`=범주 이름 |
| 2 | 자료원 설정 제외(`config.scope.exclude`, 대소문자 무시) | `PATH_EXCLUDED`, `rule`=`source-exclude` |
| 3 | 접근 판정(`policy.kinds[kind].judge(item.access)`, 등록 없음이면 `UNKNOWN`) | `TEAM`이 아니면 `ACCESS_HELD` |
| 4 | 메타데이터 비밀값(`source_id`, `location`, `title`, `url`) | `SECRET_BLOCKED`, `stage=ITEM_SECRET`, `rule`=비밀값 규칙, `field` |
| 5 | 식별자 주소(`safe_text(source_id, PATH 또는 TEXT, policy.output_context(kind))`가 주소를 가렸음. 맨 호스트 포함) | `SECRET_BLOCKED`, `stage=ITEM_SECRET`, `rule=identifier-address`, `field=source_id` |

5번은 ING-001이 본문을 받은 자료의 `source_id`를 `collect.py` 로그와 `FetchResult.to_dict()`에 그대로 남기기 때문에 둔다(R-01). 위치·제목·링크의 주소는
막지 않고 이 명세의 기록에서 가린다.

2번은 ING-001 `list_all()`이 이미 거른 것을 다시 확인하는 방어선이다(대소문자 무시로 더 엄격하다). 개인 정보 확인으로 사람이 넣은 제외 패턴이 여기서
지켜진다(FR-024, SC-003).

```python
def screen_contents(
    contents: Iterable[SourceContent],
    items_by_id: Mapping[str, SourceItem],
    config: SourceConfig,
    policy: SecurityPolicy,
) -> tuple[tuple[ScreenedContent, ...], tuple[SecurityVerdict, ...]]: ...
```

본문·제목·위치를 `find_secrets()`로 검사한다. 예외는 `(config.name, 정규화한 location, rule)`이 예외 목록에 있을 때 그 규칙만 건너뛴다(FR-012).
하나라도 남으면 자료 전체가 `SECRET_BLOCKED`다(FR-011). 남지 않으면 `PASSED`, `access_scope=TEAM`.

## 전송 직전 검사

```python
def check_outgoing(pieces: Sequence[OutgoingPiece], policy: SecurityPolicy) -> SendCheck: ...
```

- 조각마다 `find_secrets(piece.text)`를 돌린다. `origin`이 있는 조각에만 그 `(source_name, path)` 예외를 적용한다. `origin`이 `None`이면 예외를 적용하지 않는다.
- 걸린 조각이 하나라도 있으면 `allowed=False`. 호출자는 그 요청 전체를 보내지 않는다(FR-013).
- 결과와 로그에 조각 본문이나 맞은 문자열을 담지 않는다. 조각 번호, 규칙 이름, 줄 번호만 담는다.
- 연결은 QK-EMB-001(임베딩 입력), QK-GEN-001(생성 입력)이 한다.

## 출력

- `SecurityVerdict.to_dict(policy.output_context(config.kind))`, `FilterSummary.to_dict()`가 판정 기록과 요약의 유일한 직렬화다. 로그도 이 사전만 쓴다.
- 로그 이름은 `qello_knowledge.security`. 자료마다 `INFO` 한 줄(`verdict`, `stage`, `rule`, 가린 `source_id`)과 실행마다 요약 한 줄.
- 모든 문자열은 `safe_text(value, field_kind, context)`를 거친다(FR-023, R-07). 필드와 `FieldKind` 대응은 data-model.md `OutputContext`에 고정돼 있다.
  `url`은 `context.public_link_hosts`에 있는 `https` 주소만 남고 나머지는 `[가림:address]`다.
  스킴 없는 맨 호스트 이름은 필드 종류별로 판정한다(R-07). 경로 필드(`location`, 경로형 `source_id`)의 파일 이름 부분만 확장자가 `FILE_EXTENSIONS`에 있으면
  남고, 디렉터리 부분과 글 필드(`title`, 원본 권한 원값, 경로 아닌 `source_id`)의 점으로 이어진 이름은 모두 숫자가 아니면 끝부분과 상관없이 가린다.

## 정책 읽기

```python
def load_policy(
    exceptions_path: Path, configs: Sequence[SourceConfig]
) -> tuple[SecurityPolicy | None, tuple[PolicyIssue, ...]]: ...
```

예외 파일 검증 오류가 하나라도 있으면 `None`과 오류 목록을 돌려준다. 호출자는 원본을 부르기 전에 멈춘다([security-exceptions.md](security-exceptions.md)).
