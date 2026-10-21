# 🤖 Orchestrator

**Autonomous AI Mini Software Office & TDD Orchestration Engine**

An autonomous, deterministic agentic system designed to solve discrete software issues and defects following a rigorous **assembly line of specialized AI desks**. It reproduces defects with failing tests, formulates deep architectural plans, performs surgical code edits, executes automated verification in isolated environments, and outputs clean Git branches with ready-to-merge Pull Requests.

> 📘 **Full Architecture Specification**: Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for complete technical blueprints of all 5 desks, Phase 2 Visual QA, Tier-2 Peer Critique protocols, and state machine internals.

---

## 🏢 The Paradigm: A "Mini Software Office" (vs. IDE Chatbots)

Most AI coding tools (such as Antigravity, Cursor, or ChatGPT) operate as an **interactive, generalist conversational chatbot** bound to an active IDE window. One model attempts to be customer support, software architect, code writer, and tester all at once, leading to token bloat and conversational drift.

**Orchestrator** operates as a **deterministic, headless software office** with specialized desks, strict artifact handoffs, and heterogeneous model routing:

```text
[ Input: Issue / Bug Report + Screenshot ]
                    │
                    ▼
 ┌──────────────────────────────────────┐
 │ Desk 1: Triage Engineer              │ ◄── Google Gemini 3.8 Flash (1M Context)
 │ • AST Repo Map & Ripgrep Parsing     │     Cost: $0.00 (Free Tier)
 │ • Multimodal Screenshot Inspection   │
 └──────────────────┬───────────────────┘
                    │ ── [Target Files & Triage Report] ──
                    ▼
 ┌──────────────────────────────────────┐
 │ Desk 2: QA & Test Engineer           │ ◄── Google Gemini 3.8 Flash
 │ • Writes Reproduction Test Case      │     Cost: $0.00 (Free Tier)
 │ • Asserts Failing Behavior (Red)     │
 └──────────────────┬───────────────────┘
                    │ ── [Test Script & Failure Trace] ──
                    ▼
 ┌──────────────────────────────────────┐
 │ Desk 3: Systems Architect            │ ◄── DeepSeek-R1 (`deepseek-reasoner`)
 │ • Deep Chain-of-Thought Reasoning    │     Cost: ~$0.01 - $0.02
 │ • Surgical Step-by-Step Fix Plan     │
 └──────────────────┬───────────────────┘
                    │ ── [Implementation Plan] ──
                    ▼
 ┌──────────────────────────────────────┐
 │ Desk 4: Core Coder                   │ ◄── DeepSeek-V3 (`deepseek-chat`)
 │ • Injects Disk File Context          │     Cost: ~$0.01 - $0.02
 │ • Emits Atomic SEARCH/REPLACE Blocks │
 └──────────────────┬───────────────────┘
                    │ ── [Atomic Code Edits] ──
                    ▼
 ┌──────────────────────────────────────┐
 │ Verification & Test Execution        │ ◄── Runner (`LocalHost` or `Docker`)
 └──────────┬───────────────────┬───────┘
            │                   │
     [PASS / Green]       [FAIL / Red]
            │                   │
            │                   ├── Tier 1: Slices trace ──► Retry Coder (Max 3 attempts)
            │                   │
            │                   └── Tier 2: Plan Backtrack (Max 2 backtracks)
            │                       • Coder files structured Obstacle Report
            │                       • Git resets hard to pristine state
            │                       • Architect formulates Post-Mortem Plan v2
            ▼
 ┌──────────────────────────────────────┐
 │ Desk 5: Tech Lead / Reviewer         │ ◄── Google Gemini 3.8 Flash
 │ • Audits Clean Git Diff              │     Cost: $0.00 (Free Tier)
 │ • Generates Structured PR Markdown   │
 │ • Commits to Branch (`fix/run_<id>`) │
 └──────────────────────────────────────┘
```

### Architectural Comparison Matrix

| Dimension | Interactive IDE Agent (Antigravity, Cursor) | Orchestrator (Mini Software Office) |
| :--- | :--- | :--- |
| **Operating Paradigm** | Interactive pair-programmer engaged in real-time conversational chat. | Headless, unattended assembly line executing a deterministic state machine. |
| **Control Flow** | Dynamic ReAct tool loop (agent dynamically decides actions based on chat history). | Rigid 5-stage TDD pipeline (`Triage` $\to$ `Reproduce` $\to$ `Plan` $\to$ `Edit` $\to$ `Verify` $\to$ `Review`). |
| **Environment Binding** | Bound to an active desktop IDE window and human session. | Zero UI dependency. Runs in headless CLI, background workers, Docker containers, or CI/CD pipelines. |
| **Model Strategy** | Single selected frontier model (Claude 3.7 Sonnet, GPT-4o, etc.). | Heterogeneous cost routing: Free Gemini 3.8 Flash + Low-cost DeepSeek-R1 & V3. |
| **Token Economics** | Context window swells monotonically with conversational history. | Isolated phase context windows. Total run cost remains bounded at **~$0.03 – $0.05 per bug fix**. |
| **Handoff Protocol** | Conversational chat ("Thanks, now do this..."). | Strict, schema-validated artifact handoffs (no natural language banter). |
| **Backtrack Policy** | Open-ended conversational correction. | Formal Two-Tier Backtrack state machine with git rollbacks and peer critique protocols. |
| **Sandboxing** | Runs with ambient developer terminal permissions. | Configurable `LocalHostRunner` (path jailed, command filter) or `DockerRunner` container sandboxes. |

---

## 🌟 Key Features

- **Deterministic 5-Stage TDD State Machine**: Structured assembly line (`Triage` $\to$ `Reproduce` $\to$ `Plan` $\to$ `Surgical Edit` $\to$ `Verify` $\to$ `Review & PR`). Eliminates free-form conversational chatter.
- **Multimodal Visual Issue Resolution (`--image`)**: Inspects UI bugs and error screenshots using Gemini 3.8 Flash Vision to localize frontend defects.
- **Web Monorepo Support (`--web`, `--in-place`)**: In-place git branching with automatic view cache invalidation (e.g., `php artisan view:clear`) for rapid live verification against local web servers.
- **Two-Tier Backtrack Policy**:
  - *Tier 1 (Inner Edit Loop)*: Automatically retries code edits up to 3 times against compiler and test runner error traces.
  - *Tier 2 (Plan Backtrack)*: If edits fail repeatedly, reverts uncommitted Git changes and forces the Planner to rethink its hypothesis from scratch (up to 2 backtracks).
- **Pluggable Execution Environments**:
  - `LocalHostRunner`: Rapid local subprocess execution with strict path confinement (blocks directory traversal) and dangerous command filters.
  - `DockerRunner`: Ephemeral container execution via Docker Desktop for untrusted codebases.
- **Hybrid Cost Routing (Paid DeepSeek + 100% Free Gemini)**:
  - Deep architectural planning powered by **DeepSeek-R1** (`deepseek-reasoner`).
  - Precise code edits synthesized by **DeepSeek-V3** (`deepseek-chat`).
  - Large-context repo triage, test generation, and PR review powered by **Google Gemini 3.8 Flash** (100% Free Tier, 1M context).
- **Dual-Mode Model Protocol**: Seamlessly parses native JSON tool calls or delimited search-and-replace blocks (`<<<<<<< SEARCH ... >>>>>>> REPLACE`) for reasoning models like DeepSeek-R1.
- **Git Worktree & In-Place Branching**: Isolated worktrees for background runs, or clean `--in-place` branching for hot-reloading dev environments.
- **State Persistence & Resumability**: Saves full state after every phase to `.orchestrator/runs/<run_id>/state.json`. Resume anytime via `--resume <run_id>`.

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
| triage    | gemini   | gemini-3.8-flash  | Found          |
| reproduce | gemini   | gemini-3.8-flash  | Found          |
| planner   | deepseek | deepseek-reasoner | Found          |
| coder     | deepseek | deepseek-chat     | Found          |
| reviewer  | gemini   | gemini-3.8-flash  | Found          |
+-----------------------------------------------------------+
```

---

## 🧪 Real-World Benchmark: Solving UI Bugs on Live Monorepos

Orchestrator has been validated on live, real-world full-stack monorepos (such as large Laravel + JavaScript applications).

### Example: Fixing Duplicate Modal Eye Icons
```powershell
orchestrator solve `
  --repo "C:\laragon\www\customs\labarugi" `
  --issue "Fitur show hide password pada modal Verifikasi Keamanan, cukup munculkan satu icon saja jika fungsinya sama" `
  --image "image.png" `
  --web
```

### Result:
- **Triage**: Gemini 3.8 Flash inspected the screenshot, parsed the repo AST, pruned `vendor/` and `node_modules/`, and isolated `resources/js/app.js`.
- **Plan**: DeepSeek-R1 formulated the surgical JavaScript event handler modification.
- **Edit**: DeepSeek-V3 ingested the verbatim disk content and synthesized atomic search-and-replace blocks.
- **Cache Hook**: Automatically invalidated `php artisan view:clear`.
- **Metrics**: Verified, committed to branch `fix/run_fd8f86df`, and merged into Bitbucket `development` for **$0.0387 total spend** across **25,096 tokens**.

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
| `--image` | `-img` | `None` | Path to screenshot or visual issue attachment (passed to Gemini vision) |
| `--web` | | `False` | Web preset (enables in-place editing, skip-verify, and interactive browser preview) |
| `--in-place` | | `False` | Edit directly in active working tree on a new git branch (for hot-reloading dev servers) |
| `--skip-verify` | | `False` | Skip automated test reproduction/verification for untested codebases |
| `--sandbox` | `-s` | `local` | Sandbox mode: `local` (host subprocess) or `docker` (container) |
| `--interactive` | `-it` | `False` | Enable interactive breakpoints on verification failure and PR review |
| `--resume` | | `None` | Resume an interrupted run from checkpoint by its `run_id` |
| `--test-cmd` | | `None` | Override auto-detected test command (e.g. `"poetry run pytest"`) |
| `--config` | `-c` | `orchestrator.yaml` | Path to custom YAML configuration file |

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
    default_model: gemini-3.8-flash

roles:
  triage:
    provider: gemini
    model: gemini-3.8-flash
  reproduce:
    provider: gemini
    model: gemini-3.8-flash
  planner:
    provider: deepseek
    model: deepseek-reasoner
  coder:
    provider: deepseek
    model: deepseek-chat
  reviewer:
    provider: gemini
    model: gemini-3.8-flash
```

---

## 🔒 Safety & Sandboxing

1. **Path Confinement**: When running on `local` mode, file reads and writes are strictly jailed within the repository root. Any attempt to access paths like `../../etc/passwd` or outside the repository raises an immediate `PermissionError`.
2. **Dangerous Command Filter**: Shell commands containing patterns like `rm -rf /`, `curl | sh`, modifying `.git/config` credentials, or accessing `~/.ssh` are blocked before execution.
3. **Subprocess Timeout**: Every test and build command has a strict 60-second execution cap to prevent buggy agent edits (e.g., infinite while-loops) from hanging your machine.
4. **Docker Sandbox**: For untrusted third-party repositories, pass `--sandbox docker` to execute commands inside an isolated Docker Desktop container mounting only the repository volume.

---

## 🚀 Phase 2 Roadmap & Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for full design specifications of the upcoming enhancements:

1. **Visual QA Desk (Headless Browser Hybrid)**:
   - Automated headless Chromium execution via Playwright.
   - Dual-verification: automated DOM assertions combined with Before/After screenshot diffing using Gemini 3.8 Flash Vision.
2. **Structured Tier-2 Peer Critique**:
   - Structured handoff protocol when edit attempts fail: Desk 4 (Coder) files an `Obstacle Report` before git rollback, enabling Desk 3 (Architect) to formulate a targeted `Post-Mortem Plan v2`.
3. **Mission Control Dashboard**:
   - **Phase 2A**: Real-time Terminal Live UI (`Rich.Live`) displaying desk statuses, token burn meters, and scrolling git diffs.
   - **Phase 2B**: Local Web Mission Control (FastAPI/HTML) for job management and visual screenshot comparison.

---

## 🧪 Running the Test Suite

Run the full unit test suite and deterministic Git fixture harness:

```powershell
pytest -v
```

All 26 tests run in ~3-5 seconds completely offline without consuming external API tokens.

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
