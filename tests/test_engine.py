import asyncio
import time
from pathlib import Path
import pytest
from unittest.mock import AsyncMock

from orchestrator.config import OrchestratorConfig
from orchestrator.core.engine import OrchestrationEngine
from orchestrator.core.state import TDDPhase
from orchestrator.tools.git import (
    remove_worktree,
    ensure_git_repo,
    create_worktree,
    is_git_clean,
    ensure_orchestrator_ignored,
)
from tests.test_harness_e2e import init_mock_git_repo


@pytest.mark.asyncio
async def test_prompt_with_timeout_normal():
    cfg = OrchestratorConfig(interactive_timeout=1.0)
    engine = OrchestrationEngine(cfg, interactive=True)

    def mock_prompt():
        return "user_answer"

    result = await engine._prompt_with_timeout(mock_prompt, default_val="default")
    assert result == "user_answer"


@pytest.mark.asyncio
async def test_prompt_with_timeout_fallback():
    cfg = OrchestratorConfig(interactive_timeout=0.05)
    engine = OrchestrationEngine(cfg, interactive=True)

    def slow_prompt():
        time.sleep(0.2)
        return "too_late"

    result = await engine._prompt_with_timeout(slow_prompt, default_val="fallback_val")
    assert result == "fallback_val"


@pytest.mark.asyncio
async def test_remove_worktree_safety(tmp_path: Path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    init_mock_git_repo(repo_dir)

    # 1. Safety check: remove_worktree should never delete repo_dir itself
    safe_result = await remove_worktree(repo_dir, repo_dir)
    assert safe_result is True
    assert repo_dir.exists()

    # 2. Creating and then removing an isolated worktree
    wt = await create_worktree(repo_dir, "fix/test_branch")
    assert wt.exists()
    assert wt != repo_dir

    remove_res = await remove_worktree(repo_dir, wt)
    assert remove_res is True
    assert not wt.exists()


@pytest.mark.asyncio
async def test_engine_cancelled_cleans_worktree(tmp_path: Path):
    repo_dir = tmp_path / "repo_cancel"
    repo_dir.mkdir()
    init_mock_git_repo(repo_dir)

    cfg = OrchestratorConfig()
    engine = OrchestrationEngine(cfg)

    # Force cancellation during triage
    mock_client = AsyncMock()
    mock_client.complete.side_effect = asyncio.CancelledError("User interrupted")
    engine.router.get_client_for_role = lambda role: mock_client

    with pytest.raises(asyncio.CancelledError):
        await engine.run(
            repo_path=repo_dir,
            issue_text="Test cancel",
        )

    # Verify worktree was cleaned up
    worktrees_dir = repo_dir / ".orchestrator" / "worktrees"
    if worktrees_dir.exists():
        subdirs = [p for p in worktrees_dir.iterdir() if p.is_dir()]
        assert len(subdirs) == 0


@pytest.mark.asyncio
async def test_orchestrator_ignored_and_clean_working_tree(tmp_path: Path):
    repo_dir = tmp_path / "repo_ignore_test"
    repo_dir.mkdir()
    init_mock_git_repo(repo_dir)

    # 1. ensure_orchestrator_ignored writes to .git/info/exclude
    ensure_orchestrator_ignored(repo_dir)
    exclude_file = repo_dir / ".git" / "info" / "exclude"
    assert exclude_file.exists()
    assert ".orchestrator/" in exclude_file.read_text(encoding="utf-8")

    # 2. Creating files inside .orchestrator should NOT make git dirty
    orc_dir = repo_dir / ".orchestrator" / "runs" / "test_run"
    orc_dir.mkdir(parents=True, exist_ok=True)
    (orc_dir / "state.json").write_text("{}", encoding="utf-8")

    clean = await is_git_clean(repo_dir)
    assert clean is True

    # 3. But creating an actual untracked source file DOES make git dirty
    (repo_dir / "untracked.py").write_text("print('hello')", encoding="utf-8")
    dirty = await is_git_clean(repo_dir)
    assert dirty is False
