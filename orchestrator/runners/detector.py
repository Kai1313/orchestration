from orchestrator.runners.base import ExecutionEnvironment

async def detect_test_command(runner: ExecutionEnvironment) -> str:
    """
    Probes the workspace environment and file layout to synthesize the correct test command.
    Falls back gracefully to standard framework conventions.
    """
    # 1. Python detection
    if await runner.file_exists("pyproject.toml") or await runner.file_exists("setup.py") or await runner.file_exists("requirements.txt"):
        # Check for venv-specific pytest
        if await runner.file_exists(".venv/Scripts/pytest.exe"):
            return ".venv/Scripts/pytest.exe -o pythonpath=."
        if await runner.file_exists(".venv/bin/pytest"):
            return ".venv/bin/pytest -o pythonpath=."
        if await runner.file_exists("venv/bin/pytest"):
            return "venv/bin/pytest -o pythonpath=."
        if await runner.file_exists("poetry.lock"):
            return "poetry run pytest -o pythonpath=."
        return "python -m pytest -o pythonpath=."

    # 2. JavaScript / TypeScript detection
    if await runner.file_exists("package.json"):
        if await runner.file_exists("yarn.lock"):
            return "yarn test"
        if await runner.file_exists("pnpm-lock.yaml"):
            return "pnpm test"
        return "npm test"

    # 3. Rust detection
    if await runner.file_exists("Cargo.toml"):
        return "cargo test"

    # 4. Go detection
    if await runner.file_exists("go.mod"):
        return "go test ./..."

    # Default fallback
    return "python -m pytest -o pythonpath=."


async def detect_docker_image(runner: ExecutionEnvironment) -> str:
    """
    Probes repository manifests to pick the appropriate base Docker image.
    """
    if await runner.file_exists("package.json"):
        return "node:20-slim"
    if await runner.file_exists("Cargo.toml"):
        return "rust:latest"
    if await runner.file_exists("go.mod"):
        return "golang:1.22-alpine"
    return "python:3.11-slim"
