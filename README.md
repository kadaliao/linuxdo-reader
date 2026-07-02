# linuxdo-reader

Linux.do Reader is a Codex Skill for reading Linux.do hot topics, comments, and
daily discussion trends.

The Skill is the product. The `linuxdo-reader` CLI is the helper underneath it:
it fetches topic lists, hydrates discussion floors, keeps a local SQLite cache,
refreshes your own Linux.do cookies, and renders Markdown digests for the agent
to summarize.

Use it when you want to ask Codex things like:

- 今天 Linux.do 热点在聊什么？
- 总结这个帖子的主贴和评论区分歧。
- 抓今天热门帖子，按主题输出 digest。
- 这个帖显示 134 楼但缓存只有 25 楼，继续往后读。

## One-Command Install

Install the Skill, helper CLI, and Playwright Chromium:

```bash
curl -fsSL https://raw.githubusercontent.com/kadaliao/linuxdo-reader/main/install.sh | bash
```

Install a pinned release:

```bash
curl -fsSL https://raw.githubusercontent.com/kadaliao/linuxdo-reader/main/install.sh | bash -s -- --version v0.1.2
```

The installer requires `uv`. It does not require `git clone`.

If you already installed the helper CLI, you can install or update only the Skill:

```bash
linuxdo-reader install-skill --force
```

Then ask Codex:

```text
Use $linuxdo-reader to crawl today's Linux.do hot topics and summarize the comment discussions.
```

## Install From Codex

If your Codex has the built-in `skill-installer` Skill, you can also ask Codex:

```text
Use $skill-installer to install https://github.com/kadaliao/linuxdo-reader/tree/main/skills/linuxdo-reader
```

That installs the Skill only. You still need the helper CLI for reading Linux.do:

```bash
uv tool install git+https://github.com/kadaliao/linuxdo-reader --with playwright --force
uv tool run playwright install chromium
```

## Personal Login Cookies

Linux.do may block anonymous RSS or JSON requests with Cloudflare/Discourse
checks. For personal reading, let the helper maintain a cookies file from your
own browser session:

```bash
linuxdo-reader auth refresh
```

The first run opens a Playwright Chromium profile. Log in or complete the site
check in that window if needed. The helper saves Linux.do cookies to:

```text
~/.config/linuxdo-reader/cookies.txt
```

Normal commands automatically use this default file. You can also pass a custom
file:

```bash
linuxdo-reader auth refresh --cookies-file ~/.config/linuxdo-reader/cookies.txt
linuxdo-reader --cookies-file ~/.config/linuxdo-reader/cookies.txt crawl --source top --period daily --limit 10 --prefer browser
```

For automation:

```bash
linuxdo-reader auth refresh
linuxdo-reader crawl --source top --period daily --limit 10 --prefer browser
linuxdo-reader digest --limit 10 --comments-per-topic 30
```

Or set:

```bash
export LINUXDO_READER_COOKIES_FILE=~/.config/linuxdo-reader/cookies.txt
```

The helper does not read Chrome or Safari cookie databases directly. It only uses
the cookies file you explicitly configure or refresh through its own Playwright
profile.

## Skill Workflow

The bundled Skill teaches Codex to:

1. Fetch current Linux.do data before summarizing current topics.
2. Use the local SQLite cache as working memory.
3. Distinguish topic metadata from cached comments/floors.
4. Prefer RSS/JSON when available.
5. Use browser-backed reading with your cookies when feeds are blocked.
6. Render summaries from cache instead of repeatedly hitting the site.

The Skill lives here:

```text
skills/linuxdo-reader/SKILL.md
```

## Common Prompts

Daily hot topics:

```text
Use $linuxdo-reader to crawl Linux.do daily hot topics, include cached discussion floors, and produce a concise Chinese digest.
```

One thread:

```text
Use $linuxdo-reader to hydrate https://linux.do/t/topic/2489666 and summarize the main post plus discussion positions.
```

Deeper browser-backed read:

```text
Use $linuxdo-reader with browser-backed hydration to continue reading this Linux.do thread beyond the RSS-visible floors.
```

## Helper CLI

Humans can run the helper directly. Agents should normally follow the Skill
instructions rather than inventing command sequences.

Daily digest:

```bash
linuxdo-reader crawl --source top --period daily --limit 10 --prefer browser
linuxdo-reader digest --limit 10 --comments-per-topic 30
```

Hydrate one topic:

```bash
linuxdo-reader hydrate https://linux.do/t/topic/2489984 --prefer browser
linuxdo-reader topic 2489984
```

Search cached floors:

```bash
linuxdo-reader search GLM --limit 20
```

Every command accepts `-h` and `--help`.

## Access Model

Linux.do access has practical constraints:

- RSS is useful for discovery when available.
- Topic RSS may expose only a recent floor window.
- Anonymous JSON or RSS can be blocked by Cloudflare or Discourse rate limits.
- Browser mode is the normal fallback for personal reading.
- If JSON fails in browser mode, the helper falls back to rendered page text so
  the digest can still include visible discussion content.

If `refresh` or `crawl` cannot fetch daily top topics through RSS, the client
tries both `/top.rss?period=<period>` and `/top/<period>.rss`. With
`--prefer browser`, it can fall back to the rendered `/top?period=<period>` page.

## Repository Layout

```text
skills/linuxdo-reader/        # Codex Skill; the main interface.
src/linuxdo_reader/           # Helper CLI, cache, fetchers, cookie auth, MCP server.
docs/                         # Notes, examples, and implementation plans.
tests/                        # Helper behavior tests.
```

## Local Development

```bash
uv sync
uv run pytest
uv build
```

Run tests in an isolated environment:

```bash
uv run --isolated --with-editable . --with pytest --with respx pytest -q
```

Validate the bundled Skill if you have Codex `skill-creator` locally:

```bash
uv run --with pyyaml python /path/to/skill-creator/scripts/quick_validate.py skills/linuxdo-reader
```

## Optional MCP

MCP is not the main interface. It is only for clients that require a tool server.

```bash
uv run linuxdo-reader-mcp
```

For a client config example, see `docs/mcp-config.example.json`.

## Boundaries

- Use this for personal reading and summarization.
- Do not use it as a training crawler or full-site mirror.
- Cache locally by default.
- Treat "N 个帖子" on Linux.do as Discourse floor/post count, including the main post.
- Run `hydrate` or `crawl` before expecting comments/floors in a digest.
