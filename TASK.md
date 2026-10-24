# Task Contract: 운영 예약 실행 켜기 결과 기록 (QK-SYN-001 사람 단계 H07 후속)

> Generated at: `2026-10-24`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-103` / https://tkv123.atlassian.net/browse/SCRUM-103 (상위 `SCRUM-42` 팀 RAG 구축)
- 기능명세서 ID / 링크: 해당 없음: 운영 구성 작업이다. QK-SYN-001 사람 단계 H05·H07(`specs/QK-SYN-001-incremental-sync/quickstart.md` 3절)의 병합 뒤 결과 기록
- 팀 스프린트 ID: `QELLO-S2026-W43`
- GitHub Issue: 해당 없음. `#50`은 PR #55 병합으로 닫혔다. 이 작업은 #55 계약의 경계 문단("병합 뒤 운영 검증, 결과는 후속 PR로 기록")을 따른다
- Branch: `docs/SCRUM-103-h07-sync-timer-record`
- Base branch: `main`. 2026-10-24 `origin/main` `59132b2`(#55 병합)에서 분기했다
- 이전 계약: `59132b2`의 `TASK.md`(운영 저장소 OCI 구성·H04~H07). 그 Decisions 기록은 git 이력에 남긴다

## Objective

- PR #55 병합 뒤 운영 검증(0006 적용, 수동 1회 실행, 잠금 시험, 타이머 켜기)과 첫 예약 실행 결과를 기록한다.
- 병합으로 끝난 승인(ADR-008·ADR-020, H04)을 결정 기록과 tasks.md에 반영한다.
- 운영 문서에 "새 마이그레이션은 그 코드가 `main`에 들어가기 전에 운영 DB에 적용한다"는 규칙을 더한다(0006에서 드러남).

## Scope

- `TASK.md`
- `specs/QK-SYN-001-incremental-sync/tasks.md`: H04·H05·H07 결과 기록과 체크
- `docs/ops/oci-production-store.md`: 마이그레이션 순서 규칙, 켜기 결과
- `docs/sdd/decisions/ADR-008-runtime-and-cost-cap.md`, `docs/sdd/decisions/ADR-020-scheduled-sync-systemd-timer.md`: Status·Approval만(PR #55 리뷰 승인)
- OCI 인스턴스 읽기 전용 확인(예약 실행 결과). 사람이 인증하고 승인한 명령만

## Explicit exclusions

- `src/`·`tests/`·`pyproject.toml`·`uv.lock`·마이그레이션·`.github/workflows/` 변경. `index-sync.yml` 삭제·수정, 실패 알림, 미리 보기 예상식 보정(QK-EMB-001 후속)은 별도 작업이다.
- 서버 유닛·스크립트·비밀값 파일·DB 컨테이너 변경. 타이머 끄기는 실행 실패로 회의 봇에 영향이 있을 때만 사람 승인 뒤 한다.
- `AGENTS.md`, `CLAUDE.md`, `.claude/**`, constitution, 로드맵 수정. 원본 자료원에 쓰기.
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 접속 주소, OCI 계정 식별자(OCID·테넌시·지문), 비공개 원문은 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: 해당 없음(기존 `dnd-backend-docs`)
- 외부 API로 보내는 데이터: 예약 실행이 바뀐 문서의 청크만 Workers AI bge-m3로 보낸다(기존 경로, ADR-020)
- 예상 임베딩·생성 호출량과 무료 한도 대비: 원본이 바뀌지 않은 날 0. 2026-10-23 수동 실행 0 Neurons. 최악(전체 색인) 약 900, 하루 무료 10,000 안
- 인덱스 버전 변경: 없음(`iv-4c0bc4fcc642` 유지)

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `TASK.md`, `specs/QK-SYN-001-incremental-sync/tasks.md` 사람 단계 기록 | Byuntil | 사람 리뷰 |
| `docs/ops/oci-production-store.md` | Byuntil | 사람 리뷰 |
| `docs/sdd/decisions/ADR-008-*.md`, `ADR-020-*.md`의 Status·Approval | Byuntil | 사람 리뷰 |

## Existing user-owned changes

- 2026-10-24 `origin/main`(`59132b2`)에서 브랜치 생성 시 `git status --short` 결과: 변경 없음

## Validation

```bash
python scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
```

운영 확인(사람 인증 뒤, 읽기 전용): Bastion 세션으로 `systemctl list-timers qk-sync.timer`, `journalctl -u qk-sync.service`, 터널로 `qk-index runs list --json`·`qk-index index status --json`·`qk-index usage --json`.

## Completion criteria

- 서버 systemd 타이머의 예약 실행 1회가 성공한다(ADR-020) — `journalctl -u qk-sync.service`, `qk-index runs list`의 2026-10-24 00:30 UTC 무렵 `trigger=schedule` 실행 기록
- 병합 뒤 운영 검증(0006, 수동 실행, 잠금 시험, 타이머 켜기)과 승인이 tasks.md·결정 기록에 남는다 — 이 PR 리뷰

## Decisions

- 2026-10-23 사실: PR #55를 리뷰어(팀원)가 승인(APPROVED, 15:13 UTC)했고 사용자가 병합했다(15:16 UTC, `59132b2`). `#50`이 닫혔다.
- 2026-10-23 사실(읽기 전용): `main`에 #54가 함께 들어와 마이그레이션 `0006_generation_usage`가 생겼다. `qk-index usage prune`이 생성 사용량도 정리하므로(`qk.generation_usage_prune`) 0006이 없으면 서버 스크립트의 정리 단계가 실패한다. 의존성(`pyproject.toml`·`uv.lock`)과 청킹·임베딩·필터 코드는 그대로다.
- 2026-10-23 사실(사용자 승인 명령, Herdr 오른쪽 패널): 첫 Bastion 세션 생성 시도는 OCI CLI가 보이지 않는 대화형 입력을 기다려 `oci bastion bastion get`에서 멈췄고(10분, 변경 없음) Ctrl+C로 끊었다. 사용자가 다시 인증한 뒤 세션 `qk-h07`(3시간)을 만들었다(허용 IP 변경 없음).
- 2026-10-23 사실(사용자 승인 명령, 터널 경유): 운영 DB에 0006 적용. dry-run `pending 0006 generation_usage`만 → `applied=1 skipped=5` → 재실행 `applied=0 skipped=6`.
- 2026-10-23 사실(사용자 승인 명령, Bastion 세션): `sudo systemctl start qk-sync.service` 1회. 복제본 `4c66ff6`→`59132b2`, `sync-20261023T155324-1bbd7bfc` succeeded(`trigger=schedule`, `target=remote`, `iv-4c0bc4fcc642` 활성):
  문서 80 처리(UNCHANGED 79·SKIP 1), GitHub 요청 83, 임베딩 요청 0·제공자 호출 0·0 Neurons, 보류·실패 없음. 정리 단계(임베딩·생성 사용량, 실행 기록) 모두 0건으로 성공. `Result=success`, 종료 코드 0, 색인 약 68초.
  스크립트가 `--trigger schedule`을 고정하므로 수동 실행도 `schedule`로 기록된다. 예약 실행과는 시작 시각으로 구분한다.
- 2026-10-23 사실(사용자 승인, 위 실행 중): 잠금 시험. 첫 실행이 advisory lock을 잡은 것(`pg_locks` granted 2)을 본 뒤 `systemd-run`으로 `qksync` 사용자의 두 번째 `qk-index run --allow-remote --trigger manual`을 띄웠다.
  결과 `{"reason": "already_running", "status": "stopped", "exit_code": 6}`, 실행 기록 없음. 첫 실행은 영향 없이 성공했다.
- 2026-10-23 사실(사용자 승인 명령, 터널 경유, 읽기 전용): `index status` active=current=`iv-4c0bc4fcc642`, `matches=true`. `runs list` 3건 succeeded(schedule 1, manual 2). `usage` 2026-10-23 색인 894.50(첫 색인분), 남은 색인 예산 4,105.5.
- 2026-10-23 사실(사용자 승인 명령, Bastion 세션): 마지막 실행 성공을 확인하고 `sudo systemctl enable --now qk-sync.timer`. `enabled / active`, 다음 실행 `Sat 2026-10-24 00:30:00 UTC`(LAST n/a, 켤 때 바로 돌지 않음).
- 2026-10-24 사용자 결정: 후속 기록 PR 브랜치를 만들어 예약 실행 확인 전 기록을 먼저 한다.
- 2026-10-24 사용자 결정: 이 계약과 기록 초안(ADR-008·ADR-020 Status·Approval 포함)을 승인했다. 지금 기록을 커밋하고, 예약 실행 확인 뒤 H07 체크 커밋을 더해 PR을 올린다.
- 2026-10-24 사실(사용자 재인증 뒤 승인 명령, Herdr 오른쪽 패널, 읽기 전용): 첫 재인증은 `qello-team` 프로필에 들어가지 않아(`session validate`: expired) 세션 생성이 `Abort:`로 끝났다(변경 없음).
  다시 인증한 뒤 Bastion 세션 `qk-h07-check`로 확인했다. 타이머 LAST `2026-10-24 00:30:31 UTC`, NEXT `2026-10-25 00:30:00 UTC`.
  예약 실행 `sync-20261024T003032-be5aa192` succeeded(`trigger=schedule`): UNCHANGED 79·SKIP 1, 제공자 호출 0, 0 Neurons, 정리 단계 성공, `Result=success`·종료 코드 0.
  터널로 `index status` matches=true, `runs list` 4건 succeeded, `usage` 2026-10-24 0. 실행 뒤 `qk-postgres` 261 MiB, 호스트 가용 4.4 GiB. 완료 조건 첫째를 충족했다.
