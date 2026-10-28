# Contract: ADF → Markdown 변환(`adf-md-v1`)

근거: [research.md](../research.md) R-08, R-11 | 요구: spec FR-013~FR-019, FR-021~FR-023

`convert_adf(doc, *, title, site_host, public_link_hosts, doc_type) -> ConvertResult(markdown, rules_version, warnings, meeting)`. 위치는 `adapters/atlassian_adf.py`이고 표준 라이브러리만 쓴다.
입력이 같으면 출력이 바이트 단위로 같다. 줄바꿈은 `\n`, 블록 사이 빈 줄 하나, 끝에 줄바꿈 하나다. 첫 줄은 `# <title>`이다.

## 블록

| ADF 노드 | Markdown |
| --- | --- |
| `heading`(level n) | `#`×min(n+1, 6) + 텍스트(페이지 제목이 H1이라 한 단계 내린다) |
| `paragraph` | 인라인 텍스트 |
| `bulletList` / `orderedList` / `taskList` | `- ` / `1. ` / `- [ ] `·`- [x] `, 하위 목록은 두 칸 들여쓰기 |
| `codeBlock` | ```` ```<language> ```` 울타리. 본문에 ```` ``` ````가 있으면 울타리를 늘린다 |
| `blockquote` | `> ` |
| `rule` | `---` |
| `table`(병합·중첩 없음) | 첫 행을 머리글로 한 Markdown 표. 셀 안 줄바꿈은 공백, `\|`는 `\\|` |
| `table`(셀 병합 또는 표 안 표) | 행 순서대로 `- <셀1> / <셀2> …` 목록, 경고 `TABLE_FLATTENED` |
| `panel` | `**<패널 종류 이름>**` 줄 뒤에 본문 |
| `expand` / `nestedExpand` | `**<attrs.title>**` 줄 뒤에 본문 |
| `mediaSingle` / `mediaGroup` | `mediaSingle`은 `[이미지]`, `mediaGroup`의 항목은 `[첨부: <attrs.alt>]`(없으면 `[첨부]`). 파일은 받지 않는다 |
| `extension` / `bodiedExtension` / 모르는 블록 | `[매크로: <extensionKey 또는 노드 종류>]`, 경고 `UNSUPPORTED_BLOCK`. 설정값·하위 내용은 넣지 않는다. 사용자 정보를 보여 주는 매크로도 이 규칙이다 |
| `blockCard` / `embedCard` | 링크 규칙을 따른 링크 한 줄 |
| `layoutSection` / `layoutColumn` | 열 구분 없이 안의 블록을 차례로 펼친다(구현 검토 C2) |
| `decisionList` / `decisionItem` | 항목마다 `- <텍스트>` 목록(구현 검토 C2) |

## 인라인

| ADF | Markdown |
| --- | --- |
| `text` + `strong`·`em`·`code`·`strike` | `**`·`*`·`` ` ``·`~~` |
| `text` + `link` | 링크 규칙 |
| `hardBreak` | 줄바꿈 |
| `mention` | `attrs.text`에서 앞의 `@`를 뗀 표시 이름. `attrs.id`(계정 ID)는 버린다 |
| `emoji` / `status` / `date` | `attrs.text`(없으면 `shortName`) / `attrs.text` / `attrs.timestamp`를 UTC `YYYY-MM-DD`로 |
| `inlineCard` | 링크 규칙 |
| `inlineExtension`·모르는 인라인 | `[매크로: <키>]`, 경고 `UNSUPPORTED_BLOCK` |

## 링크 규칙(FR-018)

링크 텍스트는 항상 남긴다. 주소는 `https`이고 다음 중 하나일 때만 `[텍스트](주소)`로 남긴다(2026-10-28 사용자 결정, research R-06).

1. 호스트가 `site_host`와 같고, 경로가 사람·개인 스페이스를 가리키지 않는다. 퍼센트 인코딩을 푼 경로의 어느 조각이 `people`이거나 `~`로 시작하면 주소를 버린다(`/wiki/people/…`, `/jira/people/…`, `/wiki/display/~…`, `%7E…`, 구현 검토 C3).
2. 호스트가 `public_link_hosts`(보안 필터에 등록된 모든 종류의 공개 링크 호스트 합집합. 변환기 인자로 받는다)에 있다.

남기는 주소도 쿼리와 조각을 버린다. `mailto:`는 `[메일 주소]`로 바꾸고 주소를 버린다. 그 밖은 텍스트만 남긴다. 텍스트가 없는 카드는 남긴 주소 자체를 텍스트로 쓰고, 주소를 버렸으면 `[링크]`다.
링크 텍스트가 버린 주소를 담거나 그 주소의 호스트를 담으면(스킴 없는 자동 링크 포함) 텍스트도 `[링크]`로 바꾼다. 계정 ID가 텍스트로 남지 않게 하려는 것이다(plan 재검토 N3, 구현 검토 C3).

## 이스케이프(구현 검토 C7)

코드 표식이 없는 원문 텍스트의 ```` ``` ````는 `` \`\`\` ``로 바꾼다. 줄 머리(문단 시작과 줄바꿈 뒤)의 `#`·`>`·`|`·`+`·`*`·`-`는 앞에, 번호 표시(`1.`·`1)`)는 점·괄호 앞에 백슬래시를 둔다.
형식이 어긋난 속성(문자열 `colspan` 등)은 기본값으로 보고, 그래도 변환이 실패하면 그 페이지만 잘못된 응답으로 실패한다(구현 검토 C6).
서명은 `convert_adf(doc, *, title, site_host, public_link_hosts, doc_type)`이다.

## 본문 없음

변환 결과에 제목 줄·자리 표시(`[이미지]`·`[첨부…]`·`[매크로…]`·`[링크]`·`[메일 주소]`) 말고 텍스트가 없으면 `markdown`은 빈 문자열이다. 청커가 `EMPTY`를 돌려주고 요약 "본문 없음"으로 센다(FR-032).
입력 `doc`은 `body.atlas_doc_format.value`(JSON 문자열)를 파싱한 객체다.

## 문서 종류별 처리

- `회의록`: 본문 첫 표의 첫 열 `일시`·`회의 종류`·`관련 명세 ID` 행을 읽어 `meeting={date, kind, spec_ids}`를 만든다. `일시`가 없거나 `YYYY-MM-DD`가 아니면 `meeting=None`과
  경고 `MEETING_METADATA_MISSING`. `관련 명세 ID`는 쉼표로 나눠 앞뒤 공백을 지우고 `없음`·빈 값은 뺀다. 표는 본문에 그대로 둔다(FR-022).
- `용어집`: 머리글이 `용어 | 정의 | 동의어·약어·영문 | 코드 식별자·API 경로 | 관련 문서`인 표를 행마다 `## <용어>`와 `- <머리글>: <값>` 목록(빈 값 생략)으로 바꾼다.
  그런 표가 하나도 없으면 경고 `NOT_GLOSSARY`(FR-023).
- 그 밖: 위 규칙만.

## 경고

`ConversionWarning(kind, block)` — `block`은 최상위 블록 순번이다. 원문·매크로 설정값·이름은 담지 않는다. 경고는 수집 요약에서 종류별 수로만 나온다.

## 시험

`tests/fixtures/confluence/adf/<사례>.json`과 사람이 쓴 `<사례>.md`·`<사례>.warnings.json`을 짝으로 두고 같음을 본다(SC-003). 사례: 기본 블록, 코드 울타리 충돌, 병합 표, 표 안 표,
패널·확장, 모르는 매크로, 페이지 포함 매크로, 멘션·메일·사용자 정보 매크로, 이미지·첨부만 있는 페이지(빈 본문), 링크(사이트 일반 경로, 사이트 사람·개인 스페이스 경로, 등록 호스트,
그 밖의 공개 주소, 쿼리·조각 있음), 회의록(정상·일시 없음·형식 틀림), 용어집(정상·머리글 다름).
두 번 변환해 바이트가 같은지도 본다.
