from orchestrator.providers.protocol import parse_search_replace_blocks, parse_reproduction_script

def test_parse_search_replace_blocks():
    text = """
Here is the fix for the bug:

FILE: src/math/calc.py
<<<<<<< SEARCH
def subtract(a, b):
    return a + b
=======
def subtract(a, b):
    return a - b
>>>>>>> REPLACE

And here is another edit:

FILE: tests/test_calc.py
<<<<<<< SEARCH
assert subtract(3, 2) == 5
=======
assert subtract(3, 2) == 1
>>>>>>> REPLACE
"""
    chunks = parse_search_replace_blocks(text)
    assert len(chunks) == 2
    assert chunks[0].file_path == "src/math/calc.py"
    assert "return a + b" in chunks[0].search_content
    assert "return a - b" in chunks[0].replace_content
    assert chunks[1].file_path == "tests/test_calc.py"


def test_parse_reproduction_script():
    text = """
I wrote a reproduction test:

```python:tests/test_issue_42.py
def test_calc_broken():
    from src.calc import add
    assert add(1, 2) == 3
```
"""
    parsed = parse_reproduction_script(text)
    assert parsed is not None
    filename, code = parsed
    assert filename == "tests/test_issue_42.py"
    assert "def test_calc_broken" in code
