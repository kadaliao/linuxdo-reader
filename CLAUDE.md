# CLAUDE.md

Guidance for AI assistants working in this repository.

## What this project is

`linuxdo-reader` fetches, caches, and summarizes hot topics and discussion
floors from [Linux.do](https://linux.do) (a Discourse forum). The **product is a
Codex Skill** (`skills/linuxdo-reader/SKILL.md`); the Python package is the
helper tool that Skill drives. When changing behavior, keep the Skill's
documented workflow and the CLI in sync — the Skill tells the agent which
commands to run and how to interpret their output.

There are two runtime entry points into the same core:

- `linuxdo-reader` — the Typer CLI (`linuxdo_reader.cli:app`), the primary one.
- `linuxdo-reader-mcp` — an optional MCP tool server (`linuxdo_reader.mcp_server:main`)
  for clients that need one. Not the main path; keep its tools a thin wrapper
  over the service.

## Architecture

Layered, with one orchestrator in the middle. Entry points stay thin; all logic
lives below `service.py`.

```
cli.py / mcp_server.py     entry points (arg parsing only, thin)
        │
        ▼
service.py  ── LinuxDoService  orchestrates fetch → cache → render
        │
        ├── client.py    httpx: RSS + Discourse JSON endpoints
        ├── browser.py   Playwright fallback (optional dependency, lazy-imported)
        ├── storage.py   Store: SQLite cache (topics, posts)
        ├── digest.py    Markdown rendering (Chinese output)
        ├── feeds.py     RSS/HTML parsing → Topic/Post
        ├── cookies.py   Netscape cookies.txt <-> Playwright cookies
        └── installer.py install-skill (download skill from GitHub tarball)

models.py     frozen dataclasses: Topic, Post
sample_data.py  seed fixtures for the hidden `seed-sample` command
```

### Data flow and the access-fallback chain

Reading Linux.do is unreliable (Cloudflare / Discourse rate limits), so fetching
is a deliberate fallback chain. Preserve this behavior when editing:

- **Topic lists**: `fetch_top` tries `/top.rss?period=<p>` then `/top/<p>.rss`
  (each with a short retry via `_get_with_fallbacks`); `--prefer browser` adds a
  rendered-page fallback in `crawl_top`.
- **Single topic** (`hydrate_topic`): `prefer=json` → Discourse JSON, falling
  back to RSS on error; `prefer=rss` → RSS only; `prefer=browser` → Playwright.
- **Browser mode** (`fetch_topic_posts_with_browser`): opens a real page, runs
  same-origin `fetch` for JSON inside the page, and if that fails falls back to
  scraping rendered page text (`source="browser:page"`). Rendered-text posts are
  visible samples, **not** guaranteed full history — the digest/Skill must say so.

The `source` field on every `Topic`/`Post` records where the data came from
(`json`, `rss`, `browser`, `browser:page`, `top:daily`, etc.). Keep it accurate;
callers and the Skill reason about it.

### Cache model

`Store` is a SQLite cache (`~/.local/share/linuxdo-reader/linuxdo.sqlite` by
default) with two tables:

- `topics` — keyed by `topic_id`; upserts refresh metadata + `updated_at`.
- `posts` — keyed by `(topic_id, post_id)`; the discussion floors.

Key distinction the whole system depends on: **`refresh` caches topic metadata
only; it does not cache floors.** `hydrate`/`crawl` cache posts. "0 cached
floors" means metadata-only, not an error.

## Conventions

- **Python 3.11+** (`.python-version` pins 3.13 for local dev). Managed with
  `uv`; build backend is `uv_build`.
- Every module starts with `from __future__ import annotations`.
- `models.Topic` / `models.Post` are `@dataclass(frozen=True)` — construct new
  instances, don't mutate.
- Private module helpers are prefixed `_` (e.g. `_post_from_json`, `_clip`).
- `Store` and `LinuxDoClient` are context managers (`with Store(path) as store:`).
- **Playwright is optional and lazy-imported** inside functions, never at module
  top level, so the package works without it. Missing-Playwright errors must
  raise `RuntimeError(PLAYWRIGHT_INSTALL_HINT)`.
- Digest/CLI user-facing output is **Chinese**; error prefixes and internal logs
  are English. `digest.py` clips text with `_clip`.
- Cookies are handled only via an explicit Netscape `cookies.txt` (default
  `~/.config/linuxdo-reader/cookies.txt`, env `LINUXDO_READER_COOKIES_FILE`) or a
  Playwright profile the tool controls. Never read the OS browser cookie stores.
- Only `linux.do` / `*.linux.do` cookies are ever loaded or written
  (`_is_linuxdo_domain`).
- The package version lives in **both** `pyproject.toml` and
  `src/linuxdo_reader/__init__.py` (`__version__`). `installer.default_ref()`
  derives the install tag `v<__version__>`, so keep them in sync when bumping.

## Development

```bash
uv sync                 # install deps + dev group (pytest, respx)
uv run pytest           # run the suite
uv run pytest -q        # what CI runs
uv build                # build the package
```

Isolated run (matches how the helper is used as a uv tool):

```bash
uv run --isolated --with-editable . --with pytest --with respx pytest -q
```

Run the CLI from a checkout: `uv run linuxdo-reader <command> -h`.

### Testing

- `pytest` config lives in `pyproject.toml`: `pythonpath = ["src"]`,
  `testpaths = ["tests"]`. Tests import as `linuxdo_reader.*`.
- HTTP is mocked with **`respx`** (`@respx.mock`) — no live network in tests.
- CLI tests use Typer's **`CliRunner`** (`from typer.testing import CliRunner`).
- Shared XML/JSON fixtures live in `tests/fixtures.py`.
- **Playwright/browser code is not exercised in CI.** Browser tests only assert
  pure helpers (`build_topic_url`, `topics_from_browser_rows`) and the
  install-hint path (by monkeypatching `__import__` to fail the playwright
  import). Do not add tests that launch a real browser.
- CI: `.github/workflows/test.yml` runs `uv run pytest -q` on push and PR.

When you add a fetch path, feed format, or CLI flag, add a mocked test and update
`SKILL.md` if it changes the agent-facing workflow.

## Adding a capability end to end

A new read/summarize feature typically touches, in order:

1. `client.py` or `browser.py` — the fetch.
2. `feeds.py` / `models.py` — parsing into `Topic`/`Post`.
3. `storage.py` — persistence, if a new field/table is needed.
4. `service.py` — orchestration on `LinuxDoService`.
5. `cli.py` (and `mcp_server.py` if it should be exposed there) — the command.
6. `digest.py` — rendering, if it shows in a digest.
7. `tests/` — mocked coverage.
8. `skills/linuxdo-reader/SKILL.md` + `README.md` — agent + human docs.

## Scope / boundaries

Personal reading and summarization only. Do not add features to bypass auth,
mint API keys, mirror the whole forum, or build a training-data crawler — the
Skill's safety boundary reflects this and should stay intact.
