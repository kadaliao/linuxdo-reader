# Cookie Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let linuxdo-reader use and refresh the user's own Linux.do cookies for personal reading.

**Architecture:** Add a small cookie utility that reads/writes Netscape cookies.txt. Thread an optional cookies file through the CLI into `LinuxDoClient` and Playwright browser contexts. Add `auth login` and `auth refresh` commands that use a persistent Playwright profile, open Linux.do for the user to complete login/challenge, then export cookies to the configured file.

**Tech Stack:** Python, Typer, httpx, Playwright, pytest/respx.

---

### Task 1: Cookie file utility

**Files:**
- Create: `src/linuxdo_reader/cookies.py`
- Test: `tests/test_cookies.py`

- [ ] Write tests for reading Netscape cookies.txt and filtering `linux.do`.
- [ ] Implement `default_cookies_file`, `load_cookie_jar`, and `write_netscape_cookies`.
- [ ] Verify malformed or missing files are handled predictably.

### Task 2: HTTP client cookie support

**Files:**
- Modify: `src/linuxdo_reader/client.py`
- Modify: `src/linuxdo_reader/service.py`
- Modify: `src/linuxdo_reader/cli.py`
- Test: `tests/test_client.py`
- Test: `tests/test_cli.py`

- [ ] Add a `cookies_file` option to `LinuxDoClient`.
- [ ] Add a global `--cookies-file` CLI option and `LINUXDO_READER_COOKIES_FILE` fallback.
- [ ] Verify requests include cookies from the configured file.

### Task 3: Browser auth commands

**Files:**
- Modify: `src/linuxdo_reader/browser.py`
- Modify: `src/linuxdo_reader/cli.py`
- Test: `tests/test_browser.py`
- Test: `tests/test_cli.py`

- [ ] Add `auth login` and `auth refresh`.
- [ ] Use Playwright persistent context under `~/.local/share/linuxdo-reader/browser-profile`.
- [ ] Export `linux.do` cookies to cookies.txt after navigation.
- [ ] Keep browser install/challenge failures as clear CLI errors.

### Task 4: Verification

**Files:**
- No new files.

- [ ] Run `uv run --isolated --with-editable . --with pytest --with respx pytest -q`.
- [ ] Run `linuxdo-reader auth refresh --cookies-file <temp>` in source checkout when Playwright is available.
- [ ] Run `crawl --prefer browser` with the cookies file and confirm it caches current topics.
