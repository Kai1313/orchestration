from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class CommandResult:
    stdout: str
    stderr: str
    exit_code: int
    duration_seconds: float

    @property
    def success(self) -> bool:
        return self.exit_code == 0


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
