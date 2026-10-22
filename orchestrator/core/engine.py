import asyncio
import uuid
from pathlib import Path
from typing import Any
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel

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
import base64
import mimetypes
import re
from orchestrator.runners.base import ExecutionEnvironment
from orchestrator.runners.local import LocalHostRunner
from orchestrator.runners.docker import DockerRunner
from orchestrator.runners.detector import detect_test_command, detect_docker_image
from orchestrator.tools.repomap import generate_repo_map
from orchestrator.tools.search import grep_search
from orchestrator.tools.edit import apply_atomic_edits, EditError
from orchestrator.tools.git import (
    create_worktree,
    get_git_diff,
    reset_git_hard,
    commit_worktree,
    ensure_git_repo,
    remove_worktree,
    is_git_clean,
    get_current_branch,
    checkout_branch,
    delete_branch,
    ensure_orchestrator_ignored,
)
from orchestrator.providers.router import ModelRouter
from orchestrator.providers.protocol import (
    parse_search_replace_blocks,
    parse_tool_call_edits,
    parse_reproduction_script,
)

console = Console()

TRIAGE_STOP_WORDS = frozenset({
    "this", "that", "with", "from", "have", "must", "should", "could",
    "cukup", "saja", "jika", "sama", "pada", "untuk", "yang", "akan",
})


async def _collect_mentioned_files(
    runner: ExecutionEnvironment, content: str, state: OrchestrationState
) -> None:
    """
    Extracts file paths mentioned in LLM text, normalizes Windows path separators,
    and registers valid workspace files in state.target_files.
    """
    for line in content.splitlines():
        words = re.findall(r'[\w./\\-]+\.(?:blade\.php|php|vue|js|ts|jsx|tsx|css|py|html)', line)
        for w in words:
            cleaned = w.strip("`'\",").replace("\\", "/")
            if await runner.file_exists(cleaned) and cleaned not in state.target_files:
                state.target_files.append(cleaned)


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
        image_path: str | None = None,
        in_place: bool = False,
        skip_verify: bool = False,
    ) -> OrchestrationState:
        repo_dir = Path(repo_path).resolve()
        ensure_orchestrator_ignored(repo_dir)
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
                image_path=image_path,
                in_place=in_place,
                skip_verify=skip_verify,
            )

        active_workspace = repo_dir
        is_isolated_worktree = False

        try:
            # 2. Setup Git workspace: in-place branch or isolated worktree
            is_git = await ensure_git_repo(repo_dir)
            if is_git:
                if in_place:
                    clean = await is_git_clean(repo_dir)
                    if not clean:
                        raise RuntimeError(
                            "Working tree has uncommitted changes. Please commit or stash your changes before running with --in-place."
                        )
                    state.original_branch = await get_current_branch(repo_dir)
                    console.print(f"[blue]In-place mode: checking out branch '{state.worktree_branch}' from '{state.original_branch}'[/blue]")
                    checked_out = await checkout_branch(repo_dir, state.worktree_branch, create=True)
                    if not checked_out:
                        raise RuntimeError(f"Failed to checkout in-place branch '{state.worktree_branch}'")
                    active_workspace = repo_dir
                else:
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
                    await self._phase_edit(state, runner, active_workspace)
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
                await remove_worktree(repo_dir, active_workspace, console=console)

    async def _phase_triage(self, state: OrchestrationState, runner: ExecutionEnvironment):
        repo_map = await generate_repo_map(runner)
        has_image = bool(state.image_path and Path(state.image_path).exists())

        # Keyword search: extract potential tokens / keywords from issue text
        keywords = re.findall(r'"([^"]+)"|([A-Za-z0-9_-]{4,})', state.issue_text)
        search_terms = []
        for quoted, word in keywords:
            term = quoted or word
            if term and term.lower() not in TRIAGE_STOP_WORDS:
                search_terms.append(term)

        found_matches = []
        for term in search_terms[:5]:
            matches = await grep_search(runner, term, max_results=5)
            for m in matches:
                found_matches.append(f"{m['file']}:{m['line_number']} -> {m['line_content']}")

        grep_context = "\n".join(found_matches[:15]) if found_matches else None
        prompt_text = build_triage_prompt(state.issue_text, repo_map, grep_context=grep_context, has_image=has_image)

        messages = []
        if has_image:
            img_path = Path(state.image_path)
            mime_type, _ = mimetypes.guess_type(str(img_path))
            mime_type = mime_type or "image/png"
            b64_data = base64.b64encode(img_path.read_bytes()).decode("utf-8")
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{b64_data}"
                        }
                    }
                ]
            })
        else:
            messages.append({"role": "user", "content": prompt_text})

        client = self.router.get_client_for_role("triage")
        resp = await client.complete(messages)
        self.budget.add_usage(resp.prompt_tokens, resp.completion_tokens)
        state.triage_analysis = resp.content
        console.print("[dim]Triage analysis completed.[/dim]")

        # Extract potential suspect files from triage response
        await _collect_mentioned_files(runner, resp.content, state)

        if state.skip_verify:
            console.print("[yellow]Skip-verify enabled: advancing directly to Plan stage.[/yellow]")
            state.current_phase = TDDPhase.PLAN
        else:
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
            triage_analysis=state.triage_analysis,
        )
        client = self.router.get_client_for_role("planner")
        resp = await client.complete([{"role": "user", "content": prompt}])
        self.budget.add_usage(resp.prompt_tokens, resp.completion_tokens)
        state.plan_summary = resp.content
        console.print("[dim]Fix plan formulated.[/dim]")

        # Extract any newly mentioned target files from plan
        await _collect_mentioned_files(runner, resp.content, state)

        state.current_phase = TDDPhase.EDIT

    async def _phase_edit(self, state: OrchestrationState, runner: ExecutionEnvironment, active_workspace: Path):
        state.edit_attempt += 1
        console.print(f"[blue]Edit attempt #{state.edit_attempt} (Max {self.config.max_edit_retries})[/blue]")

        role_cfg = self.config.roles.get("coder")
        protocol = role_cfg.protocol if role_cfg else "delimited_blocks"

        # Read actual file contexts for identified target files so coder has verbatim reference
        file_contexts = {}
        for target_file in state.target_files[:5]:
            try:
                file_contexts[target_file] = await runner.read_file(target_file)
            except Exception:
                continue

        prompt = build_edit_prompt(
            state.plan_summary,
            last_error=state.last_error,
            human_hint=state.human_hint,
            file_contexts=file_contexts if file_contexts else None,
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
                chunks = parse_search_replace_blocks(resp.content)
        else:
            resp = await client.complete([{"role": "user", "content": prompt}])
            self.budget.add_usage(resp.prompt_tokens, resp.completion_tokens)
            chunks = parse_search_replace_blocks(resp.content)

        if not chunks:
            state.last_error = "No valid edits found in model response."
            if state.skip_verify:
                if state.edit_attempt < self.config.max_edit_retries:
                    console.print("[yellow]Retrying edit formulation...[/yellow]")
                    state.current_phase = TDDPhase.EDIT
                else:
                    state.current_phase = TDDPhase.FAILED
                return
            state.current_phase = TDDPhase.VERIFY
            return

        try:
            staged = await apply_atomic_edits(runner, chunks)
            state.modified_files = list(set(state.modified_files + list(staged.keys())))
            console.print(f"[green]Successfully applied edits to: {', '.join(staged.keys())}[/green]")
            state.last_error = None
        except EditError as e:
            state.last_error = f"Edit Block Mismatch: {str(e)}"
            console.print(f"[red]{state.last_error}[/red]")
            if state.skip_verify:
                if state.edit_attempt < self.config.max_edit_retries:
                    console.print("[yellow]Retrying edit block...[/yellow]")
                    state.current_phase = TDDPhase.EDIT
                else:
                    state.current_phase = TDDPhase.FAILED
                return
            state.current_phase = TDDPhase.VERIFY
            return

        # Post-edit hook: If Laravel project, clear view cache automatically
        if await runner.file_exists("artisan"):
            console.print("[dim]Detected Laravel project: invalidating view cache (php artisan view:clear)...[/dim]")
            await runner.exec("php artisan view:clear", timeout=15)

        # Skip-verify branch handling
        if state.skip_verify:
            if self.interactive:
                await self._handle_interactive_verification(active_workspace, state)
            else:
                state.current_phase = TDDPhase.REVIEW
            return

        state.current_phase = TDDPhase.VERIFY

    async def _handle_interactive_verification(
        self, active_workspace: Path, state: OrchestrationState
    ) -> None:
        """
        Renders git diff preview and prompts developer to accept, retry with hint, or abort.
        """
        diff_text = await get_git_diff(active_workspace)
        console.print("\n[bold yellow]-- INTERACTIVE PREVIEW: VERIFY EDIT IN BROWSER --[/bold yellow]")
        if diff_text:
            console.print(Panel(diff_text[:3000], title="Current Git Diff"))
        action = await self._prompt_with_timeout(
            Prompt.ask,
            "Action [y: Accept & Commit / r: Retry with hint / a: Abort]",
            choices=["y", "r", "a"],
            default="y",
            console=console,
            default_val="y",
        )
        if action == "y":
            state.current_phase = TDDPhase.REVIEW
        elif action == "r":
            await reset_git_hard(active_workspace)
            hint = await self._prompt_with_timeout(
                Prompt.ask,
                "Enter guidance hint for the coder",
                default="",
                console=console,
                default_val="",
            )
            state.human_hint = hint.strip() if hint else None
            state.current_phase = TDDPhase.EDIT
        elif action == "a":
            if state.in_place and state.original_branch:
                console.print(f"[yellow]Aborting: restoring original branch '{state.original_branch}'...[/yellow]")
                await reset_git_hard(active_workspace)
                await checkout_branch(active_workspace, state.original_branch)
                if state.worktree_branch:
                    await delete_branch(active_workspace, state.worktree_branch, force=True)
            state.current_phase = TDDPhase.FAILED
            state.last_error = "Aborted by user during interactive verification"

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
