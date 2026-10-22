from pathlib import Path
import os
import sys
from orchestrator.tools.git import mount_worktree_junctions, unmount_worktree_junctions

def test_directory_junction_lifecycle(tmp_path: Path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    node_modules = repo_dir / "node_modules"
    node_modules.mkdir()
    (node_modules / "pkg.json").write_text('{"name": "test"}', encoding="utf-8")

    worktree_path = tmp_path / "worktree"
    worktree_path.mkdir()

    # 1. Mount junctions
    mounted = mount_worktree_junctions(repo_dir, worktree_path)
    assert len(mounted) == 1
    assert (worktree_path / "node_modules").exists()
    assert (worktree_path / "node_modules" / "pkg.json").read_text(encoding="utf-8") == '{"name": "test"}'

    # 2. Unmount junctions safely
    unmount_worktree_junctions(worktree_path)
    assert not (worktree_path / "node_modules").exists()

    # 3. Assert parent repo node_modules is completely intact!
    assert node_modules.exists()
    assert (node_modules / "pkg.json").exists()
