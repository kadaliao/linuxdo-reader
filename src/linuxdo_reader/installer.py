from __future__ import annotations

import os
import shutil
import tarfile
import tempfile
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from . import __version__

REPO_ARCHIVE_URL = "https://github.com/kadaliao/linuxdo-reader/archive/{ref}.tar.gz"
SKILL_RELATIVE_PATH = Path("skills") / "linuxdo-reader"
SKILL_DIR_NAME = "linuxdo-reader"


def _codex_home_skills_root() -> Path:
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
    return codex_home / "skills"


def _claude_home_skills_root() -> Path:
    return Path.home() / ".claude" / "skills"


@dataclass(frozen=True)
class AgentSkillDirs:
    """Where a given agent loads Skills from.

    ``home_root`` is the per-user directory; ``local_relative`` is the
    project-level directory, resolved against the current working directory.
    These differ per agent (e.g. Codex reads project Skills from ``.agents/``,
    not ``.codex/``), so ``--local`` cannot assume a uniform layout.
    """

    home_root: Callable[[], Path]
    local_relative: Path


# Known agents mapped to their Skill directories.
# Add an entry here when another agent gains a standard Skill location.
KNOWN_AGENTS: dict[str, AgentSkillDirs] = {
    "codex": AgentSkillDirs(
        home_root=_codex_home_skills_root,
        local_relative=Path(".agents") / "skills",
    ),
    "claude": AgentSkillDirs(
        home_root=_claude_home_skills_root,
        local_relative=Path(".claude") / "skills",
    ),
}
DEFAULT_AGENT = "codex"


def default_skill_dest() -> Path:
    return _codex_home_skills_root() / SKILL_DIR_NAME


def resolve_skill_dest(
    agent: str | None = None,
    dest: str | Path | None = None,
    local: bool = False,
) -> Path:
    """Resolve where the Skill should be installed.

    Precedence: an explicit ``dest`` wins and is used verbatim. Otherwise the
    destination is ``<base>/linuxdo-reader`` where ``<base>`` is the known
    agent's per-user skills directory, or its project-level directory under the
    current working directory when ``local`` is set.
    """
    if dest is not None:
        return Path(dest).expanduser()
    resolved_agent = (agent or DEFAULT_AGENT).lower()
    dirs = KNOWN_AGENTS.get(resolved_agent)
    if dirs is None:
        known = ", ".join(sorted(KNOWN_AGENTS))
        raise ValueError(
            f"Unknown agent {resolved_agent!r}; choose from {known}, or pass --dest for a custom path"
        )
    base = (Path.cwd() / dirs.local_relative) if local else dirs.home_root()
    return base / SKILL_DIR_NAME


def default_ref() -> str:
    return f"v{__version__}"


def install_skill_from_directory(source: str | Path, dest: str | Path, force: bool = False) -> Path:
    source_path = Path(source).expanduser()
    dest_path = Path(dest).expanduser()
    if not (source_path / "SKILL.md").exists():
        raise FileNotFoundError(f"{source_path} does not contain SKILL.md")
    if dest_path.exists():
        if not force:
            raise FileExistsError(f"{dest_path} already exists; pass --force to replace it")
        shutil.rmtree(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_path, dest_path)
    return dest_path


def install_skill_from_github(ref: str | None = None, dest: str | Path | None = None, force: bool = False) -> Path:
    target_ref = ref or default_ref()
    dest_path = Path(dest).expanduser() if dest else default_skill_dest()
    with tempfile.TemporaryDirectory(prefix="linuxdo-reader-skill-") as tmpdir:
        archive_path = Path(tmpdir) / "linuxdo-reader.tar.gz"
        # The URL template has a fixed HTTPS origin; only its GitHub ref path varies.
        urllib.request.urlretrieve(  # nosec B310
            REPO_ARCHIVE_URL.format(ref=target_ref), archive_path
        )
        source = _extract_skill_from_archive(archive_path, Path(tmpdir) / "archive")
        return install_skill_from_directory(source, dest_path, force=force)


def _extract_skill_from_archive(archive_path: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "r:gz") as archive:
        members = [
            member
            for member in archive.getmembers()
            if _member_is_under_skill(member.name)
        ]
        if not members:
            raise FileNotFoundError(f"{archive_path} does not contain {SKILL_RELATIVE_PATH}")
        for member in members:
            _safe_extract_member(archive, member, output_dir)
    skill_dirs = list(output_dir.glob(f"*/{SKILL_RELATIVE_PATH}"))
    if not skill_dirs:
        raise FileNotFoundError(f"{archive_path} does not contain {SKILL_RELATIVE_PATH}")
    return skill_dirs[0]


def _member_is_under_skill(name: str) -> bool:
    parts = Path(name).parts
    return len(parts) >= 3 and Path(*parts[1:3]) == SKILL_RELATIVE_PATH


def _safe_extract_member(archive: tarfile.TarFile, member: tarfile.TarInfo, output_dir: Path) -> None:
    target = (output_dir / member.name).resolve()
    output_root = output_dir.resolve()
    if output_root not in target.parents and target != output_root:
        raise RuntimeError(f"Unsafe archive path: {member.name}")
    archive.extract(member, output_dir)
