from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

@dataclass
class CommandResult:
    stdout: str
    stderr: str
    exit_code: int
    duration_seconds: float

    @property
    def success(self) -> bool:
        return self.exit_code == 0


def collect_workspace_files(workspace_dir: Path, relative_dir: str = ".") -> list[str]:
    """
    Shared helper to collect non-hidden files relative to workspace_dir,
    excluding dependency and build directories (vendor, node_modules, storage, etc.).
    """
    import os

    target_dir = (workspace_dir / relative_dir).resolve()
    if not target_dir.exists() or not target_dir.is_dir():
        return []

    ignore_dirs = {
        "vendor",
        "node_modules",
        "storage",
        ".git",
        ".orchestrator",
        "dist",
        "build",
        ".venv",
        "venv",
        "__pycache__",
    }

    files = []
    for root, dirs, filenames in os.walk(str(target_dir)):
        # Prune ignored and hidden directories in-place to avoid deep scanning
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ignore_dirs]
        for f in filenames:
            if f.startswith("."):
                continue
            full_path = Path(root) / f
            try:
                rel = str(full_path.relative_to(workspace_dir)).replace("\\", "/")
                files.append(rel)
            except ValueError:
                continue
    return files


class ExecutionEnvironment(ABC):
    """
    Abstract interface for executing commands and accessing files within a target repository workspace.
    """

    @abstractmethod
    async def exec(self, cmd: str, timeout: int = 60, cwd: str | None = None) -> CommandResult:
        """Execute a shell command with a timeout."""
        pass

    @abstractmethod
    async def read_file(self, path: str) -> str:
        """Read text content of a file relative to workspace root."""
        pass

    @abstractmethod
    async def write_file(self, path: str, content: str) -> None:
        """Write text content to a file relative to workspace root."""
        pass

    @abstractmethod
    async def file_exists(self, path: str) -> bool:
        """Check if a file exists relative to workspace root."""
        pass

    @abstractmethod
    async def list_files(self, relative_dir: str = ".") -> list[str]:
        """List files relative to workspace root."""
        pass
