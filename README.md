# Orchestrator

Autonomous AI Software Development Orchestration Engine.

## Features
- **Deterministic 5-Stage TDD State Machine**: `Triage` -> `Reproduce` -> `Surgical Edit` -> `Verify` -> `Review & PR`.
- **Two-Tier Backtrack**: Edit retry loop (up to 3 times) and plan backtrack with Git rollback.
- **Pluggable Execution**: LocalHostRunner with path confinement and DockerRunner.
- **Dual-Mode Provider Support**: Native tool-calling (Claude/Gemini) & Search/Replace blocks (DeepSeek-R1).
- **Git Worktree Isolation**: Safely develops in separate worktrees without dirtying working directory.
- **JSON Checkpoint Persistence**: Resumable task state.
