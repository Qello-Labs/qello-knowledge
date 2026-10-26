# 계정·토큰 발급 범위

WBS 0.5 산출물이다. Qello Knowledge가 쓸 계정과 토큰의 권한 범위, 보관 위치, 확인 방법을 정리한다. 토큰·키 값과 계정 식별자는 적지 않는다.

| 항목 | 내용 |
| --- | --- |
| 조사일 | 2026-10-09 |
| 조사 방법 | 각 서비스 공식 문서 확인. 토큰 발급과 확인 호출은 사람이 했고, 에이전트는 확인 명령의 출력 줄만 봤다(7절). 공식 문서에서 확인하지 못한 내용은 "미확인"으로 표시했다 |
| 진행 상태 | Phase 1 3종(GitHub, Cloudflare, Discord) 발급·확인 완료(2026-10-09). 사람 리뷰 대기(#11) |
| 확인 환경 | 로컬 개발 환경. 실행 환경(ADR-008)은 0.9에서 정하고, 정해지면 보관 위치를 옮긴다(6절) |

## 1. 요약

| 토큰 | 용도 | 필요 단계 | 권한 범위 | 만료 | 이번 작업 |
| --- | --- | --- | --- | --- | --- |
| GitHub 세분화 토큰 | 제품 저장소 문서·코드·PR·Issue 읽기 | Phase 1 | 공개 저장소 읽기만. 저장소 권한 추가 없음 | 무기한(2.1절) | 발급·확인 |
| Cloudflare API 토큰 | Workers AI 임베딩·생성 호출 | Phase 1(0.6부터) | 계정 하나의 Workers AI Read·Edit | 기본 없음. TTL 선택 | 계정 소유 토큰으로 발급·확인 |
| Discord 애플리케이션·봇 | `/ask` 명령 등록과 응답, 요약 게시 | Phase 1 | 권한 있는 인텐트 없음. 서버 설치 범위는 4.3절 | 없음(유출 시 재설정) | 발급·확인. 서버 초대는 하지 않음 |
| ClickUp 수집 전용 계정 | ClickUp Docs·Tasks 읽기 | Phase 2 | 계정이 볼 수 있는 범위 전체(범위 지정 불가) | 없음 | 문서화만. Phase 2 전 발급 |
| DB 읽기 전용 계정 | DB 스키마 수집 | — | — | — | 발급 안 함 |
| Figma 토큰 | 프레임 수집 | Phase 4 | — | — | 보류 |

## 2. GitHub 세분화 토큰

### 2.1 발급 설정

| 설정 | 값 | 근거 |
| --- | --- | --- |
| 종류 | Fine-grained personal access token | 로드맵 0.5 |
| Resource owner | 발급자 본인 계정 | 세분화 토큰은 저장소 권한을 고르지 않아도 GitHub의 모든 공개 저장소를 읽을 수 있다 [G1] |
| Repository access | 공개 저장소만(읽기). 화면의 정확한 선택지 이름은 미확인 | [G1] |
| Repository permissions | 추가하지 않음 | Contents·Pull requests·Issues 조회 API는 공개 자료만 요청하면 해당 권한 없이 쓸 수 있다 [G3][G4][G5] |
| 만료 | 무기한. 초안은 366일을 권장했으나 발급자가 무기한을 골랐다(2026-10-09). 만료로 정리되지 않으므로 6절의 교체 조건을 따른다(T-06) | 1~366일 또는 무기한을 고를 수 있고 조직은 최대 수명을 강제할 수 있다 [G1][G2]. 공개 자료 읽기만 하므로 유출돼도 피해는 호출 한도 소모 정도다 |

- `dnd-side-project` 조직 관리자의 승인은 필요 없다. 승인 대기 중인 토큰도 조직의 공개 자료는 읽을 수 있다 [G2]. 인벤토리 F-1의 "조직 관리자 승인 필요 여부"는 이것으로 답이 된다.
- 인증하지 않으면 시간당 60회, 토큰을 쓰면 시간당 5,000회까지 호출할 수 있다 [G6].
- 발급자가 팀을 떠나면 토큰도 쓸 수 없게 된다. 오래 쓸 연동에는 GitHub App이 권장되지만 [G8], 조직에 설치하려면 조직 소유자가 필요하다 [G10]. Phase 1은 개인 토큰으로 시작하고, 운영 단계에서 다시 판단한다.

### 2.2 확인

`GET /rate_limit`은 REST 호출 한도를 소모하지 않고 권한도 필요 없다 [G6][G7]. 토큰이 유효하면 `core.limit`이 60이 아니라 5,000이다.

```bash
# 저장소 루트에서 실행한다. 토큰 값은 출력하지 않는다.
( set -a; . ./.env; set +a
  curl -sS -H "Authorization: Bearer $GITHUB_API_TOKEN" https://api.github.com/rate_limit \
    | python3 -c 'import json,sys; print("github core.limit =", json.load(sys.stdin)["resources"]["core"]["limit"])' )
```

## 3. Cloudflare API 토큰

### 3.1 발급 설정

| 설정 | 값 | 근거 |
| --- | --- | --- |
| 만드는 곳 | 계정 소유 토큰은 Manage account → Account API tokens → Create Token. 사용자 토큰은 Workers AI 대시보드의 "Use REST API" → "Create a Workers AI API Token", 또는 사용자 지정 토큰 | [C7][C1]. 일반 토큰 템플릿 목록에는 Workers AI 템플릿이 없다 [C4] |
| 권한 | Account → Workers AI → Read, Account → Workers AI → Edit | 사용자 지정 토큰은 두 권한이 모두 필요하다 [C1][C3] |
| 리소스 | Qello Knowledge용 계정 하나. "All accounts"를 쓰지 않는다 | 템플릿 기본값이 모든 계정이다 [C2][C4] |
| 소유 | 계정 소유 토큰 권장. 만들 권한이 없으면 사용자 토큰. 이번에는 계정 소유 토큰으로 발급했다(7절) | 계정 소유 토큰은 만든 사람이 떠나도 동작하고 Workers AI를 지원한다. 만들려면 Super Administrator나 API Token Provisioning 권한이 필요하다. 새 계정 소유 토큰은 `cfat_`로 시작한다 [C7] |
| IP 제한 | 지금은 쓰지 않는다. 실행 환경이 정해지면 다시 본다 | 선택 사항. Verify 엔드포인트에는 적용되지 않는다 [C5] |
| TTL | 선택. 정하지 않으면 만료되지 않는다 | [C5] |

- 무료 할당은 하루 10,000 Neurons이고 00:00 UTC에 초기화된다. 초과 과금은 Paid 플랜에서만 생긴다 [C8].
- `@cf/google/embeddinggemma-300m`은 요금표에 행이 없어 단가를 확인하지 못했다(Beta) [C8][C9]. 단가 확인은 0.6에서 한다.
- 실행 환경을 Workers로 정하면 Workers 안에서는 `env.AI` 바인딩으로 호출하므로 REST 토큰이 필요 없을 수 있다 [C9]. 이 토큰은 0.6 확인과 로컬 개발에 쓴다.

### 3.2 확인

토큰 종류에 따라 확인 주소가 다르다 [C2][C6]. 이 확인은 토큰이 활성 상태인지만 보여 준다. Workers AI 권한은 0.6의 첫 추론 호출로 확인한다.

```bash
# 사용자 토큰
( set -a; . ./.env; set +a
  curl -sS -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" https://api.cloudflare.com/client/v4/user/tokens/verify \
    | python3 -c 'import json,sys; r=json.load(sys.stdin); print("cloudflare success =", r["success"], "status =", (r.get("result") or {}).get("status"))' )

# 계정 소유 토큰
( set -a; . ./.env; set +a
  curl -sS -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" "https://api.cloudflare.com/client/v4/accounts/$CLOUDFLARE_ACCOUNT_ID/tokens/verify" \
    | python3 -c 'import json,sys; r=json.load(sys.stdin); print("cloudflare success =", r["success"], "status =", (r.get("result") or {}).get("status"))' )
```

기대 결과는 `success = True status = active`다.

## 4. Discord 애플리케이션·봇

### 4.1 만들 것

Discord Developer Portal에서 애플리케이션을 만들고 봇 사용자를 추가한다. 나오는 값은 다음과 같다.

| 값 | 취급 | 근거 |
| --- | --- | --- |
| Bot Token | 비밀값. 유출되면 바로 재설정한다 | [D1] |
| Client Secret | 비밀값. 이 봇은 OAuth2 사용자 인증을 쓰지 않으므로 만들거나 저장하지 않는다 | [D2] |
| Public Key | HTTP 요청이 Discord에서 왔는지 확인하는 데 쓴다. 비밀값인지에 대한 공식 설명은 미확인이므로 `.env`에 둔다 | [D1] |
| Application ID | 설치 URL에 쓰이지만 Discord 시작 안내가 민감한 값으로 분류하므로 `.env`에 둔다 | [D1][D2] |

- Privileged Gateway Intents(Presence, Server Members, Message Content)는 모두 끈다. 슬래시 명령만 쓰는 봇에는 Message Content 인텐트가 필요 없다 [D8][D9].
- Bot 화면의 Public Bot은 껐다(2026-10-09). 화면 설명에 따르면 끄면 앱 소유자만 봇을 서버에 추가할 수 있다. 이 동작의 공식 문서 근거는 미확인이다.

### 4.2 응답 방식과 필요한 값

| 항목 | 내용 | 근거 |
| --- | --- | --- |
| 명령 수신 | HTTP 인터랙션 엔드포인트와 Gateway 중 하나만 쓴다. HTTP 방식은 상시 연결이 필요 없고, Public Key로 서명을 검증하며 실패하면 401을 돌려줘야 한다 | [D5][D10] |
| 응답 시간 | 첫 응답은 3초 안(지연 응답 type 5). 인터랙션 토큰은 15분 유효하고, 답변은 원래 응답을 수정해 채운다 | [D5] |
| 명령 등록 | Bot Token(또는 `applications.commands.update` 범위의 client credentials 토큰)이 필요하다 | [D3] |

어느 방식으로 받을지는 실행 환경(ADR-008)에 따라 정한다.

### 4.3 서버 설치 범위(이번에는 설치하지 않음)

| 쓰임 | OAuth2 범위 | 봇 권한 | 근거 |
| --- | --- | --- | --- |
| `/ask` 응답만 | `applications.commands` | 없음. 인터랙션 응답은 웹훅으로 처리된다. 채널 권한 검사 여부는 미확인 | [D3][D5][D6] |
| 채널에 요약 게시 | `applications.commands`, `bot` | View Channel, Send Messages. 스레드에 쓰면 Send Messages in Threads. Embed Links 필요 여부는 미확인 | [D2][D4][D7] |

- 헌법은 Discord 쓰기를 답변·요약 게시로 한정한다. 요약 게시가 필요해질 때만 `bot` 범위를 더한다.
- 명령을 쓸 수 있는 채널과 역할은 `default_member_permissions`와 서버 설정의 Integrations 화면에서 제한한다 [D3]. 허용 채널은 QK-BOT-001에서 정한다.

### 4.4 확인

```bash
( set -a; . ./.env; set +a
  curl -sS -o /dev/null -w 'discord users/@me = %{http_code}\n' \
    -A 'DiscordBot (https://github.com/Qello-Labs/qello-knowledge, 0.0.1)' \
    -H "Authorization: Bot $DISCORD_BOT_TOKEN" https://discord.com/api/v10/users/@me )
```

기대 결과는 `200`이다. `GET /users/@me`는 봇 자신의 사용자 정보를, `GET /applications/@me`는 봇이 속한 애플리케이션을 돌려준다 [D11][D12][D13].

## 5. 이번에 발급하지 않는 것

### 5.1 ClickUp 수집 전용 계정(Phase 2 전)

- 개인 API 토큰은 `pk_`로 시작하고 만료되지 않는다 [K1]. 계정이 속한 모든 Workspace에 웹 화면과 같은 권한으로 접근한다 [K2]. 범위를 좁히는 설정은 문서에 없다(RISK-02).
- 그래서 범위는 토큰이 아니라 계정의 접근 범위로 제한해야 한다. 후보는 두 가지다.

| 후보 | 볼 수 있는 범위 | 비용 | 확인할 것 |
| --- | --- | --- | --- |
| Member | 공개 위치 전체를 편집 권한으로 본다 [K5]. 현재 요금제에서는 Doc만 따로 비공개로 할 수 없다(WBS 0.3 보고서 4.2절 C) | Free Forever는 멤버·게스트 무제한 무료. 유료 플랜은 좌석당 과금 [K7][K8] | 요금제 |
| Guest | Space에 초대할 수 없고 공유받은 항목만 본다. 기본으로 개인 API 토큰을 쓸 수 있다 [K3][K4][K5] | 유료 플랜에서는 권한 제어 게스트가 포함 좌석을 넘으면 과금 [K4][K7] | 게스트 토큰으로 Docs API v3를 읽을 수 있는지(미확인). 회사 이메일 도메인 계정은 게스트가 될 수 없다 [K4] |

- Guest에게 사람이 확인한 Doc만 공유하면 0.3 보고서 4.3절의 "사람 검증 허용 목록"을 ClickUp 권한으로 그대로 구현할 수 있다. Phase 2 전에 게스트 토큰으로 Docs를 읽을 수 있는지 먼저 시험한다.
- 0.3 조사에 쓴 Owner 개인 토큰은 수집에 쓰지 않는다. 조사가 끝나면 재발급한다.

### 5.2 DB 읽기 전용 계정(발급 안 함)

인벤토리 3.2절 제안에 따라 DB 스키마는 Flyway 마이그레이션과 데이터 모델 문서로 수집하고 실제 DB에는 연결하지 않는다. 현재 상태 조회가 반복해서 필요해지면 Phase 6 후보(6.2)에서 다시 본다.

### 5.3 Figma 토큰(보류)

팀 회의에서 MVP 자료원에서 Figma를 뺐다(인벤토리 F-14). Figma 수집(QK-ING-008)은 Phase 4 작업이므로 Phase 4 명세를 쓰기 전에 좌석·소유권(RISK-03)과 함께 다시 본다.

## 6. 보관과 교체

| 토큰 | 이름 | `.env` 변수 | 교체 시점 | 유출 시 |
| --- | --- | --- | --- | --- |
| GitHub | `qk-github-read-dev` | `GITHUB_API_TOKEN` | 만료 없음. 발급자가 팀을 떠나거나 권한을 바꿀 때 | GitHub 설정에서 토큰 삭제 후 재발급 |
| Cloudflare(로컬) | `qk-workers-ai-dev` | `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` | TTL을 정했다면 만료 전 | 대시보드에서 토큰 삭제 후 재발급 |
| Cloudflare(서버 예약 색인) | `qk-workers-ai-index-prod` | 서버 `/etc/qello-knowledge/sync.env`(root:qksync, 0640)의 같은 두 변수 | TTL을 정했다면 만료 전 | 대시보드에서 토큰 삭제 후 재발급, 서버 파일을 숨김 입력으로 교체 |
| Discord | 애플리케이션 `Qello Knowledge` | `DISCORD_APPLICATION_ID`, `DISCORD_PUBLIC_KEY`, `DISCORD_BOT_TOKEN` | 정기 교체 없음 | Developer Portal에서 Bot Token 재설정 |

- 토큰 이름은 `qk-<서비스·용도>-<환경>` 형식이다. 지금은 로컬 개발용이라 `dev`로 끝난다. Discord는 애플리케이션 이름이 봇 이름으로 서버에 보이므로 제품 이름을 쓴다.
- 지금은 저장소 루트의 `.env`에만 둔다. `.env`와 `.env.*`는 `.gitignore`에 있다. Claude Code는 `.claude/settings.json`으로, Codex는 `.codex/config.toml` 권한 프로필로 저장소 루트 `.env` 읽기가 막혀 있다. Codex 차단은 샌드박스 안 명령에만 적용되고, 사용자가 승인한 샌드박스 밖 실행, MCP·커넥터, 브라우저에는 적용되지 않는다([하네스 개요](../../harness/OVERVIEW.md)). 하위 폴더의 `.env`도 대상이 아니므로 Codex 작업 폴더에 `.env`를 두지 않는다(WBS 0.3에서 Codex가 하위 폴더 `.env` 토큰을 직접 쓴 사례).
- 실행 환경이 정해지면 그 환경의 비밀값 저장소로 옮긴다. 옮긴 위치는 이 표에 적는다.
- 2026-10-26: Cloudflare 토큰을 Qello 전용 Cloudflare 계정(팀 계정)의 계정 소유 토큰으로 옮겼다(SCRUM-117, #61). 권한은 둘 다 그 계정의 Workers AI만이다. 쓰는 곳마다 토큰을 나눠
  한 곳이 새도 다른 곳을 멈추지 않는다. 질의 서비스용 `qk-workers-ai-query-prod`는 QK-BOT-001 운영 구성 때 같은 계정에 만든다(ADR-022 Proposed). Workers AI 무료 할당(하루 10,000 Neurons)은
  계정 단위라 토큰을 나눠도 함께 쓴다. 같은 모델을 쓰므로 인덱스 버전과 임베딩은 바뀌지 않았다(재색인 없음). 기존 계정의 토큰은 사용자가 지운다.

## 7. 확인 결과

사람이 2~4절의 확인 명령을 실행한 결과다. 상태 코드와 결과 문구만 적는다.

| 토큰 | 확인 명령 | 기대 결과 | 실제 결과 | 확인일 |
| --- | --- | --- | --- | --- |
| GitHub | 2.2 | `github core.limit = 5000` | `github core.limit = 5000` | 2026-10-09 |
| Cloudflare | 3.2 계정 소유 토큰 | `success = True status = active` | `success = True status = active`. 사용자 토큰 주소는 `success = False`로, 토큰 종류가 달라 예상한 결과다 | 2026-10-09 |
| Discord | 4.4 | `discord users/@me = 200` | `discord users/@me = 200` | 2026-10-09 |
| Cloudflare 새 계정 `qk-workers-ai-dev` | 3.2 계정 소유 토큰 | `success = True status = active` | `success = True status = active`(사용자 확인) | 2026-10-26 |
| Cloudflare 새 계정 `qk-workers-ai-index-prod` | 서버 `qksync` 환경에서 모델 조회, 벡터 검색 1회 | HTTP 200, 임베딩 호출 성공 | 모델 조회 HTTP 200. `qk-index search --mode vector --ranks-only` 종료 코드 0, 임베딩 호출 1, `qk-index usage` 질의 0.01 Neurons(측정값). 같은 날 00:30 UTC 예약 실행 `sync-20261026T003032-b9cadf41` succeeded(임베딩 호출 0) | 2026-10-26 |

- 2026-10-26 서버 확인은 Bastion 세션에서 예약 실행과 같은 조건(`qksync` 사용자, `sync.env`, `/opt/qello-knowledge`)으로 했다. 출력에는 토큰 값과 계정 ID가 없다. 서버에서 비밀값 파일 가운데
  토큰 이름이나 계정 소유 토큰 형식(`cfat_`)이 든 파일은 `sync.env` 하나였고(`/opt/qello-knowledge` 복제본의 문서·코드는 이름만), 교체 중 만든 임시 파일은 남지 않았다.
- 사람이 로컬에서 2~4절 명령을 스크립트 하나로 묶어 실행했다. 토큰 종류를 따로 묻지 않으려고 3.2의 두 주소를 모두 호출했다. 출력에는 토큰 값과 계정 ID가 없고, 에이전트는 출력 줄만 봤다.
- 같은 실행에서 `.env`가 git 추적 대상이 아니고 파일 권한이 `-rw-------`인 것을 확인했다.
- 이 확인은 토큰이 유효하다는 것까지만 보여 준다. Workers AI 권한은 0.6의 첫 추론 호출로, 대상 저장소 읽기는 GitHub 수집(QK-ING-002)에서 확인한다.

## 8. 발견한 점·결정할 것

| 번호 | 발견한 점 | 영향 | 넘길 곳 | 필요한 결정 |
| --- | --- | --- | --- | --- |
| T-01 | `scripts/preflight.py`에 GitHub 세분화 토큰(`github_pat_`), ClickUp(`pk_`), Cloudflare 계정 소유 토큰(`cfat_`), Discord 봇 토큰 형식 규칙이 없다. env 형식 규칙도 `DISCORD_BOT_TOKEN`처럼 `BOT_TOKEN`으로 끝나는 이름은 잡지 않는다 | 이 토큰들이 문서·코드에 들어가도 자동 검사에서 빠진다 | 하네스 후속 작업 | 규칙 추가 작업을 만들지 |
| T-02 | 로드맵 0.5 행에 DB 계정과 Figma 토큰이 남아 있다 | 0.G에서 미발급 항목으로 보일 수 있다 | 로드맵 수정 | 인벤토리 F-14와 함께 Phase 4 준비 작업으로 옮길지 |
| T-03 | 실행 환경(ADR-008)에 따라 필요한 값이 달라진다. Workers면 Workers AI는 바인딩으로, Discord는 HTTP 엔드포인트로 받을 가능성이 크다 | 운영에서 쓸 토큰 목록이 바뀔 수 있다 | 0.9 | ADR-008 결정 뒤 이 문서 6절 갱신 |
| T-04 | GitHub 개인 토큰과 Discord 애플리케이션은 발급한 사람에게 묶인다. Cloudflare는 계정 소유 토큰으로 발급해 해당하지 않는다 | 발급자가 팀을 떠나면 수집과 봇이 멈출 수 있다 | 운영 단계 | GitHub App으로 옮길 시점, Discord 애플리케이션 소유를 옮기는 방법 |
| T-05 | ClickUp 개인 토큰은 범위를 정할 수 없고 만료되지 않는다 | 수집 계정의 접근 범위가 곧 토큰의 범위다 | Phase 2 전, QK-SEC-001 | 수집 계정을 Member로 할지 Guest로 할지, 현재 요금제 |
| T-06 | GitHub 토큰을 무기한으로 발급했다. 초안 권장은 366일이었다 | 만료로 자동 정리되지 않아, 쓰지 않게 된 토큰이 남을 수 있다 | 운영 단계(T-04와 함께) | 정기 점검을 둘지, 둔다면 주기 |

## 9. 출처

- G1 https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens
- G2 https://docs.github.com/en/organizations/managing-programmatic-access-to-your-organization/setting-a-personal-access-token-policy-for-your-organization
- G3 https://docs.github.com/en/rest/repos/contents
- G4 https://docs.github.com/en/rest/pulls/pulls
- G5 https://docs.github.com/en/rest/issues/issues
- G6 https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
- G7 https://docs.github.com/en/rest/rate-limit/rate-limit
- G8 https://docs.github.com/en/apps/creating-github-apps/about-creating-github-apps/deciding-when-to-build-a-github-app
- G10 https://docs.github.com/en/apps/using-github-apps/installing-a-github-app-from-a-third-party
- C1 https://developers.cloudflare.com/workers-ai/get-started/rest-api/
- C2 https://developers.cloudflare.com/fundamentals/api/get-started/create-token/
- C3 https://developers.cloudflare.com/fundamentals/api/reference/permissions/
- C4 https://developers.cloudflare.com/fundamentals/api/reference/template/
- C5 https://developers.cloudflare.com/fundamentals/api/how-to/restrict-tokens/
- C6 https://developers.cloudflare.com/api/resources/accounts/subresources/tokens/methods/verify/
- C7 https://developers.cloudflare.com/fundamentals/api/get-started/account-owned-tokens/
- C8 https://developers.cloudflare.com/workers-ai/platform/pricing/
- C9 https://developers.cloudflare.com/workers-ai/models/embeddinggemma-300m/
- D1 https://docs.discord.com/developers/quick-start/getting-started
- D2 https://docs.discord.com/developers/topics/oauth2
- D3 https://docs.discord.com/developers/interactions/application-commands
- D4 https://docs.discord.com/developers/resources/message
- D5 https://docs.discord.com/developers/interactions/receiving-and-responding
- D6 https://docs.discord.com/developers/resources/webhook
- D7 https://docs.discord.com/developers/topics/permissions
- D8 https://docs.discord.com/developers/events/gateway
- D9 https://docs.discord.com/developers/gateway/you-might-not-need-a-privileged-intent
- D10 https://docs.discord.com/developers/interactions/overview
- D11 https://docs.discord.com/developers/resources/user
- D12 https://docs.discord.com/developers/resources/application
- D13 https://docs.discord.com/developers/reference
- K1 https://developer.clickup.com/docs/authentication
- K2 https://help.clickup.com/hc/en-us/articles/6303422883095-Create-your-own-app-with-the-ClickUp-API
- K3 https://help.clickup.com/hc/en-us/articles/26603207201431-Default-user-role-permissions
- K4 https://help.clickup.com/hc/en-us/articles/6310022323991-Guest-type-user-roles
- K5 https://help.clickup.com/hc/en-us/articles/6309266954263-Share-Spaces-Folders-Subfolders-Lists-and-tasks
- K7 https://help.clickup.com/hc/en-us/articles/6303244318999-Pricing-per-user-role-and-plan
- K8 https://clickup.com/pricing
