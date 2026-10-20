from dataclasses import dataclass
from orchestrator.runners.base import ExecutionEnvironment

@dataclass
class EditChunk:
    file_path: str
    search_content: str
    replace_content: str


class EditError(Exception):
    pass


def normalize_lines(text: str) -> str:
    """Standardize line endings and strip trailing whitespace on each line."""
    return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").split("\n"))


def apply_replacement(original: str, search: str, replace: str) -> str:
    """
    Applies exact replacement. If exact match fails, attempts normalized-whitespace fallback.
    Ensures that the search block occurs EXACTLY ONCE to prevent ambiguous replacements.
    """
    # 1. Direct exact match
    count = original.count(search)
    if count == 1:
        return original.replace(search, replace, 1)
    if count > 1:
        raise EditError(f"Search block occurs {count} times in file. Needs more context lines to be unique.")

    # 2. Normalized line endings fallback
    norm_original = original.replace("\r\n", "\n")
    norm_search = search.replace("\r\n", "\n")
    norm_replace = replace.replace("\r\n", "\n")
    if norm_original.count(norm_search) == 1:
        return norm_original.replace(norm_search, norm_replace, 1)

    # 3. Strip trailing whitespace per line fallback
    stripped_orig_lines = [line.rstrip() for line in norm_original.split("\n")]
    stripped_search_lines = [line.rstrip() for line in norm_search.split("\n")]
    
    search_len = len(stripped_search_lines)
    match_indices = []
    for i in range(len(stripped_orig_lines) - search_len + 1):
        if stripped_orig_lines[i : i + search_len] == stripped_search_lines:
            match_indices.append(i)

    if len(match_indices) == 1:
        idx = match_indices[0]
        orig_lines = norm_original.split("\n")
        new_lines = orig_lines[:idx] + norm_replace.split("\n") + orig_lines[idx + search_len:]
        return "\n".join(new_lines)
    elif len(match_indices) > 1:
        raise EditError(f"Fuzzy search block matches {len(match_indices)} locations. More context needed.")

    raise EditError("Search block could not be found in file. Ensure exact character sequence matches.")


async def apply_atomic_edits(runner: ExecutionEnvironment, chunks: list[EditChunk]) -> dict[str, str]:
    """
    Validates that ALL chunks in the batch can be applied successfully in memory.
    Only if 100% of chunks match without error, writes the modified files to the runner.
    Returns dict of {file_path: new_content}.
    """
    # 1. Group chunks by file
    file_chunks: dict[str, list[EditChunk]] = {}
    for chunk in chunks:
        file_chunks.setdefault(chunk.file_path, []).append(chunk)

    # 2. In-memory stage validation
    staged_files: dict[str, str] = {}
    for file_path, edits in file_chunks.items():
        if not await runner.file_exists(file_path):
            raise EditError(f"Cannot edit non-existent file: '{file_path}'")
        
        content = await runner.read_file(file_path)
        for edit in edits:
            content = apply_replacement(content, edit.search_content, edit.replace_content)
        staged_files[file_path] = content

    # 3. Commit staged files to runner
    for file_path, new_content in staged_files.items():
        await runner.write_file(file_path, new_content)

    return staged_files
