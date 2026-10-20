"""합성 GitHub 응답. 실제 원본을 읽거나 저장하지 않는다."""

from copy import deepcopy
from hashlib import sha1
from urllib.parse import quote

from qello_knowledge.adapters.replay import ReplayTransport
from qello_knowledge.sources.session import DefaultSourceSession
from tests.unit.sources.conftest import FakeClock

COMMIT = "a" * 40
TREE = "b" * 40


def blob_sha(body):
    return sha1(b"blob " + str(len(body)).encode() + b"\0" + body, usedforsecurity=False).hexdigest()


class Scenario:
    def __init__(
        self,
        *,
        repo="octo/docs",
        ref="main",
        visibility="public",
        archived=False,
        commit_sha=COMMIT,
        tree_sha=TREE,
        files=(),
        truncated=False,
    ):
        self.repo_url = f"https://api.github.com/repos/{repo}"
        self.commit_url = self.repo_url + "/commits/" + quote(ref, safe="")
        self.tree_url = self.repo_url + f"/git/trees/{tree_sha}?recursive=1"
        self.exchanges = []
        info = {"archived": archived}
        if visibility is not None:
            info["visibility"] = visibility
        self.override(self.repo_url, body=info)
        self.override(self.commit_url, body={"sha": commit_sha, "commit": {"tree": {"sha": tree_sha}}})
        entries = []
        for file in files:
            body = file.get("body", b"# Synthetic\n")
            sha = file.get("sha", blob_sha(body))
            entries.append(
                {
                    "path": file["path"],
                    "mode": file.get("mode", "100644"),
                    "type": file.get("type", "blob"),
                    "sha": sha,
                    "size": len(body),
                }
            )
            if file.get("type", "blob") == "blob":
                self.queue(self.repo_url + "/git/blobs/" + sha, body=body.decode("utf-8"))
        self.override(self.tree_url, body={"truncated": truncated, "tree": entries})

    def override(self, url, status=200, headers=None, body=""):
        self.exchanges = [entry for entry in self.exchanges if entry["url"] != url]
        self.queue(url, status, headers, body)
        return self

    def queue(self, url, status=200, headers=None, body=""):
        self.exchanges.append(
            {"method": "GET", "url": url, "responses": [{"status": status, "headers": headers or {}, "body": body}]}
        )
        return self

    def transport(self):
        return ReplayTransport(deepcopy(self.exchanges))


def session(adapter, transport, config, clock=None, jitter=None):
    return DefaultSourceSession(
        transport, adapter, config, clock or FakeClock(), jitter=jitter or (lambda cap: cap / 2)
    )


def basic_scenario(**kwargs):
    files = [
        {"path": p, "body": f"# Document {i}\n".encode()}
        for i, p in enumerate(("README.md", "docs/a.md", "docs/b.md", "docs/deep/c.md", "docs/d.md"))
    ]
    files += [
        {"path": "docs/run.md", "mode": "100755", "body": b"# Executable\n"},
        {"path": "docs/private/x.md"},
        {"path": "code.java"},
        {"path": "module", "type": "commit", "mode": "160000", "sha": "c" * 40},
        {"path": "docs/link.md", "mode": "120000"},
        {"path": "docs", "type": "tree", "mode": "040000"},
        {"path": "docs/deep", "type": "tree", "mode": "040000"},
    ]
    return Scenario(files=files, **kwargs)
