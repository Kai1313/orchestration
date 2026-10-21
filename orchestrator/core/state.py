from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

class TDDPhase(str, Enum):
    TRIAGE = "triage"
    REPRODUCE = "reproduce"
    PLAN = "plan"
    EDIT = "edit"
    VERIFY = "verify"
    REVIEW = "review"
    COMPLETED = "completed"
    FAILED = "failed"


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class OrchestrationState(BaseModel):
    run_id: str
    repo_path: str
    issue_text: str
    current_phase: TDDPhase = TDDPhase.TRIAGE
    test_command: str = "pytest"
    worktree_branch: str | None = None
    reproduce_test_path: str | None = None
    failing_test_output: str | None = None
    plan_summary: str | None = None
    modified_files: list[str] = Field(default_factory=list)
    edit_attempt: int = 0
    plan_backtrack_count: int = 0
    last_error: str | None = None
    human_hint: str | None = None
    pr_title: str | None = None
    pr_body: str | None = None
    commit_hash: str | None = None
    image_path: str | None = None
    triage_analysis: str | None = None
    target_files: list[str] = Field(default_factory=list)
    in_place: bool = False
    skip_verify: bool = False
    original_branch: str | None = None
    usage: TokenUsage = Field(default_factory=TokenUsage)

    @property
    def prompt_tokens(self) -> int:
        return self.usage.prompt_tokens

    @prompt_tokens.setter
    def prompt_tokens(self, val: int):
        self.usage.prompt_tokens = val

    @property
    def completion_tokens(self) -> int:
        return self.usage.completion_tokens

    @completion_tokens.setter
    def completion_tokens(self, val: int):
        self.usage.completion_tokens = val

    @property
    def estimated_cost_usd(self) -> float:
        return self.usage.estimated_cost_usd

    @estimated_cost_usd.setter
    def estimated_cost_usd(self, val: float):
        self.usage.estimated_cost_usd = val
