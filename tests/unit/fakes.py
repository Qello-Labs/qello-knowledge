"""형식만 맞춘 가짜 설정 값. 토큰 형식 문자열이 파일에 그대로 남지 않게 실행 중에 이어 붙여 만든다."""

GITHUB_PREFIX = "gh" + "p_"


def valid_environ() -> dict[str, str]:
    scheme = "postgres" + "ql"
    return {
        "DATABASE_URL": f"{scheme}://qk@127.0.0.1:54322/postgres",
        "GITHUB_API_TOKEN": GITHUB_PREFIX + "x" * 36,
        "CLOUDFLARE_API_TOKEN": "c" * 40,
        "CLOUDFLARE_ACCOUNT_ID": "a" * 32,
        "DISCORD_APPLICATION_ID": "1" * 18,
        "DISCORD_PUBLIC_KEY": "f" * 64,
        "DISCORD_BOT_TOKEN": "d" * 60,
    }
