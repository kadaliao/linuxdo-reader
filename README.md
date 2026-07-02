# linuxdo-reader

`linuxdo-reader` 是一个 Linux.do 阅读 Skill（标准 `SKILL.md` 格式），用来抓取、缓存并总结 Linux.do 的热门帖子、评论区和每日讨论趋势。任何支持 Skill 的 AI 助手（如 Codex、Claude）都能加载它。

这个项目的入口是 **Skill**。`linuxdo-reader` CLI 是 Skill 背后的辅助工具，负责抓帖子列表、读取楼层、维护本地 SQLite 缓存、刷新你自己的 Linux.do cookies，并把内容渲染成 Markdown digest，方便 AI 助手做总结。

你可以这样问你的 AI 助手：

- 今天 Linux.do 热点在聊什么？
- 总结这个帖子的主贴和评论区分歧。
- 抓今天热门帖子，按主题输出 digest。
- 这个帖显示 134 楼但缓存只有 25 楼，继续往后读。

## 一行安装

安装 Skill、辅助 CLI 和 Playwright Chromium：

```bash
curl -fsSL https://raw.githubusercontent.com/kadaliao/linuxdo-reader/main/install.sh | bash
```

安装指定版本：

```bash
curl -fsSL https://raw.githubusercontent.com/kadaliao/linuxdo-reader/main/install.sh | bash -s -- --version v0.1.2
```

安装脚本需要本机已有 `uv`，不需要 `git clone`。

默认把 Skill 装到 Codex 的 `~/.codex/skills/linuxdo-reader`。你可以指定装给哪个助手，或装到当前项目目录：

```bash
# 装给 Claude（~/.claude/skills/linuxdo-reader）
curl -fsSL https://raw.githubusercontent.com/kadaliao/linuxdo-reader/main/install.sh | bash -s -- --agent claude

# 装到当前目录的 ./.claude/skills/linuxdo-reader（项目级 Skill）
curl -fsSL https://raw.githubusercontent.com/kadaliao/linuxdo-reader/main/install.sh | bash -s -- --agent claude --local

# 装到自定义路径
curl -fsSL https://raw.githubusercontent.com/kadaliao/linuxdo-reader/main/install.sh | bash -s -- --dest /path/to/skills/linuxdo-reader
```

如果你已经装好了辅助 CLI，只想安装或更新 Skill：

```bash
linuxdo-reader install-skill --force                    # 默认 Codex
linuxdo-reader install-skill --agent claude --force     # 装给 Claude
linuxdo-reader install-skill --agent claude --local --force  # 装到当前项目 ./.claude/skills
linuxdo-reader install-skill --dest /path/to/skill --force   # 自定义路径
```

`--agent` 目前支持 `codex` 和 `claude`；`--dest` 会覆盖 `--agent`/`--local`。

安装后重启你的 AI 助手，然后直接问：

```text
Use $linuxdo-reader to crawl today's Linux.do hot topics and summarize the comment discussions.
```

## 用支持 Skill 的助手安装

如果你的助手内置了 skill 安装器（例如 Codex 的 `skill-installer`），也可以直接让它安装：

```text
Use $skill-installer to install https://github.com/kadaliao/linuxdo-reader/tree/main/skills/linuxdo-reader
```

这只会安装 Skill。实际读取 Linux.do 仍然需要辅助 CLI：

```bash
uv tool install git+https://github.com/kadaliao/linuxdo-reader --with playwright --force
uv tool run playwright install chromium
```

## 个人登录 Cookies

Linux.do 可能会用 Cloudflare 或 Discourse 机制拦截匿名 RSS/JSON 请求。作为个人阅读工具，推荐让 `linuxdo-reader` 维护你自己的 Linux.do cookies 文件：

```bash
linuxdo-reader auth refresh
```

第一次运行会打开一个 Playwright Chromium profile。如果需要登录或过站点检查，在弹出的浏览器里手动完成即可。工具会把 Linux.do cookies 保存到：

```text
~/.config/linuxdo-reader/cookies.txt
```

普通命令会自动读取这个默认文件。也可以显式指定：

```bash
linuxdo-reader auth refresh --cookies-file ~/.config/linuxdo-reader/cookies.txt
linuxdo-reader --cookies-file ~/.config/linuxdo-reader/cookies.txt crawl --source top --period daily --limit 10 --prefer browser
```

每天自动总结可以这样跑：

```bash
linuxdo-reader auth refresh
linuxdo-reader crawl --source top --period daily --limit 10 --prefer browser
linuxdo-reader digest --limit 10
```

或者设置环境变量：

```bash
export LINUXDO_READER_COOKIES_FILE=~/.config/linuxdo-reader/cookies.txt
```

工具不会直接读取 Chrome 或 Safari 的 cookies 数据库，只会使用你明确配置的 cookies 文件，或者通过自己的 Playwright profile 刷新出来的 cookies。

## Skill 工作流

这个 Skill 会指导 AI 助手按正确方式读 Linux.do：

1. 总结当前热点前，先抓取最新数据。
2. 使用本地 SQLite 缓存作为帖子和楼层的工作记忆。
3. 区分「只缓存了帖子元信息」和「已经缓存了评论/楼层」。
4. RSS/JSON 能用时优先使用它们。
5. Feed 被拦时，用带个人 cookies 的浏览器模式读取。
6. 总结时从缓存渲染 digest，避免反复请求站点。

Skill 文件在这里：

```text
skills/linuxdo-reader/SKILL.md
```

## 常用问法

总结今日热点：

```text
Use $linuxdo-reader to crawl Linux.do daily hot topics, include cached discussion floors, and produce a concise Chinese digest.
```

总结一个帖子：

```text
Use $linuxdo-reader to hydrate https://linux.do/t/topic/2489666 and summarize the main post plus discussion positions.
```

继续深读评论区：

```text
Use $linuxdo-reader with browser-backed hydration to continue reading this Linux.do thread beyond the RSS-visible floors.
```

## 辅助 CLI

人也可以直接运行辅助 CLI。AI 助手通常应该按 Skill 里的说明调用，不要临时发明命令序列。

生成每日 digest：

```bash
linuxdo-reader crawl --source top --period daily --limit 10 --prefer browser
linuxdo-reader digest --limit 10
```

读取一个帖子：

```bash
linuxdo-reader hydrate https://linux.do/t/topic/2489984 --prefer browser
linuxdo-reader topic 2489984
```

搜索已缓存楼层：

```bash
linuxdo-reader search GLM --limit 20
```

所有命令都支持 `-h` 和 `--help`。

## 访问模型

Linux.do 的读取有一些现实约束：

- RSS 可用时适合做列表发现。
- 单帖 RSS 往往只暴露最近一段楼层。
- 匿名 JSON 或 RSS 可能被 Cloudflare 或 Discourse 频控拦截。
- 浏览器模式是个人阅读场景下的正常 fallback。
- 浏览器模式里 JSON 也失败时，工具会退到渲染页面文本，让 digest 至少包含可见评论内容。

如果 `refresh` 或 `crawl` 不能通过 RSS 读取每日热门，客户端会尝试 `/top.rss?period=<period>` 和 `/top/<period>.rss`。使用 `--prefer browser` 时，还可以退到渲染后的 `/top?period=<period>` 页面。

## 仓库结构

```text
skills/linuxdo-reader/        # Skill，主要入口
src/linuxdo_reader/           # 辅助 CLI、缓存、抓取器、cookies 登录
docs/                         # 设计说明、示例和实现计划
tests/                        # 行为测试
```

## 本地开发

```bash
uv sync
uv run pytest
uv build
```

隔离环境跑测试：

```bash
uv run --isolated --with-editable . --with pytest --with respx pytest -q
```

如果本机装了 Codex `skill-creator`，可以校验内置 Skill：

```bash
uv run --with pyyaml python /path/to/skill-creator/scripts/quick_validate.py skills/linuxdo-reader
```

## 边界

- 用于个人阅读和总结。
- 不要拿它做训练数据爬虫或全站镜像。
- 默认只做本地缓存。
- Linux.do 里的「N 个帖子」按 Discourse 楼层/帖子数理解，包含主贴。
- 想让 digest 有评论区内容，需要先运行 `hydrate` 或 `crawl`。
