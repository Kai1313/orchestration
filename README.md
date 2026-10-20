# 🤖 Orchestrator

**Autonomous AI Software Development Orchestration Engine**

An autonomous, deterministic agentic system designed to solve discrete software issues and bugs following a rigorous **Test-Driven Development (TDD) assembly line**. It reproduces defects with failing tests, performs surgical search-and-replace code edits, executes automated verification in isolated environments, and outputs clean Git worktree branches with ready-to-merge Pull Requests.

---

## 🌟 Key Features

- **Deterministic 5-Stage TDD State Machine**: Structured assembly line (`Triage` $\to$ `Reproduce` $\to$ `Plan` $\to$ `Surgical Edit` $\to$ `Verify` $\to$ `Review & PR`). Eliminates free-form conversational chatter.
- **Two-Tier Backtrack Policy**:
  - *Tier 1 (Inner Edit Loop)*: Automatically retries code edits up to 3 times against compiler and test runner error traces.
  - *Tier 2 (Plan Backtrack)*: If edits fail repeatedly, reverts uncommitted Git changes and forces the Planner to rethink its hypothesis from scratch (up to 2 backtracks).
- **Pluggable Execution Environments**:
  - `LocalHostRunner`: Rapid local subprocess execution with strict path confinement (blocks directory traversal) and dangerous command filters.
  - `DockerRunner`: Ephemeral container execution via Docker Desktop for untrusted codebases.
- **Hybrid Cost Routing (Paid DeepSeek + 100% Free Gemini)**:
  - Deep architectural planning powered by **DeepSeek-R1** (`deepseek-reasoner`).
  - Precise code edits synthesized by **DeepSeek-V3 / V4** (`deepseek-chat`).
  - Large-context repo triage, test generation, and PR review powered by **Google Gemini 2.5 Flash** (100% Free Tier, 1M context).
- **Dual-Mode Model Protocol**: Seamlessly parses native JSON tool calls or delimited search-and-replace blocks (`<<<<<<< SEARCH ... >>>>>>> REPLACE`) for models like DeepSeek-R1.
- **Git Worktree Isolation**: Executes all changes inside `.orchestrator/worktrees/<branch>`, leaving your active branch, unstaged files, and working tree pristine.
- **State Persistence & Resumability**: Saves full state after every phase to `.orchestrator/runs/<run_id>/state.json`. Resume anytime via `--resume <run_id>`.

---

## 🏗️ Architecture: The 5-Stage TDD Pipeline

```text
[Input: Issue + Repository]
            │
            ▼
   1. TRIAGE & LOCATE
   • Scans AST Repo Map (classes, methods, signatures)
   • Runs ripgrep across codebase
   • Identifies suspected root-cause files
            │
            ▼
   2. REPRODUCE (TDD Red)
   • Writes a standalone test reproducing the issue
   • Executes test command via Runner
   • Asserts test FAILS (Red)
            │
            ▼
   3. SURGICAL EDIT
   • DeepSeek-R1 formulates implementation plan
   • DeepSeek-V3 emits atomic SEARCH/REPLACE blocks
   • Validates all blocks in memory before disk write
            │
            ▼
   4. VERIFY (Inner Loop)
   • Runs test suite (e.g., pytest, npm test)
   │
   ├── [PASS / Green] ──► Advance to Stage 5
   │
   └── [FAIL / Red]   ──► Slices stderr traceback
                          ├── Retry Edit (Max 3 attempts)
                          └── If exhausted: Reset Git & Backtrack to Plan (Max 2 attempts)
            │
            ▼
   5. REVIEW & PR
   • Inspects clean git diff
   • Generates structured Pull Request Title & Markdown Body
   • Commits to isolated Git branch
```

---

## ⚡ Quickstart in 3 Minutes

### 1. Prerequisites
- **Python 3.11+** installed
- **Git** installed and on your PATH
- *(Optional)* **Docker Desktop** (if you want container sandboxing)

### 2. Installation
Clone the repository and set up a virtual environment:

```powershell
# Clone the repository
git clone https://github.com/Kai1313/orchestration.git
cd orchestration

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
# source .venv/bin/activate

# Install orchestrator in editable mode with dev tools
pip install -e .[dev]
```

### 3. Configure API Keys
Copy the example environment file:
```powershell
cp .env.example .env
```

Open `.env` and paste your API keys:
```ini
# DeepSeek API key (paid, pennies per task): https://platform.deepseek.com/
DEEPSEEK_API_KEY=sk-your_deepseek_key_here

# Google Gemini API key (100% Free Tier): https://aistudio.google.com/apikey
GEMINI_API_KEY=AIzaSy_your_gemini_key_here
```

### 4. Verify Configuration
Check that your models and credentials are detected properly:
```powershell
orchestrator config
```
You should see:
```text
              Configured Roles & Model Routing               
+-----------------------------------------------------------+
| Role      | Provider | Model             | API Key Status |
|-----------+----------+-------------------+----------------|
| triage    | gemini   | gemini-2.5-flash  | Found          |
| reproduce | gemini   | gemini-2.5-flash  | Found          |
| planner   | deepseek | deepseek-reasoner | Found          |
| coder     | deepseek | deepseek-chat     | Found          |
| reviewer  | gemini   | gemini-2.5-flash  | Found          |
+-----------------------------------------------------------+
```

---

## 🧪 Try the Included Demo Playground

This repository comes with a built-in broken calculator project inside [`examples/demo_calculator`](examples/demo_calculator) (`add()` subtracts instead of adding).

Run the orchestrator to solve it in one command:

```powershell
orchestrator solve --repo examples/demo_calculator --issue "Fix add() in calculator.py which returns a - b instead of a + b"
```

### What Happens:
1. **Triage**: Detects `calculator.py` using AST Repo Map.
2. **Reproduce**: Writes `tests/test_reproduce_issue.py` asserting `add(2, 3) == 5`. Test fails (Exit code 1).
3. **Plan & Edit**: DeepSeek-R1 formulates a surgical fix, and DeepSeek-V3 replaces `return a - b` with `return a + b`.
4. **Verify**: Test suite runs and passes (Green).
5. **PR**: Commits the verified fix to branch `fix/run_<id>` and generates a Pull Request summary.

---

## 📖 CLI Command Reference

### `orchestrator solve`
Autonomously resolves an issue in a repository.

```powershell
orchestrator solve [OPTIONS]
```

| Flag | Short | Default | Description |
| :--- | :--- | :--- | :--- |
| `--repo` | `-r` | `.` | Path to the target repository directory |
| `--issue` | `-i` | *(required)* | Issue text description **or** path to a `.md` issue file |
| `--sandbox` | `-s` | `local` | Sandbox mode: `local` (host subprocess) or `docker` (container) |
| `--resume` | | `None` | Resume an interrupted run from checkpoint by its `run_id` |
| `--test-cmd` | | `None` | Override auto-detected test command (e.g. `"poetry run pytest"`) |
| `--config` | `-c` | `orchestrator.yaml` | Path to custom YAML configuration file |

#### Example: Running in a Docker Container
```powershell
orchestrator solve --repo /path/to/untrusted/repo --issue "Fix IndexError in parser" --sandbox docker
```

#### Example: Resuming an Interrupted Run
```powershell
orchestrator solve --repo . --issue "..." --resume run_a1b2c3d4
```

---

### `orchestrator status <run_id>`
Inspects checkpoints and post-mortem metrics of a run.

```powershell
orchestrator status run_a1b2c3d4 --repo .
```

Displays phase status, modified files, commit hash, token usage, and error traces.

---

### `orchestrator config`
Prints the loaded provider configuration, role dispatch table, and credential statuses.

---

## ⚙️ Customizing `orchestrator.yaml`

You can customize models, provider endpoints, and budgets in [`orchestrator.yaml`](orchestrator.yaml):

```yaml
max_cost_usd: 2.00          # Stop if spend exceeds $2.00
max_tokens: 500000          # Global token budget per run
test_timeout_seconds: 60    # Timeout per test execution to kill infinite loops
max_edit_retries: 3         # Retries in edit loop before backtracking
max_plan_backtracks: 2      # Plan reformulations before failing gracefully

providers:
  deepseek:
    name: deepseek
    base_url: https://api.deepseek.com
    api_key_env: DEEPSEEK_API_KEY
    default_model: deepseek-chat
  gemini:
    name: gemini
    base_url: https://generativelanguage.googleapis.com/v1beta/openai/
    api_key_env: GEMINI_API_KEY
    default_model: gemini-2.5-flash

roles:
  triage:
    provider: gemini
    model: gemini-2.5-flash
  reproduce:
    provider: gemini
    model: gemini-2.5-flash
  planner:
    provider: deepseek
    model: deepseek-reasoner
  coder:
    provider: deepseek
    model: deepseek-chat
  reviewer:
    provider: gemini
    model: gemini-2.5-flash
```

---

## 🔒 Safety & Sandboxing

1. **Path Confinement**: When running on `local` mode, file reads and writes are strictly jailed within the repository root. Any attempt to access paths like `../../etc/passwd` or outside the repository raises an immediate `PermissionError`.
2. **Dangerous Command Filter**: Shell commands containing patterns like `rm -rf /`, `curl | sh`, modifying `.git/config` credentials, or accessing `~/.ssh` are blocked before execution.
3. **Subprocess Timeout**: Every test and build command has a strict 60-second execution cap to prevent buggy agent edits (e.g., infinite while-loops) from hanging your machine.
4. **Docker Sandbox**: For untrusted third-party repositories, pass `--sandbox docker` to execute commands inside an isolated Docker Desktop container mounting only the repository volume.

---

## 🧪 Running the Test Suite

Run the full unit test suite and deterministic Git fixture harness:

```powershell
pytest -v
```

All 11 tests run in ~3-4 seconds completely offline without consuming external API tokens.

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
