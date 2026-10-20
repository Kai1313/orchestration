import re
from dataclasses import dataclass, field

@dataclass
class TokenBudget:
    max_tokens: int = 500_000
    max_cost_usd: float = 2.00
    used_prompt_tokens: int = 0
    used_completion_tokens: int = 0
    estimated_cost_usd: float = 0.0

    def add_usage(self, prompt_tokens: int, completion_tokens: int, rate_per_million_prompt: float = 1.0, rate_per_million_comp: float = 3.0):
        self.used_prompt_tokens += prompt_tokens
        self.used_completion_tokens += completion_tokens
        cost = (prompt_tokens / 1_000_000 * rate_per_million_prompt) + (completion_tokens / 1_000_000 * rate_per_million_comp)
        self.estimated_cost_usd += cost

    def is_exceeded(self) -> tuple[bool, str | None]:
        total_tokens = self.used_prompt_tokens + self.used_completion_tokens
        if total_tokens > self.max_tokens:
            return True, f"Token budget exceeded: {total_tokens} > {self.max_tokens}"
        if self.estimated_cost_usd > self.max_cost_usd:
            return True, f"Cost budget exceeded: ${self.estimated_cost_usd:.4f} > ${self.max_cost_usd:.2f}"
        return False, None


def slice_error_log(log_text: str, max_lines: int = 50) -> str:
    """
    Deterministically slices and extracts the high-signal error sections of test logs,
    removing repetitive test suite banners and verbose passes.
    """
    if not log_text or not log_text.strip():
        return "(No output recorded)"

    lines = log_text.splitlines()
    if len(lines) <= max_lines:
        return log_text

    # Search for failure anchor lines
    failure_indices = []
    for idx, line in enumerate(lines):
        if re.search(r"\b(FAILED|ERROR|AssertionError|Traceback|Exception|SyntaxError)\b", line, re.IGNORECASE):
            failure_indices.append(idx)

    if failure_indices:
        # Window around the first significant error and the bottom of the trace
        first_fail = failure_indices[0]
        start = max(0, first_fail - 3)
        end = min(len(lines), start + max_lines)
        sliced = lines[start:end]
        if end < len(lines):
            sliced.append(f"... [Truncated {len(lines) - end} lines of log] ...")
        return "\n".join(sliced)

    # Fallback to tail
    tail = lines[-max_lines:]
    return f"... [Truncated first {len(lines) - max_lines} lines] ...\n" + "\n".join(tail)
