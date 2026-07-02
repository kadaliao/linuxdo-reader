from __future__ import annotations

from http.cookiejar import Cookie, LoadError, MozillaCookieJar
from pathlib import Path
from typing import Any

import httpx

LINUXDO_DOMAINS = ("linux.do", ".linux.do")


def default_cookies_file() -> Path:
    return Path.home() / ".config" / "linuxdo-reader" / "cookies.txt"


def default_browser_profile_dir() -> Path:
    return Path.home() / ".local" / "share" / "linuxdo-reader" / "browser-profile"


def load_cookie_jar(path: str | Path | None) -> httpx.Cookies | None:
    if path is None:
        return None
    cookie_path = Path(path).expanduser()
    if not cookie_path.exists():
        return None
    jar = MozillaCookieJar(str(cookie_path))
    try:
        jar.load(ignore_discard=True, ignore_expires=True)
    except LoadError as exc:
        raise RuntimeError(f"Invalid cookies file {cookie_path}: {exc}") from exc
    filtered = httpx.Cookies()
    for cookie in jar:
        if _is_linuxdo_domain(cookie.domain):
            filtered.set(cookie.name, cookie.value, domain=cookie.domain, path=cookie.path)
    return filtered


def write_netscape_cookies(path: str | Path, cookies: list[dict[str, Any]]) -> Path:
    cookie_path = Path(path).expanduser()
    cookie_path.parent.mkdir(parents=True, exist_ok=True)
    jar = MozillaCookieJar(str(cookie_path))
    for item in cookies:
        domain = str(item.get("domain") or "")
        if not _is_linuxdo_domain(domain):
            continue
        jar.set_cookie(_cookie_from_playwright(item))
    jar.save(ignore_discard=True, ignore_expires=True)
    return cookie_path


def load_playwright_cookies(path: str | Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    cookie_path = Path(path).expanduser()
    if not cookie_path.exists():
        return []
    cookies: list[dict[str, Any]] = []
    for line in cookie_path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_netscape_line(line)
        if parsed is None:
            continue
        domain, _include_subdomains, path_value, secure, expires, name, value, http_only = parsed
        if not _is_linuxdo_domain(domain):
            continue
        cookies.append(
            {
                "name": name,
                "value": value,
                "domain": domain,
                "path": path_value,
                "expires": expires,
                "httpOnly": http_only,
                "secure": secure,
                "sameSite": "Lax",
            }
        )
    return cookies


def _is_linuxdo_domain(domain: str) -> bool:
    normalized = domain.lower().lstrip(".")
    return normalized == "linux.do" or normalized.endswith(".linux.do")


def _cookie_from_playwright(item: dict[str, Any]) -> Cookie:
    domain = str(item.get("domain") or "linux.do")
    path = str(item.get("path") or "/")
    expires_value = item.get("expires")
    expires = int(expires_value) if isinstance(expires_value, int | float) and expires_value > 0 else None
    return Cookie(
        version=0,
        name=str(item.get("name") or ""),
        value=str(item.get("value") or ""),
        port=None,
        port_specified=False,
        domain=domain,
        domain_specified=domain.startswith("."),
        domain_initial_dot=domain.startswith("."),
        path=path,
        path_specified=True,
        secure=bool(item.get("secure")),
        expires=expires,
        discard=expires is None,
        comment=None,
        comment_url=None,
        rest={"HttpOnly": None} if item.get("httpOnly") else {},
        rfc2109=False,
    )


def _parse_netscape_line(
    line: str,
) -> tuple[str, bool, str, bool, int, str, str, bool] | None:
    if not line.strip() or line.startswith("# Netscape"):
        return None
    http_only = False
    if line.startswith("#HttpOnly_"):
        http_only = True
        line = line.removeprefix("#HttpOnly_")
    elif line.startswith("#"):
        return None
    parts = line.split("\t")
    if len(parts) != 7:
        return None
    domain, include_subdomains, path, secure, expires, name, value = parts
    try:
        expires_int = int(expires)
    except ValueError:
        expires_int = -1
    return (
        domain,
        include_subdomains.upper() == "TRUE",
        path,
        secure.upper() == "TRUE",
        expires_int,
        name,
        value,
        http_only,
    )
