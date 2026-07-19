---
name: linuxdo-reader
description: Use when the user asks an agent to read, crawl, cache, summarize, search, or digest Linux.do topics, hot posts, comments, floors, or daily discussion trends. Trigger for requests like "today's Linux.do hot topics", "summarize this Linux.do thread", "why are cached comments 0", "crawl all floors/comments", or "continue reading beyond the RSS comments".
---

# Linux.do Reader

Use this Skill as the primary interface for Linux.do reading tasks. The
`linuxdo-reader` CLI is the helper tool this Skill drives; do not treat the CLI
as the product.

## Operating Model

- Fetch current data before summarizing current hot topics.
- Use the local SQLite cache as the working memory for topics and floors.
- Explain cache state clearly. `refresh` caches topic metadata only; it does not
  cache comments/floors.
- Use `hydrate` for one topic and `crawl` for a topic list.
- Use `digest`, `topic`, and `search` to read from cache.
- Treat Linux.do/Discourse "N 个帖子" as floor/post count including the main post.
- Do not present RSS output as complete thread history on busy topics.

## Command Runner

Choose the command form from the environment:

- In a cloned `linuxdo-reader` checkout, run `uv run linuxdo-reader ...`.
- If the helper is installed with `uv tool install`, run `linuxdo-reader ...`.
- If no helper command is available, install it:

```bash
curl -fsSL https://raw.githubusercontent.com/kadaliao/linuxdo-reader/main/install.sh | bash
```

Before relying on behavior, check help:

```bash
linuxdo-reader -h
linuxdo-reader digest -h
```

Use `uv run linuxdo-reader -h` instead when working inside the repository.

## Daily Digest Workflow

For a normal daily summary (`digest` already shows up to 50 cached comments per
topic by default, so no flag is needed for a rich summary):

```bash
linuxdo-reader crawl --source top --period daily --limit 10 --prefer browser
linuxdo-reader digest --limit 10
```

For an even deeper daily pass when the user wants maximum floor context:

```bash
linuxdo-reader crawl --source top --period daily --limit 10 --prefer browser
linuxdo-reader digest --limit 10 --comments-per-topic 120
```

If working inside the repository:

```bash
uv run linuxdo-reader crawl --source top --period daily --limit 10
uv run linuxdo-reader digest --limit 10
```

Summarize the digest in Chinese unless the user asks otherwise. Group by topic,
include the thread link, and distinguish the main post from discussion floors.

## Personal Cookies

When RSS or anonymous JSON is blocked, use the user's own Linux.do browser
session instead of stale cache.

Refresh the default cookies file:

```bash
linuxdo-reader auth refresh
```

The first run may open Chromium and require the user to log in or complete a
site check. The helper saves Linux.do cookies to:

```text
~/.config/linuxdo-reader/cookies.txt
```

Normal commands use this file automatically. If the user provides a custom file,
pass it globally:

```bash
linuxdo-reader --cookies-file ~/.config/linuxdo-reader/cookies.txt crawl --source top --period daily --limit 10 --prefer browser
```

You may also use:

```bash
export LINUXDO_READER_COOKIES_FILE=~/.config/linuxdo-reader/cookies.txt
```

If browser mode cannot reach Linux.do and the user has a proxy, pass it with
`--proxy http://HOST:PORT` or set `LINUXDO_READER_PROXY`.

## One Topic Workflow

Cache one thread:

```bash
linuxdo-reader hydrate 2489666
```

Render the cached thread (`topic` renders every cached floor, not a truncated
window):

```bash
linuxdo-reader topic 2489666
```

If the user gives a URL, pass the URL directly:

```bash
linuxdo-reader hydrate https://linux.do/t/topic/2489666
```

## Browser-Backed Reading

Use browser-backed hydration when:

- the user asks for all floors or deeper comments;
- JSON is blocked by Cloudflare;
- RSS only returns a recent window;
- the digest shows fewer cached floors than the topic count implies.

From a development checkout, install browser support and hydrate:

```bash
uv pip install playwright
uv run playwright install chromium
uv run linuxdo-reader hydrate 2489666 --prefer browser
```

From a `uv tool install` setup, reinstall the helper with the optional browser
dependency and install Chromium:

```bash
uv tool install git+https://github.com/kadaliao/linuxdo-reader --with playwright --force
uv tool run playwright install chromium
linuxdo-reader hydrate 2489666 --prefer browser
```

Then render:

```bash
uv run linuxdo-reader topic 2489666
```

If browser mode is not available, say so explicitly and summarize from the
cached/RSS-visible floors only.

If browser JSON fails because of Discourse/Cloudflare limits, the helper may
fall back to rendered page text. Treat those cached posts as visible page
samples, not guaranteed full thread history.

## Search Workflow

Search cached floors:

```bash
linuxdo-reader search GLM --limit 20
```

Use search only for cached data. If the user expects current site-wide results,
run `crawl` or `hydrate` first.

## Interpreting Results

If cached floors are `0`, explain that only topic metadata has been refreshed.
Run `hydrate <topic>` or `crawl`.

`hydrate` fetches JSON in this order: `?print=true`, then plain topic JSON with
chunked `post_ids` pagination (both walk the full floor stream), then RSS as
the last resort. When it had to settle for the RSS window, the CLI prints a
stderr note — relay that limitation instead of presenting the floors as
complete. A partial JSON crawl (pagination interrupted mid-topic) is kept and
cached; it is still much more complete than RSS.

`crawl` does not stop when one topic fails: successful topics report
`<id>: cached N posts` on stdout and failed ones report `<id>: failed (...)` on
stderr. Summarize the successes and mention the failures; rerun later or use
`--prefer browser` for the failed ones. `--delay` (default 0.5s) spaces out
per-topic requests to ease rate limits.

If a topic shows 134 floors but only 25 are cached, explain that RSS likely
returned a recent window and anonymous JSON may have been blocked. Use
`--prefer browser` when feasible.

`digest` orders topics by the most recent refresh batch first (hottest first
within the batch), so run `refresh`/`crawl` before digesting to get today's
list rather than previously cached days.

If `refresh` or `crawl --source top` fails, note that the helper tries both
`/top.rss?period=<period>` and `/top/<period>.rss` with a short retry. If both
paths fail, summarize the attempted paths from the error and treat it as a
temporary Linux.do/Cloudflare/TLS access issue; do not summarize stale cache as
current hot topics.

## Safety Boundary

Use this for personal reading and summarization. Do not attempt to create API
keys, bypass authentication, mirror the whole forum, or build a training data
crawler.
