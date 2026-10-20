import ast
import re
from orchestrator.runners.base import ExecutionEnvironment

def extract_python_skeleton(code: str, file_path: str) -> list[str]:
    """Extracts top-level and class-level function/class signatures using Python AST."""
    signatures = []
    try:
        tree = ast.parse(code)
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                signatures.append(f"class {node.name}:")
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        args = [a.arg for a in item.args.args]
                        signatures.append(f"    def {item.name}({', '.join(args)})")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = [a.arg for a in node.args.args]
                signatures.append(f"def {node.name}({', '.join(args)})")
    except Exception:
        # Fallback to regex if syntax error (e.g. invalid file or non-standard syntax)
        for line in code.splitlines():
            line_str = line.strip()
            if line_str.startswith(("def ", "class ", "async def ")):
                signatures.append(line_str.split(":")[0])
    return signatures


def extract_generic_skeleton(code: str) -> list[str]:
    """Simple regex extractor for JS/TS/Go/Rust definitions."""
    signatures = []
    pattern = re.compile(r"^\s*(export\s+)?(function|class|interface|type|struct|fn)\s+([A-Za-z0-9_]+)", re.MULTILINE)
    for match in pattern.finditer(code):
        signatures.append(match.group(0).strip())
    return signatures[:20]


async def generate_repo_map(runner: ExecutionEnvironment, max_files: int = 50) -> str:
    """
    Scans the repository and builds a concise text map of file paths and symbol signatures.
    """
    all_files = await runner.list_files(".")
    repo_map_lines = []

    for file_path in all_files[:max_files]:
        # Filter source files
        if not file_path.endswith((".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs")):
            continue

        try:
            content = await runner.read_file(file_path)
            if file_path.endswith(".py"):
                sigs = extract_python_skeleton(content, file_path)
            else:
                sigs = extract_generic_skeleton(content)

            if sigs:
                repo_map_lines.append(f"📄 {file_path}")
                for s in sigs[:15]:
                    repo_map_lines.append(f"   {s}")
                repo_map_lines.append("")
        except Exception:
            continue

    return "\n".join(repo_map_lines) if repo_map_lines else "(No source files discovered)"
