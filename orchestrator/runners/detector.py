from orchestrator.runners.base import ExecutionEnvironment

async def detect_test_command(runner: ExecutionEnvironment) -> str:
    """
    Probes the workspace environment and file layout to synthesize the correct test command.
    Falls back gracefully to standard framework conventions.
    """
    # 1. Python detection
    if await runner.file_exists("pyproject.toml") or await runner.file_exists("setup.py") or await runner.file_exists("requirements.txt"):
        mypy_prefix = ""
        if await runner.file_exists("mypy.ini") or await runner.file_exists(".mypy.ini"):
            mypy_prefix = "mypy . && "
        elif await runner.file_exists("pyproject.toml"):
            try:
                pyproj = await runner.read_file("pyproject.toml")
                if "[tool.mypy]" in pyproj:
                    mypy_prefix = "mypy . && "
            except Exception:
                pass

        # Check for venv-specific pytest
        if await runner.file_exists(".venv/Scripts/pytest.exe"):
            return f"{mypy_prefix}.venv/Scripts/pytest.exe -o pythonpath=."
        if await runner.file_exists(".venv/bin/pytest"):
            return f"{mypy_prefix}.venv/bin/pytest -o pythonpath=."
        if await runner.file_exists("venv/bin/pytest"):
            return f"{mypy_prefix}venv/bin/pytest -o pythonpath=."
        if await runner.file_exists("poetry.lock"):
            return f"{mypy_prefix}poetry run pytest -o pythonpath=."
        return f"{mypy_prefix}python -m pytest -o pythonpath=."

    # 2. JavaScript / TypeScript detection
    if await runner.file_exists("package.json"):
        tsc_prefix = "npx tsc --noEmit && " if await runner.file_exists("tsconfig.json") else ""
        if await runner.file_exists("yarn.lock"):
            return f"{tsc_prefix}yarn test"
        if await runner.file_exists("pnpm-lock.yaml"):
            return f"{tsc_prefix}pnpm test --"
        return f"{tsc_prefix}npm test --"

    # 3. Rust detection
    if await runner.file_exists("Cargo.toml"):
        return "cargo check && cargo test"

    # 4. Go detection
    if await runner.file_exists("go.mod"):
        return "go vet ./... && go test ./..."

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
