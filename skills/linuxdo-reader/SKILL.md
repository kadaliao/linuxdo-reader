---
name: linuxdo-reader
description: Use when the user asks to read, crawl, cache, summarize, or search Linux.do topics, hot posts, comments, floors, or daily discussion trends using the linuxdo-reader CLI. Trigger for questions like "today's linux.do hot topics", "summarize this linux.do thread", "why are cached comments 0", or "crawl all floors/comments".
---

# Linux.do Reader

Use the `linuxdo-reader` CLI as the source of truth. The skill is a workflow guide;
it does not replace the CLI.

## Core Model

- `refresh` caches topic metadata only. It does not cache floors/comments.
- Linux.do/Discourse "N 个帖子" means N floors/posts including the main post.
- `hydrate` caches floors for one topic.
- `crawl` refreshes a topic list and hydrates each topic.
- `digest` reads local SQLite cache and prints Markdown by default.
- Normal JSON may be blocked by Cloudflare. Then `hydrate` falls back to topic RSS,
  which usually returns only a recent 25-floor window.
- Use `--prefer browser` when the user wants the most complete thread.

## First Checks

Run help before assuming behavior:

```bash
uv run linuxdo-reader -h
uv run linuxdo-reader digest -h
```

If commands cannot import the package in local development, run:

```bash
uv sync --reinstall-package linuxdo-reader
```

On macOS only, if `.pth` files are skipped as hidden, clear the local venv flag:

```bash
chflags -R nohidden .venv
```

## Common Workflows

Refresh hot topic metadata:

```bash
uv run linuxdo-reader refresh --source top --period daily --limit 20
```

Cache floors for one topic:

```bash
uv run linuxdo-reader hydrate 2489666
```

Try full browser-backed hydration:

```bash
uv pip install playwright
uv run playwright install chromium
uv run linuxdo-reader hydrate 2489666 --prefer browser
```

Crawl and hydrate hot topics:

```bash
uv run linuxdo-reader crawl --source top --period daily --limit 10
```

Browser-backed crawl:

```bash
uv run linuxdo-reader crawl --source top --period daily --limit 10 --prefer browser
```

Print digest to stdout:

```bash
uv run linuxdo-reader digest --limit 10 --comments-per-topic 25
```

Write digest to a file:

```bash
uv run linuxdo-reader digest --limit 10 --output outputs/linuxdo-digest.md
```

Search cached floors:

```bash
uv run linuxdo-reader search GLM --limit 20
```

## Answering User Confusion

If a digest says cached floors are `0`, explain that only topic metadata has been
refreshed. Tell the user to run `hydrate <topic>` or `crawl`.

If a topic has 134 floors but only 25 cached, explain that anonymous JSON was
blocked and RSS only returned a recent window. Recommend `--prefer browser`.

If the user asks what MCP is for, say it is optional. The CLI is the main
capability; this skill is the preferred agent integration because it teaches the
agent when and how to invoke the CLI correctly.
