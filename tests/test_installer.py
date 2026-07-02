from linuxdo_reader.installer import default_skill_dest, install_skill_from_directory


def test_default_skill_dest_uses_codex_home(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))

    assert default_skill_dest() == tmp_path / "codex" / "skills" / "linuxdo-reader"


def test_install_skill_from_directory_copies_skill(tmp_path) -> None:
    source = tmp_path / "source" / "linuxdo-reader"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("# Linux.do Reader\n", encoding="utf-8")
    (source / "agents").mkdir()
    (source / "agents" / "openai.yaml").write_text("version: 1\n", encoding="utf-8")
    dest = tmp_path / "dest" / "linuxdo-reader"

    installed = install_skill_from_directory(source, dest)

    assert installed == dest
    assert (dest / "SKILL.md").read_text(encoding="utf-8") == "# Linux.do Reader\n"
    assert (dest / "agents" / "openai.yaml").exists()


def test_install_skill_from_directory_refuses_existing_dest(tmp_path) -> None:
    source = tmp_path / "source" / "linuxdo-reader"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("# Linux.do Reader\n", encoding="utf-8")
    dest = tmp_path / "dest" / "linuxdo-reader"
    dest.mkdir(parents=True)

    try:
        install_skill_from_directory(source, dest)
    except FileExistsError as exc:
        assert str(dest) in str(exc)
    else:
        raise AssertionError("expected FileExistsError")


def test_install_skill_from_directory_force_replaces_existing_dest(tmp_path) -> None:
    source = tmp_path / "source" / "linuxdo-reader"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("# New\n", encoding="utf-8")
    dest = tmp_path / "dest" / "linuxdo-reader"
    dest.mkdir(parents=True)
    (dest / "SKILL.md").write_text("# Old\n", encoding="utf-8")

    install_skill_from_directory(source, dest, force=True)

    assert (dest / "SKILL.md").read_text(encoding="utf-8") == "# New\n"
