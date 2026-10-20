import json

import pytest

from qello_knowledge.adapters.replay import ReplayTransport
from qello_knowledge.devtools import db
from qello_knowledge.devtools.measure import (
    CountingTransport,
    PreparedSource,
    measure_source,
    prepare_source,
    render_measurement,
)
from qello_knowledge.domain.source import SourceRequest, SourceResponse
from qello_knowledge.sources.config import load_sources
from tests.unit.adapters.github_scenarios import COMMIT, Scenario
from tests.unit.fakes import valid_environ
from tests.unit.review_records import write_review
from tests.unit.sources.conftest import FakeClock

TOKEN = "gh" + "p_" + "A" * 36


@pytest.fixture
def paths(tmp_path):
    sources = tmp_path / "sources.toml"
    sources.write_text("""[[source]]
name = "docs"
kind = "github_repo_files"
enabled = true
auth = "GITHUB_API_TOKEN"
allowed_hosts = ["api.github.com"]
[source.scope]
repo = "octo/docs"
ref = "main"
include = ["docs/**/*.md", "README.md"]
exclude = ["docs/private/**"]
""")
    reviews = tmp_path / "reviews"
    configs, issues = load_sources(sources)
    assert not issues
    write_review(configs[0], reviews)
    return sources, reviews, tmp_path / "absent-exceptions.toml"


@pytest.mark.parametrize("failure", ["missing", "mismatch", "extension", "exceptions", "sources"])
def test_preparation_errors_without_transport(paths, failure, monkeypatch):
    monkeypatch.setattr(db, "HttpsTransport", lambda *a, **kw: pytest.fail("전송 생성 금지"))
    sources, reviews, exceptions = paths
    if failure == "missing":
        (reviews / "docs.toml").unlink()
    elif failure == "mismatch":
        path = reviews / "docs.toml"
        path.write_text(path.read_text().replace('"main"', '"different"'))
    elif failure == "extension":
        sources.write_text(sources.read_text().replace('"README.md"', '"**/*.org"'))
    elif failure == "exceptions":
        exceptions.write_text("[[exception]\n")
    else:
        sources.write_text("[[source]\n")
    prepared = prepare_source("docs", sources, reviews, exceptions)
    assert isinstance(prepared, tuple) and prepared


def test_prepared_source_only(paths):
    prepared = prepare_source("docs", *paths)
    assert isinstance(prepared, PreparedSource)
    with pytest.raises(TypeError):
        PreparedSource(prepared.config, prepared.policy)
    with pytest.raises(TypeError):
        measure_source(prepared.config, ReplayTransport([]), FakeClock())


@pytest.mark.parametrize("case", ["normal", "secret", "empty"])
def test_measurement_has_all_fields_and_counts_unique_items_and_blocked_bodies(paths, case):
    prepared = prepare_source("docs", *paths)
    body = ("# Synthetic\n" + TOKEN if case == "secret" else "# Synthetic\n").encode()
    files = [] if case == "empty" else [{"path": "README.md", "body": body}, {"path": "docs/ok.md", "body": b"# OK\n"}]
    scenario = Scenario(files=files)
    measurement = measure_source(prepared, scenario.transport(), FakeClock())
    data = measurement.to_dict()
    assert {
        "commit",
        "visibility",
        "tree_truncated",
        "include",
        "exclude",
        "measured_at",
        "environment",
        "requests",
        "elapsed_seconds",
        "listing_complete",
        "stop",
        "files",
        "bodies_fetched",
        "total_bytes",
        "max_file_bytes",
        "by_verdict",
        "by_rule",
        "blocked",
        "limits",
    } <= data.keys()
    assert data["commit"] == COMMIT and data["visibility"] == "public" and data["tree_truncated"] is False
    assert data["include"] == list(prepared.config.scope.include) and data["exclude"] == list(
        prepared.config.scope.exclude
    )
    assert data["files"] == len(files) == sum(data["by_verdict"].values())
    assert data["bodies_fetched"] == len(files)
    assert data["total_bytes"] == sum(len(file["body"]) for file in files)
    assert data["max_file_bytes"] == max((len(file["body"]) for file in files), default=0)
    assert data["requests"] == 3 + len(files) and data["listing_complete"] and data["stop"] is None
    assert "Python" in data["environment"] and data["measured_at"]
    if case == "secret":
        assert data["by_verdict"]["SECRET_BLOCKED"] == 1
        assert data["blocked"][0]["rule"] == "github-token"
    else:
        assert not data["blocked"]
    for json_output in (False, True):
        output = render_measurement(measurement, json_output=json_output)
        assert TOKEN not in output and "# Synthetic" not in output and "Authorization" not in output
        if json_output:
            assert len(output.splitlines()) == 1 and json.loads(output) == data


def test_counting_transport_counts_only_blob_2xx_and_preserves_response():
    responses = [
        SourceResponse(200, {}, b"123"),
        SourceResponse(200, {}, b"1234"),
        SourceResponse(403, {}, b"error"),
        SourceResponse(206, {}, b"12", True),
    ]

    class Inner:
        def send(self, request):
            return responses.pop(0)

    transport = CountingTransport(Inner())
    for path in ("/repo", "/git/blobs/a", "/git/blobs/b", "/git/blobs/c"):
        expected = responses[0]
        assert transport.send(SourceRequest("GET", "https://api.github.com" + path)) is expected
    assert transport.bodies_fetched == 2 and transport.total_bytes == 6 and transport.max_file_bytes == 4


def cli_args(paths, tmp_path, name="docs"):
    sources, reviews, exceptions = paths
    return [
        "source",
        "measure",
        "--name",
        name,
        "--sources",
        str(sources),
        "--reviews",
        str(reviews),
        "--exceptions",
        str(exceptions),
        "--env-file",
        str(tmp_path / "missing.env"),
        "--json",
    ]


@pytest.fixture
def index_env(monkeypatch):
    for name, value in valid_environ().items():
        monkeypatch.setenv(name, value)


@pytest.mark.parametrize("failure", ["settings", "missing_review", "unknown", "disabled", "kind"])
def test_measure_cli_rejects_before_transport(paths, tmp_path, monkeypatch, index_env, failure):
    monkeypatch.setattr(db, "HttpsTransport", lambda *a, **kw: pytest.fail("전송 생성 금지"))
    sources, reviews, _ = paths
    name = "missing" if failure == "unknown" else "docs"
    if failure == "settings":
        for key in valid_environ():
            monkeypatch.delenv(key, raising=False)
    elif failure == "missing_review":
        (reviews / "docs.toml").unlink()
    elif failure == "disabled":
        sources.write_text(sources.read_text().replace("enabled = true", "enabled = false"))
    elif failure == "kind":
        sources.write_text(
            '[[source]]\nname = "docs"\nkind = "fake"\nenabled = true\n[source.scope]\ninclude = ["**/*.md"]\n'
        )
        configs, _ = load_sources(sources)
        write_review(configs[0], reviews)
    assert db.main(cli_args(paths, tmp_path, name)) == 1


@pytest.mark.parametrize("case,code", [("normal", 0), ("truncated", 1), ("fetch_failure", 1)])
def test_measure_cli_with_replay(paths, tmp_path, monkeypatch, index_env, capsys, case, code):
    scenario = Scenario(files=[{"path": "README.md"}], truncated=case == "truncated")
    if case == "fetch_failure":
        url = next(entry["url"] for entry in scenario.exchanges if "/git/blobs/" in entry["url"])
        scenario.override(url, status=403)
    calls = []

    def create(hosts, token):
        calls.append((hosts, type(token).__name__))
        return scenario.transport()

    monkeypatch.setattr(db, "HttpsTransport", create)
    assert db.main(cli_args(paths, tmp_path)) == code
    output = capsys.readouterr().out
    data = json.loads(output)
    assert data["commit"] == COMMIT and len(output.splitlines()) == 1
    assert calls == [(("api.github.com",), "SecretValue")]


@pytest.mark.parametrize("json_output", [False, True])
def test_measure_cli_missing_token_matches_selected_output_format(
    paths, tmp_path, monkeypatch, index_env, capsys, json_output
):
    from qello_knowledge.config.loader import Settings

    # 설정 점검 뒤의 방어 분기를 직접 확인한다. 전송 생성은 금지한다.
    monkeypatch.setattr(Settings, "get", lambda self, name: None)
    monkeypatch.setattr(db, "HttpsTransport", lambda *a, **kw: pytest.fail("전송 생성 금지"))
    args = cli_args(paths, tmp_path)
    if not json_output:
        args.remove("--json")
    assert db.main(args) == 1
    output = capsys.readouterr().out
    if json_output:
        assert len(output.splitlines()) == 1
        assert json.loads(output) == {"ok": False, "issues": [{"field": "auth", "code": "MISSING"}]}
    else:
        assert output == "자료원 수집 점검: 실패\n  MISSING auth\n"
