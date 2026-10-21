import asyncio
from pathlib import Path
from rich.console import Console
from orchestrator.runners.base import CommandResult

_default_console = Console(stderr=True)

async def run_git(cmd: list[str], cwd: Path) -> CommandResult:
    proc = await asyncio.create_subprocess_exec(
        "git",
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(cwd),
    )
    stdout_b, stderr_b = await proc.communicate()
    return CommandResult(
        stdout=stdout_b.decode("utf-8", errors="replace"),
        stderr=stderr_b.decode("utf-8", errors="replace"),
        exit_code=proc.returncode or 0,
        duration_seconds=0.0,
    )


async def ensure_git_repo(repo_dir: Path) -> bool:
    res = await run_git(["status"], cwd=repo_dir)
    return res.success


async def create_worktree(repo_dir: Path, branch_name: str) -> Path:
    """
    Creates an isolated git worktree under .orchestrator/worktrees/<branch_name>.
    Falls back to repo_dir with git checkout -b if worktree creation fails.
    """
    worktree_path = (repo_dir / ".orchestrator" / "worktrees" / branch_name).resolve()
    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    # Clean existing worktree if present
    if worktree_path.exists():
        await run_git(["worktree", "remove", "--force", str(worktree_path)], cwd=repo_dir)

    res = await run_git(["worktree", "add", "-b", branch_name, str(worktree_path)], cwd=repo_dir)
    if res.success and worktree_path.exists():
        return worktree_path

    # Fallback to in-place branch
    await run_git(["checkout", "-b", branch_name], cwd=repo_dir)
    return repo_dir


async def get_git_diff(repo_dir: Path) -> str:
    res = await run_git(["diff"], cwd=repo_dir)
    return res.stdout


async def reset_git_hard(repo_dir: Path) -> bool:
    res = await run_git(["reset", "--hard"], cwd=repo_dir)
    await run_git(["clean", "-fd"], cwd=repo_dir)
    return res.success


async def commit_worktree(repo_dir: Path, message: str) -> str:
    await run_git(["add", "-A"], cwd=repo_dir)
    res = await run_git(["commit", "-m", message], cwd=repo_dir)
    if not res.success:
        return ""
    hash_res = await run_git(["rev-parse", "HEAD"], cwd=repo_dir)
    return hash_res.stdout.strip()


async def remove_worktree(
    repo_dir: Path, worktree_path: Path, console: Console | None = None
) -> bool:
    """
    Safely removes a git worktree and prunes worktree tracking.
    Never removes or damages repo_dir itself.
    """
    c = console or _default_console
    try:
        if worktree_path.resolve() == repo_dir.resolve():
            return True
        res = await run_git(["worktree", "remove", "--force", str(worktree_path)], cwd=repo_dir)
        if not res.success:
            err_msg = res.stderr.strip() or f"exit code {res.exit_code}"
            c.print(f"[yellow]Warning: Could not remove worktree '{worktree_path}': {err_msg}[/yellow]")
            return False

        await run_git(["worktree", "prune"], cwd=repo_dir)

        # Clean up empty parent directories up to .orchestrator/worktrees
        parent = worktree_path.parent
        worktrees_root = (repo_dir / ".orchestrator" / "worktrees").resolve()
        while parent != worktrees_root and parent.is_relative_to(worktrees_root):
            try:
                parent.rmdir()
                parent = parent.parent
            except OSError:
                break

        return True
    except Exception as e:
        c.print(f"[yellow]Warning: Unexpected error removing worktree '{worktree_path}': {e}[/yellow]")
        return False


async def is_git_clean(repo_dir: Path) -> bool:
    """Checks if the working tree has no uncommitted or unstaged changes."""
    res = await run_git(["status", "--porcelain"], cwd=repo_dir)
    return res.success and len(res.stdout.strip()) == 0


async def get_current_branch(repo_dir: Path) -> str:
    """Returns the name of the currently checked out branch."""
    res = await run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_dir)
    return res.stdout.strip() if res.success else "main"


async def checkout_branch(repo_dir: Path, branch_name: str, create: bool = False) -> bool:
    """Checks out or creates and checks out a git branch."""
    cmd = ["checkout", "-b", branch_name] if create else ["checkout", branch_name]
    res = await run_git(cmd, cwd=repo_dir)
    return res.success


async def delete_branch(repo_dir: Path, branch_name: str, force: bool = True) -> bool:
    """Deletes a git branch."""
    flag = "-D" if force else "-d"
    res = await run_git(["branch", flag, branch_name], cwd=repo_dir)
    return res.success
