import asyncio
import subprocess
from pathlib import Path
import pytest
from unittest.mock import AsyncMock

from orchestrator.config import OrchestratorConfig
from orchestrator.core.engine import OrchestrationEngine
from orchestrator.core.state import TDDPhase
from orchestrator.providers.client import LLMResponse

def init_mock_git_repo(path: Path):
    """Initializes a real local Git repository with a deliberate bug for testing."""
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, check=True, capture_output=True)

    # Broken calculator code
    code = "def add(a: int, b: int) -> int:\n    return a - b\n"
    (path / "calc.py").write_text(code, encoding="utf-8")

    subprocess.run(["git", "add", "-A"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit with broken calculator"], cwd=path, check=True, capture_output=True)


@pytest.mark.asyncio
async def test_full_tdd_state_machine_harness(tmp_path: Path):
    repo_dir = tmp_path / "sample_calc_repo"
    repo_dir.mkdir()
    init_mock_git_repo(repo_dir)

    cfg = OrchestratorConfig(
        max_cost_usd=1.0,
        max_tokens=100_000,
        test_timeout_seconds=15,
        max_edit_retries=2,
    )

    engine = OrchestrationEngine(cfg)

    # Mock the LLM client responses across the 5 phases
    mock_client = AsyncMock()

    triage_response = LLMResponse(
        content="Root cause is in calc.py add function returning a - b instead of a + b.",
        prompt_tokens=50,
        completion_tokens=20,
        finish_reason="stop",
        model="mock-model",
    )

    reproduce_response = LLMResponse(
        content=(
            "```python:test_calc.py\n"
            "from calc import add\n\n"
            "def test_add():\n"
            "    assert add(2, 3) == 5\n"
            "```"
        ),
        prompt_tokens=60,
        completion_tokens=30,
        finish_reason="stop",
        model="mock-model",
    )

    plan_response = LLMResponse(
        content="Plan: replace 'return a - b' with 'return a + b' in calc.py.",
        prompt_tokens=70,
        completion_tokens=25,
        finish_reason="stop",
        model="mock-model",
    )

    edit_response = LLMResponse(
        content=(
            "FILE: calc.py\n"
            "<<<<<<< SEARCH\n"
            "    return a - b\n"
            "=======\n"
            "    return a + b\n"
            ">>>>>>> REPLACE"
        ),
        prompt_tokens=80,
        completion_tokens=35,
        finish_reason="stop",
        model="mock-model",
    )

    review_response = LLMResponse(
        content="## Summary\nFixed arithmetic sign error in calc.py add function.\n\n## Verification\nTest suite passes.",
        prompt_tokens=90,
        completion_tokens=40,
        finish_reason="stop",
        model="mock-model",
    )

    mock_client.complete.side_effect = [
        triage_response,
        reproduce_response,
        plan_response,
        edit_response,
        review_response,
    ]

    # Patch router to return mock client
    engine.router.get_client_for_role = lambda role: mock_client

    import sys
    # Run the orchestrator on the mock repository
    state = await engine.run(
        repo_path=repo_dir,
        issue_text="Issue #1: calc.add(2, 3) returns -1 instead of 5",
        sandbox="local",
        test_cmd_override=f'"{sys.executable}" -m pytest -q -o pythonpath=.',
    )

    # Assertions
    assert state.current_phase == TDDPhase.COMPLETED
    assert state.commit_hash is not None and len(state.commit_hash) > 0
    assert "calc.py" in state.modified_files
    assert state.pr_body is not None
    assert "calc.py add function" in state.pr_body
