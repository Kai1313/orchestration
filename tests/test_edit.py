import pytest
from pathlib import Path
from orchestrator.tools.edit import apply_replacement, apply_atomic_edits, EditChunk, EditError
from orchestrator.runners.local import LocalHostRunner

def test_exact_replacement():
    original = "def foo():\n    return 1\n"
    search = "    return 1"
    replace = "    return 2"
    result = apply_replacement(original, search, replace)
    assert result == "def foo():\n    return 2\n"


def test_ambiguous_replacement_fails():
    original = "x = 1\nx = 1\n"
    with pytest.raises(EditError, match="occurs 2 times"):
        apply_replacement(original, "x = 1", "x = 2")


def test_fuzzy_trailing_whitespace_replacement():
    original = "def compute():   \n    val = 10   \n    return val"
    search = "def compute():\n    val = 10"
    replace = "def compute():\n    val = 20"
    result = apply_replacement(original, search, replace)
    assert "val = 20" in result


@pytest.mark.asyncio
async def test_atomic_multi_file_edits(tmp_path: Path):
    runner = LocalHostRunner(tmp_path)
    await runner.write_file("file1.py", "val1 = 'old'\n")
    await runner.write_file("file2.py", "val2 = 'old'\n")

    # Both valid
    chunks = [
        EditChunk("file1.py", "val1 = 'old'", "val1 = 'new'"),
        EditChunk("file2.py", "val2 = 'old'", "val2 = 'new'"),
    ]
    await apply_atomic_edits(runner, chunks)
    assert await runner.read_file("file1.py") == "val1 = 'new'\n"
    assert await runner.read_file("file2.py") == "val2 = 'new'\n"

    # One invalid -> Entire batch should abort without modifying any file
    bad_chunks = [
        EditChunk("file1.py", "val1 = 'new'", "val1 = 'corrupted'"),
        EditChunk("file2.py", "NON_EXISTENT_STRING", "val2 = 'corrupted'"),
    ]
    with pytest.raises(EditError):
        await apply_atomic_edits(runner, bad_chunks)

    # Verify file1 was untouched
    assert await runner.read_file("file1.py") == "val1 = 'new'\n"
