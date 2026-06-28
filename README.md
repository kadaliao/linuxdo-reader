# linuxdo-agent

Agent-friendly Linux.do hot-topic and discussion cache.

`linuxdo-agent` helps an agent answer questions like:

- "今天 linux.do 热点在聊什么？"
- "这个帖子评论区主要站哪几派？"
- "只看我本地缓存里和 GLM / Gemini / 福利站有关的讨论。"

It uses public RSS feeds for topic discovery, then tries Discourse topic JSON for
full discussion hydration. If JSON is blocked by Cloudflare, it falls back to
topic RSS. A browser dump command is available for manual, logged-in reading.

## Why This Shape

Linux.do exposes useful Discourse RSS feeds:

- `https://linux.do/latest.rss`
- `https://linux.do/top.rss?period=daily`

Topic RSS can expose recent comments, but it usually returns a rolling window
rather than the full thread. For full discussion summaries, this tool tries:

1. `/t/-/<topic_id>.json?print=true`
2. `/t/<topic_id>/posts.json?post_ids[]=...`
3. `/t/topic/<topic_id>.rss`
4. Optional browser dump for pages that need a real browser session

The default mode is conservative: cache what you read, avoid repeated requests,
and keep search local.

## Install

```bash
uv tool install git+https://github.com/<owner>/linuxdo-agent
```

For local development:

```bash
uv sync
uv run pytest
```

## CLI

Refresh hot topics:

```bash
uv run linuxdo-agent refresh --source top --period daily --limit 20
```

Refresh latest topics:

```bash
uv run linuxdo-agent refresh --source latest --limit 20
```

Hydrate a topic discussion:

```bash
uv run linuxdo-agent hydrate https://linux.do/t/topic/2489984
```

Generate a cached digest:

```bash
uv run linuxdo-agent digest --limit 10 --output outputs/linuxdo-digest.md
```

Search cached comments:

```bash
uv run linuxdo-agent search GLM --limit 20
```

Use browser mode when HTTP API is blocked:

```bash
uv pip install playwright
uv run playwright install chromium
uv run linuxdo-agent browser-dump https://linux.do/t/topic/2489984 --output outputs/topic.txt
```

## MCP

Run the MCP server:

```bash
uv run linuxdo-agent-mcp
```

Optional cache path:

```bash
LINUXDO_AGENT_DB=/path/to/linuxdo.sqlite uv run linuxdo-agent-mcp
```

Tools exposed:

- `refresh_hot_topics(period="daily", limit=20)`
- `refresh_latest_topics(limit=20)`
- `hydrate_topic(topic, prefer="json")`
- `summarize_topic(topic)`
- `daily_digest(limit=10)`
- `search_cache(query, limit=20)`

For a client config example, see `docs/mcp-config.example.json`.

## Automation

Run a light background refresh every hour, then ask your agent for summaries from
the local cache:

```bash
uv run linuxdo-agent refresh --source top --period daily --limit 20
uv run linuxdo-agent hydrate 2489984
uv run linuxdo-agent digest --output outputs/linuxdo-daily.md
```

## Notes

- User API Key authorization appears disabled for normal linux.do users.
- RSS is reliable for discovery. Topic JSON is best-effort and may be challenged.
- Do not use this as a training crawler or full-site mirror.
- The project intentionally stores only a local SQLite cache by default.
