"""Discord 컴포넌트 값과 순수 표시 함수."""

import re

_PATTERN = re.compile(r"^qk1:(up|down|keep|skip):(q-[0-9]{8}T[0-9]{6}-[0-9a-f]{8})$")


def parse_custom_id(value):
    match = _PATTERN.fullmatch(value) if isinstance(value, str) else None
    return match.groups() if match else None


def custom_id(action, run_id):
    value = f"qk1:{action}:{run_id}"
    if parse_custom_id(value) is None:
        raise ValueError("invalid_component")
    return value


def _buttons(run_id, choices):
    return (
        {
            "type": 1,
            "components": [
                {"type": 2, "style": style, "label": label, "custom_id": custom_id(action, run_id)}
                for action, label, style in choices
            ],
        },
    )


def feedback_buttons(run_id):
    return _buttons(run_id, [("up", "👍", 2), ("down", "👎", 2)])


def consent_buttons(run_id):
    return _buttons(run_id, [("keep", "저장 동의", 1), ("skip", "저장 안 함", 2)])


def consent_text(retain_until):
    return (
        "👎 평가를 남겼습니다.\n이 질문을 답변 개선용으로 저장할까요?\n"
        "- 저장하는 것: 이 질문 하나(답변은 저장하지 않습니다)\n"
        f"- 보관 기간: Phase 2 파일럿 검토까지, 늦어도 {retain_until}\n"
        "- 보는 사람: 운영 담당자(파일럿 분석). 평가 세트로 옮기는 사본은 개인 정보를 지운 별도 사본입니다\n"
        "- 지우기: 운영 담당자에게 삭제를 요청하면 지웁니다"
    )
