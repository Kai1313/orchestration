import asyncio
from pathlib import Path
import time
from orchestrator.runners.base import ExecutionEnvironment, CommandResult, collect_workspace_files

class DockerRunner(ExecutionEnvironment):
    """
    Executes commands and manages files inside an isolated Docker container via Docker Desktop.
    """

    def __init__(self, workspace_dir: str | Path, image: str = "python:3.11-slim"):
        self.workspace_dir = Path(workspace_dir).resolve()
        self.image = image
        self.container_workspace = "/workspace"

    async def _run_docker_cli(self, args: list[str], timeout: int = 60) -> CommandResult:
        start_time = time.perf_counter()
        cmd = ["docker"] + args
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
            duration = time.perf_counter() - start_time
            return CommandResult(
                stdout=stdout_bytes.decode("utf-8", errors="replace"),
                stderr=stderr_bytes.decode("utf-8", errors="replace"),
                exit_code=process.returncode or 0,
                duration_seconds=duration,
            )
        except asyncio.TimeoutError:
            duration = time.perf_counter() - start_time
            return CommandResult(
                stdout="",
                stderr=f"Docker command timed out after {timeout} seconds",
                exit_code=124,
                duration_seconds=duration,
            )
        except Exception as e:
            duration = time.perf_counter() - start_time
            return CommandResult(
                stdout="",
                stderr=f"Docker execution error: {str(e)}",
                exit_code=1,
                duration_seconds=duration,
            )

    async def exec(self, cmd: str, timeout: int = 60, cwd: str | None = None) -> CommandResult:
        container_cwd = f"{self.container_workspace}/{cwd}" if cwd else self.container_workspace
        # Run ephemeral docker container with workspace volume mounted
        docker_args = [
            "run",
            "--rm",
            "-v",
            f"{self.workspace_dir}:{self.container_workspace}",
            "-w",
            container_cwd,
            self.image,
            "sh",
            "-c",
            cmd,
        ]
        return await self._run_docker_cli(docker_args, timeout=timeout)

    async def read_file(self, path: str) -> str:
        # Files are directly accessible on the host volume
        file_path = (self.workspace_dir / path).resolve()
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        return file_path.read_text(encoding="utf-8", errors="replace")

    async def write_file(self, path: str, content: str) -> None:
        file_path = (self.workspace_dir / path).resolve()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

    async def file_exists(self, path: str) -> bool:
        return (self.workspace_dir / path).exists()

    async def list_files(self, relative_dir: str = ".") -> list[str]:
        return collect_workspace_files(self.workspace_dir, relative_dir)
