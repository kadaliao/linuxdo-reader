# linuxdo-reader Design

## Goal

Provide a Skill for reading Linux.do hot topics and discussion floors without
manually opening every thread. The Skill uses the standard `SKILL.md` format and
works with any agent that supports Skills (Codex, Claude, ...). The CLI is an
execution helper bundled with the Skill, not the primary product surface.

## Architecture

- The Skill tells an agent which reading workflow to run.
- The CLI performs deterministic fetch, cache, search, and render operations.
- RSS discovery fetches `latest.rss` and `top.rss` to find candidate topics.
- Topic hydration first tries Discourse JSON because it can expose full
  `post_stream.stream` and fetch posts in batches.
- Topic RSS is a fallback because it often returns only recent replies.
- Browser-backed hydration is optional for cases where HTTP requests hit
  Cloudflare or the user wants deeper thread context.
- SQLite is the durable cache. Summaries should read from this cache.

## Components

- `skills/linuxdo-reader`: the Skill and its metadata.
- `linuxdo_reader.client`: HTTP access to RSS, topic JSON, and topic RSS.
- `linuxdo_reader.feeds`: RSS parsing and HTML-to-text cleanup.
- `linuxdo_reader.storage`: SQLite schema and query methods.
- `linuxdo_reader.service`: orchestration layer used by the CLI.
- `linuxdo_reader.cli`: helper command for refresh, hydrate, crawl, digest,
  topic, search, and browser dump.

## Data Flow

1. The Skill selects a workflow from the user request.
2. `refresh` stores topic metadata from RSS.
3. `hydrate` stores topic floors from JSON, RSS fallback, or browser mode.
4. `digest` and `topic` render from local cache.
5. `search` queries only local SQLite content.

## Boundaries

The project is for personal reading and summarization. It does not attempt to
bypass site authentication, create API keys, train models, or mirror the whole
forum.
