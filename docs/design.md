# linuxdo-reader Design

## Goal

Build a local tool for reading Linux.do daily hot topics and the discussion below
each topic without manually opening every thread.

## Architecture

- RSS discovery fetches `latest.rss` and `top.rss` to find candidate topics.
- Topic hydration first tries Discourse JSON because it can expose full
  `post_stream.stream` and fetch posts in batches.
- Topic RSS is a fallback because it often returns only recent replies.
- Browser dump is optional and manual for cases where HTTP requests hit
  Cloudflare or the user wants the exact logged-in rendered page.
- SQLite is the durable cache. MCP tools read from or refresh this cache.

## Components

- `linuxdo_reader.client`: HTTP access to RSS, topic JSON, and topic RSS.
- `linuxdo_reader.feeds`: RSS parsing and HTML-to-text cleanup.
- `linuxdo_reader.storage`: SQLite schema and query methods.
- `linuxdo_reader.service`: orchestration layer shared by CLI and MCP.
- `linuxdo_reader.cli`: command-line interface for refresh, hydrate, digest, and
  browser dump.
- `linuxdo_reader.mcp_server`: MCP tools for readers and automations.

## Data Flow

1. `refresh` stores topic metadata from RSS.
2. `hydrate` stores topic comments from JSON or RSS fallback.
3. `digest`, `topic`, and MCP summary tools render from local cache.
4. `search` and `search_cache` query only local SQLite content.

## Boundaries

The tool is for personal reading and summarization. It does not attempt to bypass
site authentication, create API keys, train models, or mirror the whole forum.
