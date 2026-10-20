import shutil
import subprocess
import sys
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, patch
from typer.testing import CliRunner

from orchestrator.cli import app
from orchestrator.providers.client import LLMResponse


def setup_demo_git_repo(dest_dir: Path):
    """Copies examples/demo_calculator to dest_dir and initializes a fresh Git repo."""
    src_dir = Path("examples/demo_calculator").resolve()
    shutil.copytree(src_dir, dest_dir)

    subprocess.run(["git", "init"], cwd=dest_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=dest_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=dest_dir, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=dest_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit of demo_calculator"], cwd=dest_dir, check=True, capture_output=True)


def test_demo_calculator_cli_solve_and_status(tmp_path: Path):
    demo_dir = tmp_path / "demo_repo"
    setup_demo_git_repo(demo_dir)

    mock_client = AsyncMock()

    triage_resp = LLMResponse(
        content="Bug: add function in calculator.py subtracts a - b instead of a + b.",
        prompt_tokens=40,
        completion_tokens=20,
        finish_reason="stop",
        model="mock-triage",
    )
    reproduce_resp = LLMResponse(
        content=(
            "```python:tests/test_calculator.py\n"
            "from calculator import add\n\n"
            "def test_add():\n"
            "    assert add(2, 3) == 5\n"
            "```"
        ),
        prompt_tokens=50,
        completion_tokens=30,
        finish_reason="stop",
        model="mock-reproduce",
    )
    plan_resp = LLMResponse(
        content="Plan: replace 'return a - b' with 'return a + b' in calculator.py.",
        prompt_tokens=60,
        completion_tokens=25,
        finish_reason="stop",
        model="mock-plan",
    )
    edit_resp = LLMResponse(
        content=(
            "FILE: calculator.py\n"
            "<<<<<<< SEARCH\n"
            "    return a - b\n"
            "=======\n"
            "    return a + b\n"
            ">>>>>>> REPLACE"
        ),
        prompt_tokens=70,
        completion_tokens=35,
        finish_reason="stop",
        model="mock-edit",
    )
    review_resp = LLMResponse(
        content="## Summary\nFixed calculator add function logic.\n\n## Verification\npytest passes.",
        prompt_tokens=80,
        completion_tokens=40,
        finish_reason="stop",
        model="mock-review",
    )

    mock_client.complete.side_effect = [
        triage_resp,
        reproduce_resp,
        plan_resp,
        edit_resp,
        review_resp,
    ]

    cli_runner = CliRunner()

    with patch("orchestrator.core.engine.ModelRouter.get_client_for_role", return_value=mock_client):
        # 1. Run orchestrator solve command on demo repository
        test_cmd = f'"{sys.executable}" -m pytest -q -o pythonpath=.'
        result = cli_runner.invoke(
            app,
            [
                "solve",
                "-r", str(demo_dir),
                "-i", "Fix calculator.add(2, 3) returning subtraction instead of sum",
                "--test-cmd", test_cmd,
            ],
        )

        assert result.exit_code == 0
        assert "Run Completed Successfully!" in result.output
        assert "Pull Request Ready" in result.output

        # 2. Extract run ID from the saved runs directory
        runs_dir = demo_dir / ".orchestrator" / "runs"
        assert runs_dir.exists()
        run_folders = [d for d in runs_dir.iterdir() if d.is_dir()]
        assert len(run_folders) == 1
        run_id = run_folders[0].name

        # 3. Test orchestrator status command
        status_res = cli_runner.invoke(
            app,
            [
                "status",
                run_id,
                "-r", str(demo_dir),
            ],
        )
        assert status_res.exit_code == 0
        assert run_id in status_res.output
        assert "completed" in status_res.output.lower()
