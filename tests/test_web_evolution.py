import pytest
from pathlib import Path
from orchestrator.runners.base import collect_workspace_files
from orchestrator.tools.repomap import (
    extract_php_skeleton,
    extract_template_skeleton,
    SUPPORTED_EXTENSIONS,
)
from orchestrator.core.prompts import (
    build_triage_prompt,
    build_plan_prompt,
    build_edit_prompt,
)
from orchestrator.core.state import OrchestrationState, TDDPhase


def test_collect_workspace_files_ignores_vendor_and_node_modules(tmp_path: Path):
    # Setup mock directory structure
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "User.php").write_text("<?php class User {}", encoding="utf-8")
    
    (tmp_path / "resources" / "views").mkdir(parents=True)
    (tmp_path / "resources" / "views" / "modal.blade.php").write_text("<dialog></dialog>", encoding="utf-8")

    (tmp_path / "vendor" / "laravel").mkdir(parents=True)
    (tmp_path / "vendor" / "laravel" / "Framework.php").write_text("<?php", encoding="utf-8")

    (tmp_path / "node_modules" / "vue").mkdir(parents=True)
    (tmp_path / "node_modules" / "vue" / "index.js").write_text("export default {}", encoding="utf-8")

    (tmp_path / "storage" / "framework" / "views").mkdir(parents=True)
    (tmp_path / "storage" / "framework" / "views" / "cache.php").write_text("<?php", encoding="utf-8")

    files = collect_workspace_files(tmp_path)
    
    # Should contain app/User.php and resources/views/modal.blade.php
    assert "app/User.php" in files
    assert "resources/views/modal.blade.php" in files

    # Must NOT contain vendor, node_modules, or storage files
    assert not any("vendor" in f for f in files)
    assert not any("node_modules" in f for f in files)
    assert not any("storage" in f for f in files)


def test_extract_php_skeleton():
    code = """<?php
namespace App\\Http\\Controllers;

class SecurityController extends Controller {
    public function verifyPassword(Request $request) {
        return view('auth.verify');
    }
}
"""
    sigs = extract_php_skeleton(code)
    assert any("class SecurityController" in s for s in sigs)
    assert any("public function verifyPassword" in s for s in sigs)


def test_extract_template_skeleton():
    code = """
@extends('layouts.app')

@section('content')
<div class="modal">
    <form id="verify-form">
        <input type="password" name="password" id="password_input" />
        <button type="submit">Setuju</button>
    </form>
</div>
@endsection
"""
    sigs = extract_template_skeleton(code)
    assert any("@section" in s for s in sigs)
    assert any("<form" in s for s in sigs)
    assert any("<input" in s for s in sigs)


def test_build_edit_prompt_injects_verbatim_file_content():
    prompt = build_edit_prompt(
        plan_summary="Remove duplicate eye icon",
        file_contexts={"resources/views/verify.blade.php": '<input type="password" />\n<i class="eye"></i>'},
    )
    assert "## Verbatim Target File Contents:" in prompt
    assert "resources/views/verify.blade.php" in prompt
    assert '<input type="password" />' in prompt


def test_orchestration_state_web_evolution_fields():
    state = OrchestrationState(
        run_id="run_test",
        repo_path=".",
        issue_text="Fix modal icon",
        image_path="screenshot.png",
        in_place=True,
        skip_verify=True,
        triage_analysis="Duplicate icon found in password field",
    )
    assert state.image_path == "screenshot.png"
    assert state.in_place is True
    assert state.skip_verify is True
    assert state.triage_analysis == "Duplicate icon found in password field"


@pytest.mark.asyncio
async def test_collect_mentioned_files_normalizes_windows_paths(tmp_path: Path):
    from orchestrator.core.engine import _collect_mentioned_files, TRIAGE_STOP_WORDS
    from orchestrator.runners.local import LocalHostRunner

    # Create dummy files
    (tmp_path / "resources" / "views").mkdir(parents=True)
    modal_file = tmp_path / "resources" / "views" / "modal.blade.php"
    modal_file.write_text("<div>test</div>", encoding="utf-8")

    runner = LocalHostRunner(tmp_path)
    state = OrchestrationState(
        run_id="run_test",
        repo_path=str(tmp_path),
        issue_text="Test issue",
    )

    # Content with Windows-style backslashes
    llm_content = "The defect is in `resources\\views\\modal.blade.php` inside the template."
    await _collect_mentioned_files(runner, llm_content, state)

    assert "resources/views/modal.blade.php" in state.target_files
    assert "cukup" in TRIAGE_STOP_WORDS
    assert "must" in TRIAGE_STOP_WORDS
