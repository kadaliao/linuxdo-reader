from pathlib import Path


def test_release_workflow_only_accepts_current_main_sha() -> None:
    workflow = (
        Path(__file__).parents[1] / ".github" / "workflows" / "release.yml"
    ).read_text(encoding="utf-8")

    assert "git fetch --no-tags origin main" in workflow
    assert "MAIN_SHA=$(git rev-parse origin/main)" in workflow
    assert 'test "$RELEASE_SHA" = "$MAIN_SHA"' in workflow
    assert 'gh release create "$TAG" --target "$RELEASE_SHA"' in workflow
