import fnmatch
import re
from orchestrator.runners.base import ExecutionEnvironment

async def find_files(runner: ExecutionEnvironment, pattern: str = "*", base_dir: str = ".") -> list[str]:
    """Finds files matching a glob pattern."""
    all_files = await runner.list_files(base_dir)
    return [f for f in all_files if fnmatch.fnmatch(f, pattern)]


async def grep_search(
    runner: ExecutionEnvironment,
    query: str,
    file_pattern: str = "*",
    is_regex: bool = False,
    max_results: int = 50,
) -> list[dict[str, str | int]]:
    """
    Searches for query pattern inside files in the runner workspace.
    Returns list of matches: [{file, line_number, line_content}].
    """
    files = await find_files(runner, file_pattern)
    matches = []

    pattern = re.compile(query, re.IGNORECASE) if is_regex else None

    for file_path in files:
        try:
            content = await runner.read_file(file_path)
            lines = content.splitlines()
            for line_idx, line in enumerate(lines, start=1):
                matched = False
                if pattern:
                    if pattern.search(line):
                        matched = True
                else:
                    if query.lower() in line.lower():
                        matched = True

                if matched:
                    matches.append({
                        "file": file_path,
                        "line_number": line_idx,
                        "line_content": line.strip(),
                    })
                    if len(matches) >= max_results:
                        return matches
        except Exception:
            continue

    return matches


async def view_file_slice(
    runner: ExecutionEnvironment,
    file_path: str,
    start_line: int = 1,
    end_line: int | None = None,
) -> str:
    """
    Reads a slice of a file formatted with line numbers.
    """
    content = await runner.read_file(file_path)
    lines = content.splitlines()
    total_lines = len(lines)
    
    start = max(1, start_line)
    end = min(total_lines, end_line) if end_line is not None else total_lines

    output = []
    for idx in range(start, end + 1):
        output.append(f"{idx:4d} | {lines[idx - 1]}")
    return "\n".join(output)
