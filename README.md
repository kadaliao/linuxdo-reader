# linuxdo-reader

A Codex Skill for reading and summarizing Linux.do hot topics and thread
discussions.

The Skill is the product. The `linuxdo-reader` CLI is the helper program the
Skill uses to fetch RSS, hydrate thread floors, cache data locally, and render
Markdown digests.

Use this when you want an agent to answer questions like:

- "今天 Linux.do 热点在聊什么？"
- "帮我总结这个帖子的主贴和评论区分歧。"
- "把今天热门帖子抓下来，按话题给我一个 digest。"
- "为什么这个帖子显示 134 楼但只缓存了 25 楼？继续往后读。"

## Quick Start

Install the helper CLI:

```bash
uv tool install git+https://github.com/kadaliao/linuxdo-reader
```

Install the Skill into Codex:

```bash
git clone https://github.com/kadaliao/linuxdo-reader
mkdir -p ~/.codex/skills
cp -R linuxdo-reader/skills/linuxdo-reader ~/.codex/skills/linuxdo-reader
```

Then ask Codex:

```text
Use $linuxdo-reader to crawl today's Linux.do hot topics and summarize the main discussions.
```

## What The Skill Does

The Skill teaches an agent the correct workflow:

1. Use Linux.do RSS feeds to discover hot or latest topics.
2. Hydrate selected topics into a local SQLite cache.
3. Prefer Discourse JSON when available.
4. Fall back to topic RSS when JSON is blocked.
5. Use browser-backed hydration when the user asks for fuller thread context.
6. Render summaries from local cache instead of repeatedly hitting the site.

This matters because Linux.do access has practical constraints:

- User API keys appear disabled for normal users.
- RSS works well for discovery.
- Topic RSS often exposes only a recent 25-floor window.
- Anonymous JSON can be blocked by Cloudflare.
- Browser mode is the practical fallback when the user wants deeper threads.

## Repository Layout

```text
skills/linuxdo-reader/        # The Codex Skill. This is the main interface.
src/linuxdo_reader/           # Helper CLI, cache, RSS/JSON fetchers, MCP server.
docs/                         # Implementation notes and optional MCP example.
tests/                        # Helper behavior tests.
```

Read the Skill first:

```text
skills/linuxdo-reader/SKILL.md
```

## Agent Usage

Typical prompt:

```text
Use $linuxdo-reader to crawl Linux.do daily hot topics, include cached discussion floors, and produce a concise Chinese digest.
```

For one thread:

```text
Use $linuxdo-reader to hydrate https://linux.do/t/topic/2489666 and summarize the main post plus the discussion positions.
```

For deeper reading when RSS only returns recent floors:

```text
Use $linuxdo-reader with browser-backed hydration to read more floors from this Linux.do thread.
```

## Helper CLI

Humans can run the helper directly. Agents should normally follow the Skill
instructions instead of inventing command sequences.

Daily hot-topic digest:

```bash
linuxdo-reader crawl --source top --period daily --limit 10
linuxdo-reader digest --limit 10 --comments-per-topic 25
```

Same workflow from a cloned development checkout:

```bash
uv run linuxdo-reader crawl --source top --period daily --limit 10
uv run linuxdo-reader digest --limit 10 --comments-per-topic 25
```

Hydrate one topic:

```bash
linuxdo-reader hydrate https://linux.do/t/topic/2489984
linuxdo-reader topic 2489984
```

Use browser-backed hydration from a development checkout:

```bash
uv pip install playwright
uv run playwright install chromium
uv run linuxdo-reader hydrate 2489666 --prefer browser
```

Use browser-backed hydration from a `uv tool` install:

```bash
uv tool install git+https://github.com/kadaliao/linuxdo-reader --with playwright --force
uv tool run playwright install chromium
linuxdo-reader hydrate 2489666 --prefer browser
```

Search cached floors:

```bash
linuxdo-reader search GLM --limit 20
```

Every command accepts `-h` and `--help`.

If `refresh` or `crawl` cannot fetch daily top topics, the client tries both
`/top.rss?period=daily` and `/top/daily.rss` with a short retry. If both fail,
the error lists each attempted feed path; this usually points to a temporary
Linux.do/Cloudflare/TLS path issue rather than an empty cache.

## Local Development

```bash
uv sync
uv run pytest
uv build
```

Validate the bundled Skill:

```bash
uv run --with pyyaml python /path/to/skill-creator/scripts/quick_validate.py skills/linuxdo-reader
```

This validation command is for maintainers who have the Codex `skill-creator`
Skill installed locally.

## Optional MCP

MCP is not the main interface. It is only for clients that require a tool server.

Run the optional server:

```bash
uv run linuxdo-reader-mcp
```

For a client config example, see `docs/mcp-config.example.json`.

## Boundaries

- Use this for personal reading and summarization.
- Do not use it as a training crawler or full-site mirror.
- Cache locally by default.
- Treat "N 个帖子" on Linux.do as Discourse floor/post count, including the main post.
- Run `hydrate` or `crawl` before expecting comment/floor content in a digest.
