"""형식만 맞춘 합성 비밀값. 토큰 형식 문자열이 파일에 그대로 남지 않게 실행 중에 이어 붙여 만든다(QK-SEC-001 R-12)."""

SYNTHETIC = {
    "github-classic": "gh" + "p_" + "A" * 36,
    "github-fine-grained": "github" + "_pat_" + "11AB" + "c" * 70,
    "cloudflare-account": "cf" + "at_" + "Z" * 40,
    "discord-bot": "M" + "T" * 23 + "." + "Gh" + "x" * 4 + "." + "y" * 38,
    "clickup": "p" + "k_" + "1234567" + "_" + "Q" * 32,
    "anthropic": "sk-" + "ant-" + "a" * 30,
    "openai": "sk-" + "proj-" + "a" * 40,
    "atlassian": "ATA" + "TT" + "a" * 30,
    "figma": "fi" + "gd_" + "a" * 36,
    "notion": "nt" + "n_" + "a" * 44,
    "slack": "xo" + "xb-" + "1" * 24,
    "aws": "AK" + "IA" + "A" * 16,
    "private-key": "-----BEGIN " + "OPENSSH PRIVATE KEY-----",
    "db-url": "postgres" + "ql://svc:" + "s3cretvalue" + "@db.example:5432/app",
}
