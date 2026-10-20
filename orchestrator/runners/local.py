import asyncio
from pathlib import Path
import time
from orchestrator.runners.base import ExecutionEnvironment, CommandResult
from orchestrator.core.safety import is_path_confined, is_command_safe

class LocalHostRunner(ExecutionEnvironment):
    """
    Executes commands and manages files directly on the local host filesystem.
    Includes strict path confinement to workspace_dir and dangerous command prevention.
    """

    def __init__(self, workspace_dir: str | Path):
        self.workspace_dir = Path(workspace_dir).resolve()
        if not self.workspace_dir.exists():
            self.workspace_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_safe_path(self, path: str) -> Path:
        resolved = (self.workspace_dir / path).resolve()
        if not is_path_confined(resolved, self.workspace_dir):
            raise PermissionError(f"Access denied: path '{path}' escapes workspace boundary '{self.workspace_dir}'")
        return resolved

    async def exec(self, cmd: str, timeout: int = 60, cwd: str | None = None) -> CommandResult:
        is_safe, reason = is_command_safe(cmd)
        if not is_safe:
            return CommandResult(
                stdout="",
                stderr=f"Security Error: {reason}",
                exit_code=126,
                duration_seconds=0.0,
            )

        exec_cwd = self._resolve_safe_path(cwd) if cwd else self.workspace_dir
        start_time = time.perf_counter()

        try:
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(exec_cwd),
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
            try:
                process.kill()
            except Exception:
                pass
            return CommandResult(
                stdout="",
                stderr=f"Command timed out after {timeout} seconds",
                exit_code=124,
                duration_seconds=duration,
            )
        except Exception as e:
            duration = time.perf_counter() - start_time
            return CommandResult(
                stdout="",
                stderr=f"Execution error: {str(e)}",
                exit_code=1,
                duration_seconds=duration,
            )

    async def read_file(self, path: str) -> str:
        safe_path = self._resolve_safe_path(path)
        if not safe_path.exists():
            raise FileNotFoundError(f"File not found: '{path}' in workspace")
        return safe_path.read_text(encoding="utf-8", errors="replace")

    async def write_file(self, path: str, content: str) -> None:
        safe_path = self._resolve_safe_path(path)
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        safe_path.write_text(content, encoding="utf-8")

    async def file_exists(self, path: str) -> bool:
        try:
            safe_path = self._resolve_safe_path(path)
            return safe_path.exists()
        except PermissionError:
            return False

    async def list_files(self, relative_dir: str = ".") -> list[str]:
        safe_dir = self._resolve_safe_path(relative_dir)
        if not safe_dir.exists() or not safe_dir.is_dir():
            return []
        files = []
        for p in safe_dir.rglob("*"):
            if p.is_file():
                # Avoid listing git internals or cache dirs
                rel = str(p.relative_to(self.workspace_dir)).replace("\\", "/")
                if not any(part.startswith(".") for part in rel.split("/")):
                    files.append(rel)
        return files
