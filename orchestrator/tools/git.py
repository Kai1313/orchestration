import asyncio
from pathlib import Path
from orchestrator.runners.base import CommandResult

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
