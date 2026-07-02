#!/usr/bin/env sh
set -eu

REPO="kadaliao/linuxdo-reader"
REF="main"
DEST=""
AGENT=""
LOCAL=0
INSTALL_BROWSER=1

usage() {
  cat <<'EOF'
Install linuxdo-reader and its Skill.

Usage:
  curl -fsSL https://raw.githubusercontent.com/kadaliao/linuxdo-reader/main/install.sh | bash
  curl -fsSL https://raw.githubusercontent.com/kadaliao/linuxdo-reader/main/install.sh | bash -s -- --agent claude
  curl -fsSL https://raw.githubusercontent.com/kadaliao/linuxdo-reader/main/install.sh | bash -s -- --version v0.1.2

Options:
  --version REF     GitHub ref to install, such as main or v0.1.2.
  --agent NAME      Install into a known agent's skill dir: codex or claude.
                    Defaults to codex (~/.codex/skills/linuxdo-reader).
  --local           Install into ./.<agent>/skills in the current directory.
  --dest PATH       Explicit skill destination (overrides --agent/--local).
  --no-browser      Skip Playwright Chromium installation.
  -h, --help        Show this help.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --version|--ref)
      REF="$2"
      shift 2
      ;;
    --agent)
      AGENT="$2"
      shift 2
      ;;
    --local)
      LOCAL=1
      shift
      ;;
    --dest)
      DEST="$2"
      shift 2
      ;;
    --no-browser)
      INSTALL_BROWSER=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if ! command -v uv >/dev/null 2>&1; then
  echo "Error: uv is required. Install it from https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

echo "Installing linuxdo-reader from ${REPO}@${REF}..."
uv tool install "git+https://github.com/${REPO}@${REF}" --with playwright --force

if [ "$INSTALL_BROWSER" -eq 1 ]; then
  echo "Installing Playwright Chromium..."
  uv tool run playwright install chromium
fi

echo "Installing Skill..."
set -- install-skill --ref "$REF" --force
if [ -n "$DEST" ]; then
  set -- "$@" --dest "$DEST"
else
  [ -n "$AGENT" ] && set -- "$@" --agent "$AGENT"
  [ "$LOCAL" -eq 1 ] && set -- "$@" --local
fi
linuxdo-reader "$@"

cat <<'EOF'

linuxdo-reader is installed.

Try:
  linuxdo-reader -h
  linuxdo-reader auth refresh

Restart your agent to pick up the linuxdo-reader Skill.
EOF
