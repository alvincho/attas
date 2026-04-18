"""
Regression tests for Public Repo Support.

The public FinMAS repo benefits from keeping the local-first quickstart and smoke
entry points stable for fresh-clone users.
"""

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_run_plaza_local_defaults_to_public_local_example():
    """
    Exercise the
    test_run_plaza_local_defaults_to_public_local_example regression scenario.
    """
    script = (ROOT / "run_plaza_local.sh").read_text(encoding="utf-8")

    assert "exec python3 -m prompits.cli up desk" in script
    assert 'exec python3 -m prompits.cli "$@"' in script


def test_public_readme_links_smoke_script_and_contributing_guide():
    """
    Exercise the
    test_public_readme_links_smoke_script_and_contributing_guide regression
    scenario.
    """
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "scripts/public_clone_smoke.sh" in readme
    assert "attas_smoke" in readme
    assert "CONTRIBUTING.md" in readme
    assert "docs/ROADMAP.md" in readme


def test_public_clone_smoke_script_supports_worktree_mode():
    """
    Exercise the
    test_public_clone_smoke_script_supports_worktree_mode regression scenario.
    """
    script = (ROOT / "scripts" / "public_clone_smoke.sh").read_text(encoding="utf-8")

    assert "--worktree" in script
    assert "Copying current working tree" in script
    assert "rsync -a --from0 --files-from=" in script


def test_attas_smoke_launcher_delegates_to_repo_script():
    """
    Exercise the
    test_attas_smoke_launcher_delegates_to_repo_script regression
    scenario.
    """
    launcher = (ROOT / "attas_smoke").read_text(encoding="utf-8")

    assert 'script_path="$(resolve_script_path)"' in launcher
    assert 'REPO_ROOT="$(find_repo_root)"' in launcher
    assert 'exec "${REPO_ROOT}/scripts/public_clone_smoke.sh" --source "${REPO_ROOT}" "$@"' in launcher


def test_attas_smoke_launcher_supports_help_from_nested_folder():
    """
    Exercise the
    test_attas_smoke_launcher_supports_help_from_nested_folder
    regression scenario.
    """
    result = subprocess.run(
        ["bash", str(ROOT / "attas_smoke"), "--help"],
        cwd=ROOT / "attas",
        capture_output=True,
        text=True,
        check=True,
    )

    assert "Usage: scripts/public_clone_smoke.sh" in result.stdout


def test_attas_smoke_launcher_supports_help_via_symlink_outside_repo(tmp_path):
    """
    Exercise the
    test_attas_smoke_launcher_supports_help_via_symlink_outside_repo regression
    scenario.
    """
    symlink_path = tmp_path / "attas_smoke"
    symlink_path.symlink_to(ROOT / "attas_smoke")

    result = subprocess.run(
        ["bash", str(symlink_path), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "Usage: scripts/public_clone_smoke.sh" in result.stdout
