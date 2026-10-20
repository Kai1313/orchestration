from pathlib import Path
import re

DANGEROUS_COMMAND_PATTERNS = [
    r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f*|-rf|-fr)\s+[/~]",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r"\bchmod\s+(-[a-zA-Z]*R)\s+777\s+/",
    r"\bcurl\b.*\|\s*(bash|sh)\b",
    r"\bwget\b.*\|\s*(bash|sh)\b",
    r"\.ssh[/\\]",
    r"\.aws[/\\]",
    r":\(\)\{\s*:\|:&\s*\};:",  # Fork bomb
]

def is_path_confined(target_path: str | Path, base_dir: str | Path) -> bool:
    """
    Validates that target_path resolves strictly within base_dir.
    Guards against path traversal escapes (e.g. ../../etc/passwd).
    """
    base = Path(base_dir).resolve()
    try:
        target = (base / Path(target_path)).resolve() if not Path(target_path).is_absolute() else Path(target_path).resolve()
        return target == base or base in target.parents
    except Exception:
        return False


def is_command_safe(command: str) -> tuple[bool, str | None]:
    """
    Checks if a shell command contains dangerous system-wide destructive patterns.
    Returns (is_safe, violation_reason).
    """
    for pattern in DANGEROUS_COMMAND_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return False, f"Command contains blocked dangerous pattern matching '{pattern}'"
    return True, None
