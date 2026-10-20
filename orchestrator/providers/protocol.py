import re
from orchestrator.tools.edit import EditChunk

# Pattern for SEARCH/REPLACE blocks:
# FILE: path/to/file.py
# <<<<<<< SEARCH
# old code
# =======
# new code
# >>>>>>> REPLACE
BLOCK_PATTERN = re.compile(
    r"(?:FILE|File):\s*([^\r\n]+)\s*[\r\n]+"
    r"<<<<<<<\s*SEARCH[\r\n]+"
    r"(.*?)"
    r"=======\s*[\r\n]+"
    r"(.*?)"
    r">>>>>>>\s*REPLACE",
    re.DOTALL,
)

REPRODUCE_SCRIPT_PATTERN = re.compile(
    r"```(?:python)?(?::([^\r\n]+))?[\r\n]+(.*?)```",
    re.DOTALL,
)

def parse_search_replace_blocks(text: str) -> list[EditChunk]:
    """
    Parses all SEARCH/REPLACE blocks out of model text.
    Returns a list of EditChunk objects.
    """
    chunks = []
    for match in BLOCK_PATTERN.finditer(text):
        file_path = match.group(1).strip()
        search_content = match.group(2)
        replace_content = match.group(3)
        chunks.append(EditChunk(
            file_path=file_path,
            search_content=search_content,
            replace_content=replace_content,
        ))
    return chunks


def parse_reproduction_script(text: str) -> tuple[str, str] | None:
    """
    Extracts a reproduction test or script from markdown code blocks.
    Returns (filename, script_content) or None.
    """
    for match in REPRODUCE_SCRIPT_PATTERN.finditer(text):
        filename_hint = match.group(1) or "tests/test_reproduce_issue.py"
        script_code = match.group(2).strip()
        if "def test_" in script_code or "assert " in script_code or "import " in script_code:
            return filename_hint.strip(), script_code
    return None
