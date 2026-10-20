from orchestrator.core.context import slice_error_log, TokenBudget

def test_slice_error_log():
    raw_log = "\n".join([f"test passed line {i}" for i in range(100)])
    raw_log += "\nFAILED tests/test_calc.py::test_add - AssertionError: assert -1 == 3\n"
    raw_log += "Traceback (most recent call last):\n"
    raw_log += "  File 'calculator.py', line 5, in add\n"
    raw_log += "    return a - b\n"
    raw_log += "\n".join([f"trailing output {i}" for i in range(50)])

    sliced = slice_error_log(raw_log, max_lines=30)
    assert "FAILED tests/test_calc.py" in sliced
    assert "AssertionError" in sliced
    assert len(sliced.splitlines()) <= 35


def test_token_budget_tracking():
    budget = TokenBudget(max_tokens=1000, max_cost_usd=0.01)
    assert budget.is_exceeded()[0] is False

    budget.add_usage(prompt_tokens=500, completion_tokens=400)
    assert budget.is_exceeded()[0] is False

    # Exceed tokens
    budget.add_usage(prompt_tokens=200, completion_tokens=100)
    exceeded, reason = budget.is_exceeded()
    assert exceeded is True
    assert "Token budget exceeded" in reason
