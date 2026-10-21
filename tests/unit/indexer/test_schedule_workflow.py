from pathlib import Path


def test_schedule_has_opt_in_read_only_checkout_and_always_cleanup():
    text = Path(".github/workflows/index-sync.yml").read_text()
    for expected in (
        "cron: '30 0 * * *'",
        "workflow_dispatch:",
        "if: vars.QK_SYNC_ENABLED == 'true'",
        "contents: read",
        "group: index-sync",
        "cancel-in-progress: false",
        "timeout-minutes: 30",
        "persist-credentials: false",
        "uv sync --locked --extra index --extra postgres",
        "qk-index run --allow-remote --trigger schedule --json",
        "usage prune --allow-remote",
        "runs prune --allow-remote",
    ):
        assert expected in text
    assert text.count("if: always()") == 2
    for name in ("DATABASE_URL", "QK_GITHUB_API_TOKEN", "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID"):
        assert "secrets." + name in text
    assert "continue-on-error" not in text
