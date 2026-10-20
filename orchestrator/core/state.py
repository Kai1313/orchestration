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
    pr_title: str | None = None
    pr_body: str | None = None
    commit_hash: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float = 0.0
