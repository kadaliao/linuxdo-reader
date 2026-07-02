from linuxdo_reader.cookies import (
    load_cookie_jar,
    load_playwright_cookies,
    write_netscape_cookies,
)


def test_load_cookie_jar_reads_linuxdo_netscape_cookies(tmp_path) -> None:
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(
        "\n".join(
            [
                "# Netscape HTTP Cookie File",
                ".linux.do\tTRUE\t/\tTRUE\t2147483647\t_cf_bm\tabc",
                "example.com\tFALSE\t/\tFALSE\t2147483647\tignored\tnope",
                "linux.do\tFALSE\t/\tTRUE\t2147483647\t_session\txyz",
            ]
        ),
        encoding="utf-8",
    )

    jar = load_cookie_jar(cookies_file)

    assert jar.get("_cf_bm", domain=".linux.do") == "abc"
    assert jar.get("_session", domain="linux.do") == "xyz"
    assert jar.get("ignored", domain="example.com") is None


def test_write_netscape_cookies_round_trips_linuxdo_cookies(tmp_path) -> None:
    cookies_file = tmp_path / "cookies.txt"

    write_netscape_cookies(
        cookies_file,
        [
            {
                "name": "_forum_session",
                "value": "secret",
                "domain": ".linux.do",
                "path": "/",
                "expires": 2147483647,
                "secure": True,
                "httpOnly": True,
            },
            {
                "name": "other",
                "value": "ignored",
                "domain": ".example.com",
                "path": "/",
            },
        ],
    )

    jar = load_cookie_jar(cookies_file)

    assert jar.get("_forum_session", domain=".linux.do") == "secret"
    assert jar.get("other", domain=".example.com") is None


def test_load_playwright_cookies_reads_linuxdo_cookies(tmp_path) -> None:
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(
        "# Netscape HTTP Cookie File\n"
        ".linux.do\tTRUE\t/\tTRUE\t2147483647\t_cf_bm\tabc\n",
        encoding="utf-8",
    )

    cookies = load_playwright_cookies(cookies_file)

    assert cookies == [
        {
            "name": "_cf_bm",
            "value": "abc",
            "domain": ".linux.do",
            "path": "/",
            "expires": 2147483647,
            "httpOnly": False,
            "secure": True,
            "sameSite": "Lax",
        }
    ]
