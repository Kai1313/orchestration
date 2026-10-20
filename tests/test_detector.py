import pytest
from pathlib import Path
from orchestrator.runners.local import LocalHostRunner
from orchestrator.runners.detector import detect_test_command, detect_docker_image

@pytest.mark.asyncio
async def test_detect_python_project(tmp_path: Path):
    runner = LocalHostRunner(tmp_path)
    await runner.write_file("pyproject.toml", "[project]\nname='test'\n")
    
    cmd = await detect_test_command(runner)
    assert "pytest" in cmd
    
    image = await detect_docker_image(runner)
    assert image == "python:3.11-slim"


@pytest.mark.asyncio
async def test_detect_node_project(tmp_path: Path):
    runner = LocalHostRunner(tmp_path)
    await runner.write_file("package.json", '{"name": "test"}')
    
    cmd = await detect_test_command(runner)
    assert cmd == "npm test"
    
    image = await detect_docker_image(runner)
    assert image == "node:20-slim"


@pytest.mark.asyncio
async def test_detect_rust_project(tmp_path: Path):
    runner = LocalHostRunner(tmp_path)
    await runner.write_file("Cargo.toml", '[package]\nname = "test"')
    
    cmd = await detect_test_command(runner)
    assert cmd == "cargo test"
    
    image = await detect_docker_image(runner)
    assert image == "rust:latest"
