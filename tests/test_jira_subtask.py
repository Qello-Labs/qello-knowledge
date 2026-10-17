"""Unit tests for scripts/jira_subtask.py. Run with: python -m unittest discover -s tests -v"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import jira_subtask as js  # noqa: E402


FIXTURE = json.loads((ROOT / "tests" / "fixtures" / "issue_opened.json").read_text(encoding="utf-8"))
CONFIG = js.Config(jira_base_url="https://example.atlassian.net", jira_email="bot@example.com", jira_token="test")


def parent(subtask: bool = False, sprints: list[dict] | None = None) -> dict:
    return {"key": "SCRUM-42", "fields": {"issuetype": {"subtask": subtask}, "customfield_10020": sprints}}


class FakeJira:
    def __init__(self, issues: dict[str, dict]) -> None:
        self.issues = issues
        self.created: list[dict] = []

    def get_issue(self, key: str) -> dict | None:
        return self.issues.get(key)

    def create_issue(self, payload: dict) -> str:
        self.created.append(payload)
        return "SCRUM-100"


def issue(body_replace: tuple[str, str] | None = None, **overrides) -> dict:
    data = copy.deepcopy(FIXTURE["issue"])
    if body_replace:
        data["body"] = data["body"].replace(*body_replace)
    data.update(overrides)
    return data


ACTIVE = [{"name": "Backend·Sprint 3 (12/10–18/10)", "state": "closed"},
          {"name": "Backend·Sprint 4 (19/10–25/10)", "state": "active"}]


class ParseFormTest(unittest.TestCase):
    def test_reads_sections_and_blank_values(self) -> None:
        sections = js.parse_form(FIXTURE["issue"]["body"])
        self.assertEqual(sections["Jira 상위 이슈 키"], "SCRUM-42")
        self.assertEqual(sections["기존 Jira 이슈 키"], "")
        self.assertEqual(sections["작업 종류"], "feature")
        self.assertIn("제외: 코드 청킹", sections["이번 주 산출물·구현 범위"])

    def test_empty_body(self) -> None:
        self.assertEqual(js.parse_form(""), {})


class ProcessTest(unittest.TestCase):
    def test_creates_subtask_under_parent_with_labels(self) -> None:
        jira = FakeJira({"SCRUM-42": parent(sprints=ACTIVE)})
        result = js.process(issue(), [], jira, CONFIG, dry_run=False)

        self.assertEqual(result.action, "created")
        fields = jira.created[0]["fields"]
        self.assertEqual(fields["parent"], {"key": "SCRUM-42"})
        self.assertEqual(fields["issuetype"], {"name": "Subtask"})
        self.assertEqual(fields["project"], {"key": "SCRUM"})
        self.assertEqual(fields["summary"], "[QK-ING-002] GitHub 저장소 파일 수집")
        self.assertEqual(fields["labels"], ["feature", "team-backend"])
        self.assertIn(FIXTURE["issue"]["html_url"], json.dumps(fields["description"], ensure_ascii=False))

    def test_comment_has_marker_sprint_and_branch(self) -> None:
        jira = FakeJira({"SCRUM-42": parent(sprints=ACTIVE)})
        comment = js.process(issue(), [], jira, CONFIG, dry_run=False).comment

        self.assertIn("<!-- jira-subtask: SCRUM-100 -->", comment)
        self.assertIn("Backend·Sprint 4 (19/10–25/10)", comment)
        self.assertNotIn("Sprint 3", comment)
        self.assertIn("feat/SCRUM-100-gh-99-<short-slug>", comment)
        self.assertIn("https://example.atlassian.net/browse/SCRUM-100", comment)

    def test_warns_when_parent_has_no_active_sprint(self) -> None:
        jira = FakeJira({"SCRUM-42": parent(sprints=[{"name": "Backend·Sprint 3", "state": "closed"}])})
        result = js.process(issue(), [], jira, CONFIG, dry_run=False)

        self.assertEqual(result.action, "created")
        self.assertEqual(len(jira.created), 1)
        self.assertIn("활성 스프린트에 없어", result.comment)

    def test_parent_key_is_normalized(self) -> None:
        jira = FakeJira({"SCRUM-42": parent(sprints=ACTIVE)})
        js.process(issue(body_replace=("\nSCRUM-42\n", "\n scrum-42 \n")), [], jira, CONFIG, dry_run=False)
        self.assertEqual(jira.created[0]["fields"]["parent"], {"key": "SCRUM-42"})

    def test_skips_when_marker_comment_exists(self) -> None:
        jira = FakeJira({"SCRUM-42": parent(sprints=ACTIVE)})
        comments = [{"body": "<!-- jira-subtask: SCRUM-77 -->\n만들었습니다."}]
        result = js.process(issue(), comments, jira, CONFIG, dry_run=False)

        self.assertEqual(result.action, "skipped")
        self.assertEqual(jira.created, [])
        self.assertIsNone(result.comment)

    def test_skips_when_existing_key_given(self) -> None:
        jira = FakeJira({"SCRUM-42": parent(sprints=ACTIVE)})
        body_replace = ("### 기존 Jira 이슈 키\n\n_No response_", "### 기존 Jira 이슈 키\n\nSCRUM-80")
        result = js.process(issue(body_replace=body_replace), [], jira, CONFIG, dry_run=False)

        self.assertEqual(result.action, "skipped")
        self.assertEqual(jira.created, [])

    def test_skips_issue_without_form(self) -> None:
        jira = FakeJira({})
        result = js.process(issue(body="자유 형식 본문"), [], jira, CONFIG, dry_run=False)
        self.assertEqual(result.action, "skipped")
        self.assertIsNone(result.comment)

    def test_skips_outside_author(self) -> None:
        jira = FakeJira({"SCRUM-42": parent(sprints=ACTIVE)})
        result = js.process(issue(author_association="NONE"), [], jira, CONFIG, dry_run=False)
        self.assertEqual(result.action, "skipped")
        self.assertEqual(jira.created, [])

    def test_fails_on_invalid_parent_key(self) -> None:
        jira = FakeJira({})
        result = js.process(issue(body_replace=("\nSCRUM-42\n", "\nQELLO-42\n")), [], jira, CONFIG, dry_run=False)

        self.assertEqual(result.action, "failed")
        self.assertIn("<!-- jira-subtask-failed -->", result.comment)
        self.assertEqual(jira.created, [])

    def test_fails_when_parent_missing(self) -> None:
        result = js.process(issue(), [], FakeJira({}), CONFIG, dry_run=False)
        self.assertEqual(result.action, "failed")
        self.assertIn("찾지 못했습니다", result.comment)

    def test_fails_when_parent_is_subtask(self) -> None:
        jira = FakeJira({"SCRUM-42": parent(subtask=True)})
        result = js.process(issue(), [], jira, CONFIG, dry_run=False)
        self.assertEqual(result.action, "failed")
        self.assertEqual(jira.created, [])

    def test_failed_marker_does_not_block_retry(self) -> None:
        jira = FakeJira({"SCRUM-42": parent(sprints=ACTIVE)})
        comments = [{"body": js.failed_comment("상위 이슈를 찾지 못했습니다.")}]
        result = js.process(issue(), comments, jira, CONFIG, dry_run=False)
        self.assertEqual(result.action, "created")

    def test_dry_run_does_not_create(self) -> None:
        jira = FakeJira({"SCRUM-42": parent(sprints=ACTIVE)})
        result = js.process(issue(), [], jira, CONFIG, dry_run=True)

        self.assertEqual(result.action, "created")
        self.assertEqual(jira.created, [])
        self.assertIsNotNone(result.payload)

    def test_dry_run_without_jira_skips_parent_check(self) -> None:
        result = js.process(issue(), [], None, CONFIG, dry_run=True)
        self.assertEqual(result.action, "created")
        self.assertTrue(result.notes)
        self.assertNotIn("활성 스프린트", result.comment)


class ConfigTest(unittest.TestCase):
    def test_blank_variables_fall_back_to_defaults(self) -> None:
        config = js.Config.from_env({"JIRA_PROJECT_KEY": "", "JIRA_PART_LABEL": "", "JIRA_BASE_URL": "https://x.test/"})
        self.assertEqual(config.project_key, "SCRUM")
        self.assertEqual(config.part_label, "team-backend")
        self.assertEqual(config.jira_base_url, "https://x.test")
        self.assertFalse(config.has_jira())


if __name__ == "__main__":
    unittest.main()
