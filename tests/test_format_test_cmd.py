from orchestrator.core.engine import format_target_test_command, is_executable_test_file

def test_format_target_test_command():
    # 1. No test path provided -> base command unchanged
    assert format_target_test_command("pytest", None) == "pytest"
    assert format_target_test_command("pytest {test_path}", None) == "pytest"

    # 2. Template substitution
    assert (
        format_target_test_command("npx tsc --noEmit && npm test -- {test_path}", "src/test/foo.test.ts")
        == "npx tsc --noEmit && npm test -- src/test/foo.test.ts"
    )

    # 3. Composite command with && (appends to last sub-command)
    assert (
        format_target_test_command("npx tsc --noEmit && npm test --", "src/test/foo.test.ts")
        == "npx tsc --noEmit && npm test -- src/test/foo.test.ts"
    )

    # 4. Standard command append
    assert (
        format_target_test_command("pytest -o pythonpath=.", "tests/test_calc.py")
        == "pytest -o pythonpath=. tests/test_calc.py"
    )


def test_is_executable_test_file():
    # True positives: JS/TS
    assert is_executable_test_file("src/test/sales-order-scan-service.test.ts")
    assert is_executable_test_file("src/app.spec.js")
    assert is_executable_test_file("tests/component.test.tsx")

    # True positives: Python
    assert is_executable_test_file("tests/test_calculator.py")
    assert is_executable_test_file("services/order_test.py")

    # True positives: Go & Rust
    assert is_executable_test_file("pkg/server/server_test.go")
    assert is_executable_test_file("tests/integration_test.rs")

    # Rejection of fixtures, configs, helpers, and setup files
    assert not is_executable_test_file("tests/conftest.py")
    assert not is_executable_test_file("src/test/setup.ts")
    assert not is_executable_test_file("src/test/setup.js")
    assert not is_executable_test_file("tests/fixtures/mock_data.json")
    assert not is_executable_test_file("tests/mocks/mock_auth.ts")
    assert not is_executable_test_file("src/test/helpers/db.ts")
    assert not is_executable_test_file("jest.config.ts")
    assert not is_executable_test_file("src/models/sales-order-model.ts")
