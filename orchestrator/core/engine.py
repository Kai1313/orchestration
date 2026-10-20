import uuid
from pathlib import Path
from rich.console import Console

from orchestrator.config import OrchestratorConfig
from orchestrator.core.state import OrchestrationState, TDDPhase
from orchestrator.core.context import TokenBudget, slice_error_log
from orchestrator.core.checkpoint import CheckpointManager
from orchestrator.runners.base import ExecutionEnvironment
from orchestrator.runners.local import LocalHostRunner
from orchestrator.runners.docker import DockerRunner
from orchestrator.runners.detector import detect_test_command
from orchestrator.tools.repomap import generate_repo_map
from orchestrator.tools.edit import apply_atomic_edits, EditError
from orchestrator.tools.git import create_worktree, get_git_diff, reset_git_hard, commit_worktree, ensure_git_repo
from orchestrator.providers.router import ModelRouter
from orchestrator.providers.protocol import parse_search_replace_blocks, parse_reproduction_script

console = Console()

class OrchestrationEngine:
    """
    Central coordinator driving the 5-Stage TDD State Machine.
    """

    def __init__(self, config: OrchestratorConfig):
        self.config = config
        self.router = ModelRouter(config)
        self.budget = TokenBudget(
            max_tokens=config.max_tokens,
            max_cost_usd=config.max_cost_usd,
        )

    async def run(
        self,
        repo_path: str | Path,
        issue_text: str,
        sandbox: str = "local",
        resume_run_id: str | None = None,
        test_cmd_override: str | None = None,
    ) -> OrchestrationState:
        repo_dir = Path(repo_path).resolve()
        run_id = resume_run_id or f"run_{uuid.uuid4().hex[:8]}"
        checkpoint_dir = repo_dir / ".orchestrator" / "runs"
        checkpoint_mgr = CheckpointManager(checkpoint_dir, run_id)

        # 1. Initialize or resume state
        if resume_run_id:
            state_data = checkpoint_mgr.load_state()
            if not state_data:
                raise ValueError(f"Cannot resume: run '{resume_run_id}' not found.")
            state = OrchestrationState(**state_data)
            console.print(f"[yellow]Resuming run {run_id} from phase {state.current_phase}[/yellow]")
        else:
            branch_name = f"fix/{run_id}"
            state = OrchestrationState(
                run_id=run_id,
                repo_path=str(repo_dir),
                issue_text=issue_text,
                worktree_branch=branch_name,
            )

        # 2. Setup isolated Git worktree if git repo
        is_git = await ensure_git_repo(repo_dir)
        if is_git:
            console.print(f"[blue]Setting up isolated worktree for branch: {state.worktree_branch}[/blue]")
            active_workspace = await create_worktree(repo_dir, state.worktree_branch or "fix/issue")
        else:
            active_workspace = repo_dir

        # 3. Instantiate Runner
        runner: ExecutionEnvironment
        if sandbox == "docker":
            console.print("[blue]Execution runner: Docker Container[/blue]")
            runner = DockerRunner(active_workspace)
        else:
            console.print("[blue]Execution runner: Local Host[/blue]")
            runner = LocalHostRunner(active_workspace)

        # 4. Auto-detect test runner if not overridden
        if test_cmd_override:
            state.test_command = test_cmd_override
        elif not resume_run_id:
            state.test_command = await detect_test_command(runner)
        console.print(f"[green]Using test command: '{state.test_command}'[/green]")

        # 5. Execute State Machine Phases
        while state.current_phase not in (TDDPhase.COMPLETED, TDDPhase.FAILED):
            exceeded, reason = self.budget.is_exceeded()
            if exceeded:
                state.last_error = reason
                state.current_phase = TDDPhase.FAILED
                checkpoint_mgr.save_state(state.model_dump())
                console.print(f"[bold red]{reason}[/bold red]")
                break

            console.print(f"\n[bold cyan]> Entering Phase: {state.current_phase.upper()}[/bold cyan]")
            checkpoint_mgr.save_state(state.model_dump())

            if state.current_phase == TDDPhase.TRIAGE:
                await self._phase_triage(state, runner)
            elif state.current_phase == TDDPhase.REPRODUCE:
                await self._phase_reproduce(state, runner)
            elif state.current_phase == TDDPhase.PLAN:
                await self._phase_plan(state, runner)
            elif state.current_phase == TDDPhase.EDIT:
                await self._phase_edit(state, runner)
            elif state.current_phase == TDDPhase.VERIFY:
                await self._phase_verify(state, runner, active_workspace)
            elif state.current_phase == TDDPhase.REVIEW:
                await self._phase_review(state, runner, active_workspace)

            # Persist state after each step
            state.prompt_tokens = self.budget.used_prompt_tokens
            state.completion_tokens = self.budget.used_completion_tokens
            state.estimated_cost_usd = self.budget.estimated_cost_usd
            checkpoint_mgr.save_state(state.model_dump())

        return state

    async def _phase_triage(self, state: OrchestrationState, runner: ExecutionEnvironment):
        repo_map = await generate_repo_map(runner)
        prompt = (
            f"You are the Lead Triage Architect.\n\n"
            f"## Issue Description:\n{state.issue_text}\n\n"
            f"## Repository Map:\n{repo_map}\n\n"
            f"Analyze the repository structure and issue. Identify:\n"
            f"1. Which files are most likely responsible for the issue.\n"
            f"2. What behavior needs to be tested in the reproduction test."
        )
        client = self.router.get_client_for_role("triage")
        resp = await client.complete([{"role": "user", "content": prompt}])
        self.budget.add_usage(resp.prompt_tokens, resp.completion_tokens)
        console.print("[dim]Triage analysis completed.[/dim]")
        state.current_phase = TDDPhase.REPRODUCE

    async def _phase_reproduce(self, state: OrchestrationState, runner: ExecutionEnvironment):
        prompt = (
            f"You are the Test Engineer. Write a reproduction test case for this issue:\n\n"
            f"{state.issue_text}\n\n"
            f"Output the test file inside a code block, for example:\n"
            f"```python:tests/test_reproduce_issue.py\n"
            f"# test code that triggers the bug\n"
            f"```\n"
            f"The test MUST FAIL (Red) on the current buggy codebase."
        )
        client = self.router.get_client_for_role("reproduce")
        resp = await client.complete([{"role": "user", "content": prompt}])
        self.budget.add_usage(resp.prompt_tokens, resp.completion_tokens)

        parsed = parse_reproduction_script(resp.content)
        if parsed:
            test_file, test_code = parsed
            await runner.write_file(test_file, test_code)
            state.reproduce_test_path = test_file
            console.print(f"[green]Created reproduction test: {test_file}[/green]")

            # Run test to verify it fails
            cmd = f"{state.test_command} {test_file}"
            res = await runner.exec(cmd, timeout=self.config.test_timeout_seconds)
            state.failing_test_output = slice_error_log(res.stderr or res.stdout)
            console.print(f"[dim]Initial test run exit code: {res.exit_code}[/dim]")
        
        state.current_phase = TDDPhase.PLAN

    async def _phase_plan(self, state: OrchestrationState, runner: ExecutionEnvironment):
        prompt = (
            f"You are the Systems Architect. Review the bug and reproduction error:\n\n"
            f"Issue: {state.issue_text}\n"
            f"Reproduction Test: {state.reproduce_test_path}\n"
            f"Error Output:\n{state.failing_test_output}\n\n"
            f"Formulate a surgical, step-by-step implementation plan. List the exact files and functions to modify."
        )
        client = self.router.get_client_for_role("planner")
        resp = await client.complete([{"role": "user", "content": prompt}])
        self.budget.add_usage(resp.prompt_tokens, resp.completion_tokens)
        state.plan_summary = resp.content
        console.print("[dim]Fix plan formulated.[/dim]")
        state.current_phase = TDDPhase.EDIT

    async def _phase_edit(self, state: OrchestrationState, runner: ExecutionEnvironment):
        state.edit_attempt += 1
        console.print(f"[blue]Edit attempt #{state.edit_attempt} (Max {self.config.max_edit_retries})[/blue]")

        prompt = (
            f"You are the Core Coder. Apply surgical edits to fix the issue according to the plan:\n\n"
            f"{state.plan_summary}\n\n"
            f"Output your edits using EXACT SEARCH/REPLACE blocks formatted like this:\n\n"
            f"FILE: src/example.py\n"
            f"<<<<<<< SEARCH\n"
            f"exact lines to replace\n"
            f"=======\n"
            f"new replacement lines\n"
            f">>>>>>> REPLACE"
        )
        if state.last_error:
            prompt += f"\n\nPrevious failure to correct:\n{state.last_error}"

        client = self.router.get_client_for_role("coder")
        resp = await client.complete([{"role": "user", "content": prompt}])
        self.budget.add_usage(resp.prompt_tokens, resp.completion_tokens)

        chunks = parse_search_replace_blocks(resp.content)
        if not chunks:
            state.last_error = "No valid SEARCH/REPLACE blocks found in model response."
            state.current_phase = TDDPhase.VERIFY  # Will trigger verify failure loop
            return

        try:
            staged = await apply_atomic_edits(runner, chunks)
            state.modified_files = list(set(state.modified_files + list(staged.keys())))
            console.print(f"[green]Successfully applied edits to: {', '.join(staged.keys())}[/green]")
            state.last_error = None
        except EditError as e:
            state.last_error = f"Edit Block Mismatch: {str(e)}"
            console.print(f"[red]{state.last_error}[/red]")

        state.current_phase = TDDPhase.VERIFY

    async def _phase_verify(self, state: OrchestrationState, runner: ExecutionEnvironment, active_workspace: Path):
        # 1. Run reproduction test or full test suite
        target_cmd = f"{state.test_command} {state.reproduce_test_path}" if state.reproduce_test_path else state.test_command
        console.print(f"[blue]Running verification: '{target_cmd}'[/blue]")
        res = await runner.exec(target_cmd, timeout=self.config.test_timeout_seconds)

        if res.success:
            console.print("[bold green][OK] Verification PASSED! Tests are green.[/bold green]")
            state.current_phase = TDDPhase.REVIEW
            state.last_error = None
            return

        # Verification failed
        console.print(f"[red]Verification FAILED (Exit code {res.exit_code})[/red]")
        error_slice = slice_error_log(res.stderr or res.stdout)
        state.last_error = error_slice

        # Check inner edit loop limit
        if state.edit_attempt < self.config.max_edit_retries:
            console.print(f"[yellow]Retrying edit loop ({state.edit_attempt}/{self.config.max_edit_retries})...[/yellow]")
            state.current_phase = TDDPhase.EDIT
            return

        # Edit limit exhausted -> Check Tier 2 Plan Backtrack
        if state.plan_backtrack_count < self.config.max_plan_backtracks:
            state.plan_backtrack_count += 1
            console.print(
                f"[bold magenta]Edit loop exhausted. Backtracking to PLAN "
                f"({state.plan_backtrack_count}/{self.config.max_plan_backtracks}). Resetting Git changes...[/bold magenta]"
            )
            await reset_git_hard(active_workspace)
            state.edit_attempt = 0
            state.current_phase = TDDPhase.PLAN
        else:
            console.print("[bold red]Both Edit and Plan backtrack limits exhausted. Marking run as FAILED.[/bold red]")
            state.current_phase = TDDPhase.FAILED

    async def _phase_review(self, state: OrchestrationState, runner: ExecutionEnvironment, active_workspace: Path):
        diff = await get_git_diff(active_workspace)
        prompt = (
            f"You are the Staff Code Reviewer. Review the verified git diff against the issue prompt:\n\n"
            f"Issue: {state.issue_text}\n"
            f"Git Diff:\n{diff}\n\n"
            f"Generate a Pull Request Title and detailed markdown PR Body summarizing the changes."
        )
        client = self.router.get_client_for_role("reviewer")
        resp = await client.complete([{"role": "user", "content": prompt}])
        self.budget.add_usage(resp.prompt_tokens, resp.completion_tokens)

        # Commit changes to worktree branch
        commit_msg = f"fix: resolve {state.run_id}\n\n{state.issue_text[:100]}"
        commit_hash = await commit_worktree(active_workspace, commit_msg)
        state.commit_hash = commit_hash
        state.pr_body = resp.content
        state.pr_title = f"Fix: {state.issue_text[:60]}"
        state.current_phase = TDDPhase.COMPLETED
        console.print(f"[bold green][OK] PR Prepared! Commit: {commit_hash}[/bold green]")
