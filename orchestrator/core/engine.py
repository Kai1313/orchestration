import asyncio
import uuid
from pathlib import Path
from typing import Any
from rich.console import Console
from rich.prompt import Prompt, Confirm

from orchestrator.config import OrchestratorConfig
from orchestrator.core.state import OrchestrationState, TDDPhase
from orchestrator.core.context import TokenBudget, slice_error_log
from orchestrator.core.checkpoint import CheckpointManager
from orchestrator.core.prompts import (
    build_triage_prompt,
    build_reproduce_prompt,
    build_plan_prompt,
    build_edit_prompt,
    build_review_prompt,
    APPLY_EDITS_TOOL_SCHEMA,
)
from orchestrator.runners.base import ExecutionEnvironment
from orchestrator.runners.local import LocalHostRunner
from orchestrator.runners.docker import DockerRunner
from orchestrator.runners.detector import detect_test_command, detect_docker_image
from orchestrator.tools.repomap import generate_repo_map
from orchestrator.tools.edit import apply_atomic_edits, EditError
from orchestrator.tools.git import (
    create_worktree,
    get_git_diff,
    reset_git_hard,
    commit_worktree,
    ensure_git_repo,
    remove_worktree,
)
from orchestrator.providers.router import ModelRouter
from orchestrator.providers.protocol import (
    parse_search_replace_blocks,
    parse_tool_call_edits,
    parse_reproduction_script,
)

console = Console()

class OrchestrationEngine:
    """
    Central coordinator driving the 5-Stage TDD State Machine.
    """

    def __init__(self, config: OrchestratorConfig, interactive: bool = False):
        self.config = config
        self.interactive = interactive
        self.router = ModelRouter(config)
        self.budget = TokenBudget(
            max_tokens=config.max_tokens,
            max_cost_usd=config.max_cost_usd,
        )

    def _save_checkpoint(
        self,
        state: OrchestrationState,
        checkpoint_mgr: CheckpointManager,
        next_phase: TDDPhase | None = None,
        error: str | None = None,
    ) -> None:
        """
        Synchronizes token usage and cost metrics from TokenBudget,
        optionally updates current_phase and last_error, and atomically
        persists state to disk.
        """
        if next_phase is not None:
            state.current_phase = next_phase
        if error is not None:
            state.last_error = error
        state.prompt_tokens = self.budget.used_prompt_tokens
        state.completion_tokens = self.budget.used_completion_tokens
        state.estimated_cost_usd = self.budget.estimated_cost_usd
        checkpoint_mgr.save_state(state.model_dump())

    async def _prompt_with_timeout(
        self, prompt_func: Any, *args: Any, default_val: Any = None, **kwargs: Any
    ) -> Any:
        """
        Runs a blocking terminal prompt in a worker thread, bounded by interactive_timeout.
        Falls back to default_val if the timeout expires.
        """
        coro = asyncio.to_thread(prompt_func, *args, **kwargs)
        timeout = getattr(self.config, "interactive_timeout", 300.0)
        if timeout and timeout > 0:
            try:
                return await asyncio.wait_for(coro, timeout=timeout)
            except asyncio.TimeoutError:
                console.print(
                    f"\n[bold yellow]Interactive prompt timed out after {timeout}s. "
                    f"Proceeding automatically with default: '{default_val}'[/bold yellow]"
                )
                return default_val
        return await coro

    async def run(
        self,
        repo_path: str | Path,
        issue_text: str,
        sandbox: str = "local",
        resume_run_id: str | None = None,
        test_cmd_override: str | None = None,
        docker_image_override: str | None = None,
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

        active_workspace = repo_dir
        is_isolated_worktree = False

        try:
            # 2. Setup isolated Git worktree if git repo
            is_git = await ensure_git_repo(repo_dir)
            if is_git:
                console.print(f"[blue]Setting up isolated worktree for branch: {state.worktree_branch}[/blue]")
                active_workspace = await create_worktree(repo_dir, state.worktree_branch or "fix/issue")
                if active_workspace.resolve() != repo_dir.resolve():
                    is_isolated_worktree = True
            else:
                active_workspace = repo_dir

            # 3. Instantiate Runner
            runner: ExecutionEnvironment
            if sandbox == "docker":
                probe_runner = LocalHostRunner(active_workspace)
                image = (
                    docker_image_override
                    or self.config.docker_image
                    or await detect_docker_image(probe_runner)
                )
                console.print(f"[blue]Execution runner: Docker Container ({image})[/blue]")
                runner = DockerRunner(active_workspace, image=image)
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
                    console.print(f"[bold red]{reason}[/bold red]")
                    self._save_checkpoint(state, checkpoint_mgr, next_phase=TDDPhase.FAILED, error=reason)
                    break

                console.print(f"\n[bold cyan]> Entering Phase: {state.current_phase.upper()}[/bold cyan]")
                self._save_checkpoint(state, checkpoint_mgr)

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
                self._save_checkpoint(state, checkpoint_mgr)

            return state
        except (asyncio.CancelledError, KeyboardInterrupt):
            console.print("\n[bold yellow]Execution cancelled by user. Cleaning up...[/bold yellow]")
            self._save_checkpoint(
                state, checkpoint_mgr, next_phase=TDDPhase.FAILED, error="Execution cancelled by user"
            )
            raise
        finally:
            # Clean up isolated worktree unless the run completed successfully and created a commit
            if is_isolated_worktree and state.current_phase != TDDPhase.COMPLETED:
                console.print(f"[dim]Cleaning up isolated worktree: {active_workspace}[/dim]")
                await remove_worktree(repo_dir, active_workspace)

    async def _phase_triage(self, state: OrchestrationState, runner: ExecutionEnvironment):
        repo_map = await generate_repo_map(runner)
        prompt = build_triage_prompt(state.issue_text, repo_map)
        client = self.router.get_client_for_role("triage")
        resp = await client.complete([{"role": "user", "content": prompt}])
        self.budget.add_usage(resp.prompt_tokens, resp.completion_tokens)
        console.print("[dim]Triage analysis completed.[/dim]")
        state.current_phase = TDDPhase.REPRODUCE

    async def _phase_reproduce(self, state: OrchestrationState, runner: ExecutionEnvironment):
        prompt = build_reproduce_prompt(state.issue_text)
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
        prompt = build_plan_prompt(
            state.issue_text,
            state.reproduce_test_path,
            state.failing_test_output,
            human_hint=state.human_hint,
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

        role_cfg = self.config.roles.get("coder")
        protocol = role_cfg.protocol if role_cfg else "delimited_blocks"

        prompt = build_edit_prompt(
            state.plan_summary,
            last_error=state.last_error,
            human_hint=state.human_hint,
            protocol=protocol,
        )

        client = self.router.get_client_for_role("coder")

        if protocol == "json_tools":
            resp = await client.complete(
                [{"role": "user", "content": prompt}],
                tools=[APPLY_EDITS_TOOL_SCHEMA],
                tool_choice="auto",
            )
            self.budget.add_usage(resp.prompt_tokens, resp.completion_tokens)
            chunks = parse_tool_call_edits(resp.tool_calls or [])
            if not chunks:
                # Fallback to text parsing in case model emitted markdown blocks
                chunks = parse_search_replace_blocks(resp.content)
        else:
            resp = await client.complete([{"role": "user", "content": prompt}])
            self.budget.add_usage(resp.prompt_tokens, resp.completion_tokens)
            chunks = parse_search_replace_blocks(resp.content)

        if not chunks:
            state.last_error = "No valid edits found in model response."
            state.current_phase = TDDPhase.VERIFY  # Triggers verify failure loop
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

        # Interactive human breakpoint on failure
        if self.interactive:
            console.print("\n[bold yellow]-- INTERACTIVE BREAKPOINT: VERIFICATION FAILURE --[/bold yellow]")
            action = await self._prompt_with_timeout(
                Prompt.ask,
                "Action",
                choices=["c", "r", "a"],
                default="c",
                console=console,
                default_val="c",
            )
            if action == "a":
                state.current_phase = TDDPhase.FAILED
                return
            elif action == "r":
                await reset_git_hard(active_workspace)
                state.edit_attempt = 0
                state.current_phase = TDDPhase.PLAN
                return
            else:
                hint = await self._prompt_with_timeout(
                    Prompt.ask,
                    "Enter guidance hint for the coder (optional)",
                    default="",
                    console=console,
                    default_val="",
                )
                if hint and hint.strip():
                    state.human_hint = hint.strip()

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
        prompt = build_review_prompt(state.issue_text, diff)
        client = self.router.get_client_for_role("reviewer")
        resp = await client.complete([{"role": "user", "content": prompt}])
        self.budget.add_usage(resp.prompt_tokens, resp.completion_tokens)

        # Interactive human breakpoint before commit
        if self.interactive:
            console.print("\n[bold yellow]-- INTERACTIVE BREAKPOINT: PULL REQUEST REVIEW --[/bold yellow]")
            console.print(f"[cyan]Git Diff:[/cyan]\n{diff}")
            approved = await self._prompt_with_timeout(
                Confirm.ask,
                "Approve and commit this Pull Request?",
                default=True,
                console=console,
                default_val=False,
            )
            if not approved:
                console.print("[yellow]Pull Request commit cancelled (or timed out).[/yellow]")
                state.current_phase = TDDPhase.FAILED
                state.last_error = "PR commit cancelled during interactive review"
                return

        # Commit changes to worktree branch
        commit_msg = f"fix: resolve {state.run_id}\n\n{state.issue_text[:100]}"
        commit_hash = await commit_worktree(active_workspace, commit_msg)
        state.commit_hash = commit_hash
        state.pr_body = resp.content
        state.pr_title = f"Fix: {state.issue_text[:60]}"
        state.current_phase = TDDPhase.COMPLETED
        console.print(f"[bold green][OK] PR Prepared! Commit: {commit_hash}[/bold green]")
