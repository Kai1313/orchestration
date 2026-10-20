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
    Shared helper to collect non-hidden files relative to workspace_dir.
    """
    target_dir = (workspace_dir / relative_dir).resolve()
    if not target_dir.exists() or not target_dir.is_dir():
        return []
    files = []
    for p in target_dir.rglob("*"):
        if p.is_file():
            rel = str(p.relative_to(workspace_dir)).replace("\\", "/")
            if not any(part.startswith(".") for part in rel.split("/")):
                files.append(rel)
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
