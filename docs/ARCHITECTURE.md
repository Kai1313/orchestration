# 🏢 Orchestrator: Autonomous Mini Software Office Architecture

## 1. Executive Summary & Core Philosophy

**Orchestrator** is an autonomous, deterministic software development engine designed to resolve discrete software issues and defects without human intervention. 

Unlike interactive conversational assistants (such as Antigravity, Cursor, or ChatGPT) which simulate a single generalist engineer chatting inside an IDE, Orchestrator simulates a **structured mini software engineering office**. Each "desk" in the office represents a specialized role with an isolated context window, an explicit prompt contract, and an optimal AI model chosen for both capability and cost efficiency.

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                  THE MINI SOFTWARE OFFICE ASSEMBLY LINE                                │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘

 [ Issue + Screenshot / Web Repo ]
                 │
                 ▼
 ┌───────────────────────────────┐
 │ Desk 1: Triage Engineer       │ ◄── Google Gemini 3.8 Flash (1M Context, Multimodal Vision)
 │ • AST Repo Map Parsing        │     Cost: $0.00 (Free Tier)
 │ • Multimodal Image Inspection │
 │ • Root-Cause Localization     │
 └───────────────┬───────────────┘
                 │ ── [Structured Triage Analysis & Target Files] ──
                 ▼
 ┌───────────────────────────────┐
 │ Desk 2: QA / Test Engineer    │ ◄── Google Gemini 3.8 Flash
 │ • Writes Reproduction Test    │     Cost: $0.00 (Free Tier)
 │ • Asserts Failing State (Red) │
 └───────────────┬───────────────┘
                 │ ── [Reproduction Script & Red Failure Trace] ──
                 ▼
 ┌───────────────────────────────┐
 │ Desk 3: Systems Architect     │ ◄── DeepSeek-R1 (`deepseek-reasoner`)
 │ • Deep Chain-of-Thought       │     Cost: ~$0.01 - $0.02
 │ • Surgical Step-by-Step Plan  │
 └───────────────┬───────────────┘
                 │ ── [Verbatim Implementation Plan] ──
                 ▼
 ┌───────────────────────────────┐
 │ Desk 4: Core Coder            │ ◄── DeepSeek-V3 (`deepseek-chat`)
 │ • Injects Disk File Context   │     Cost: ~$0.01 - $0.02
 │ • Emits SEARCH/REPLACE Blocks │
 └───────────────┬───────────────┘
                 │ ── [Atomic Code Edits Applied in Memory & Disk] ──
                 ▼
 ┌───────────────────────────────┐
 │ Verification & Test Execution │ ◄── Runner (`LocalHostRunner` or `DockerRunner`)
 └───────┬───────────────┬───────┘
         │               │
  [PASS / Green]   [FAIL / Red Trace]
         │               │
         │               ├── Tier-1 Retry: Slices traceback ──► Return to Desk 4 (Max 3 retries)
         │               │
         │               └── Tier-2 Backtrack: Structured Peer Critique (Max 2 backtracks)
         │                   1. Desk 4 files Obstacle Report
         │                   2. Git resets hard to pristine state
         │                   3. Desk 3 formulates Post-Mortem Plan v2
         ▼
 ┌───────────────────────────────┐
 │ Desk 5: Tech Lead / Reviewer  │ ◄── Google Gemini 3.8 Flash
 │ • Audits Clean Git Diff       │     Cost: $0.00 (Free Tier)
 │ • Generates Structured PR     │
 │ • Commits to Branch           │
 └───────────────────────────────┘
```

---

## 2. Fundamental Architectural Distinctions

Why build a dedicated headless orchestrator when IDE chat agents already exist?

| Dimension | Interactive IDE Agent (e.g., Antigravity, Cursor) | Orchestrator (Mini Software Office) |
| :--- | :--- | :--- |
| **Operating Paradigm** | Interactive pair-programmer engaged in real-time conversational dialogue. | Headless, unattended assembly line executing a deterministic state machine. |
| **Control Flow** | Dynamic ReAct tool loop (agent decides dynamically whether to chat, inspect, or code). | Rigid 5-stage TDD pipeline (`Triage` $\to$ `Reproduce` $\to$ `Plan` $\to$ `Edit` $\to$ `Verify` $\to$ `Review`). |
| **Environment Binding** | Bound to an active desktop IDE window and human session. | Zero UI dependency. Runs in headless CLI, background workers, Docker containers, or CI/CD pipelines. |
| **Model Strategy** | Single selected frontier model (Claude 3.7 Sonnet, GPT-4o, etc.). | Heterogeneous cost-optimized routing: Free Gemini 3.8 Flash + Low-cost DeepSeek-R1 & V3. |
| **Token Economics** | Context window swells monotonically with conversational history, increasing cost per turn. | Isolated phase context windows. Total run cost remains bounded at **~$0.03 – $0.05 per bug fix**. |
| **Backtrack Policy** | Open-ended conversational correction ("Try again with this fix..."). | Formal Two-Tier Backtrack state machine with git rollbacks and peer critique protocols. |
| **Sandboxing** | Runs with ambient developer terminal permissions. | Configurable `LocalHostRunner` (path jailed, command filter) or `DockerRunner` container sandboxes. |

---

## 3. The Desk Roster & Responsibilities

### Desk 1: Triage Engineer
- **Engine**: Google Gemini 3.8 Flash (100% Free Tier, 1M Token Context).
- **Inputs**: Issue prompt, optional visual screenshot (`--image`), AST repository map (`repomap.py`), and indexed symbol skeletons.
- **Responsibilities**:
  - Multimodal vision inspection of UI bugs and error screenshots.
  - Heuristic ripgrep searches across the target repository.
  - Monorepo directory pruning (excludes `vendor/`, `node_modules/`, `storage/`, `dist/`, `.venv/`).
  - Emits the list of **Target Files** suspected of containing the defect.

### Desk 2: QA & Test Engineer
- **Engine**: Google Gemini 3.8 Flash.
- **Inputs**: Issue description, target files, repository language conventions.
- **Responsibilities**:
  - Generates a standalone, minimal reproduction test script (e.g. `tests/test_reproduce_issue.py`).
  - Executes the test runner to assert that the test **FAILS (Red)** on the unmodified codebase.
  - Captures and slices the stderr failure traceback.

### Desk 3: Systems Architect
- **Engine**: DeepSeek-R1 (`deepseek-reasoner`).
- **Inputs**: Issue description, reproduction script, failing traceback, verbatim target file skeletons.
- **Responsibilities**:
  - Conducts deep chain-of-thought architectural reasoning.
  - Identifies the exact functional flaw and root cause.
  - Formulates an atomic, numbered implementation plan specifying exact functions and files.

### Desk 4: Core Coder
- **Engine**: DeepSeek-V3 (`deepseek-chat`).
- **Inputs**: Architectural plan, verbatim file contents read directly from disk, previous compiler/test errors.
- **Responsibilities**:
  - Synthesizes atomic SEARCH/REPLACE blocks.
  - Solves the "Blind Coder" mismatch problem by comparing directly against active disk contents.
  - Emits surgical diffs validated in-memory before any disk modifications.

### Desk 5: Tech Lead / Reviewer
- **Engine**: Google Gemini 3.8 Flash.
- **Inputs**: Clean `git diff`, original issue, verification execution logs.
- **Responsibilities**:
  - Audits diff for regressions, unintended file modifications, or safety violations.
  - Generates structured Pull Request title and Markdown body.
  - Commits verified changes to an isolated Git branch (`fix/run_<id>`).

---

## 4. Phase 2 Expansion: Visual QA Desk (Headless Browser)

For real-world web applications (such as Laravel Blade, React, Vue, or Angular), traditional unit test reproduction is often unavailable or infeasible. Phase 2 introduces the **Visual QA Desk**.

```
                        VISUAL QA HYBRID VERIFICATION
                        
  Target Web Application (e.g., http://localhost:8000)
                         │
                         ▼
             [ Playwright Chromium Headless ]
                         │
        ┌────────────────┴────────────────┐
        ▼                                 ▼
  [ DOM Assertions ]             [ Visual Inspection ]
  • Assert element count         • Pre-fix screenshot (Before)
  • Validate form input          • Post-fix screenshot (After)
        │                                 │
        ▼                                 ▼
  Playwright Test Script          Gemini 3.8 Flash Vision
  (e.g., tests/e2e/pw.spec.js)    "Compare Before vs After:
        │                          Did duplicate icon disappear?"
        │                                 │
        └────────────────┬────────────────┘
                         ▼
            [ Visual QA Verdict: PASS/FAIL ]
```

### Hybrid Architecture (Option C Specification):
1. **Direct Visual Confirmation Agent**:
   - Launches headless Chromium via Playwright.
   - Captures pre-fix screenshot `before.png`.
   - After surgical code edit, invalidates view caches (e.g. `php artisan view:clear`) and captures `after.png`.
   - Passes both images to Gemini 3.8 Flash: *"Verify that the defect depicted in the issue is resolved and no visual regressions were introduced."*
2. **Playwright Script Synthesizer**:
   - Synthesizes an automated Playwright spec file (`tests/e2e/test_visual_fix.spec.js`) asserting DOM state (e.g. `expect(page.locator('.eye-icon')).toHaveCount(1)`).
   - Commits this test script alongside the code fix to prevent future regressions.

---

## 5. Inter-Desk Protocol: Strict Artifact Contracts

Many multi-agent frameworks fail in production because they permit unconstrained natural language chatting between agents, creating token spirals, hallucination drift, and unpredictable execution loops.

Orchestrator enforces **Strict Artifact Handoffs**:

```text
Desk 1 (Triage)    ──► [TriageAnalysis JSON + TargetFiles List] ──► Desk 2 & 3
Desk 2 (QA)        ──► [ReproductionScript + ErrorTrace Slice]  ──► Desk 3
Desk 3 (Architect) ──► [Structured Markdown Implementation Plan] ──► Desk 4
Desk 4 (Coder)     ──► [Atomic SEARCH/REPLACE Block Payload]    ──► Runner / Disk
Desk 5 (Reviewer)  ──► [PullRequest Markdown Artifact]          ──► Git Commit
```

Zero conversational filler words ("Sure!", "Let me think", "I agree") are passed between desks. Every handoff is an immutable, schema-validated artifact.

---

## 6. Tier-2 Backtrack: Structured Peer Critique Protocol

When code edits fail compiler or test verification 3 times consecutively, the system escalates from the **Tier-1 Inner Edit Loop** to the **Tier-2 Plan Backtrack**.

Instead of having the Architect formulate a new plan in a vacuum, Orchestrator executes a structured **1-turn Peer Critique**:

```
 ┌───────────────────────────────────────────────────────────────┐
 │               TIER-2 BACKTRACK PEER CRITIQUE                  │
 └───────────────────────────────────────────────────────────────┘

  [Edit Attempts 1, 2, 3 Fail Verification]
                     │
                     ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ Step 1: Coder Obstacle Report                               │
  │ Desk 4 documents concrete technical blockers:               │
  │ - Why the Architect's hypothesis failed on disk             │
  │ - Compiler / AST errors encountered                         │
  │ - Missing dependencies or architectural misconceptions       │
  └──────────────────────────────┬──────────────────────────────┘
                                 │
                                 ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ Step 2: Git Rollback                                        │
  │ `git reset --hard` rolls back uncommitted changes to        │
  │ ensure zero state contamination.                            │
  └──────────────────────────────┬──────────────────────────────┘
                                 │
                                 ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ Step 3: Architect Post-Mortem Plan v2                       │
  │ Desk 3 (DeepSeek-R1) evaluates:                             │
  │ - Original Issue + Reproduction Trace                       │
  │ - Coder Obstacle Report                                     │
  │ Synthesizes a completely revised architectural strategy.    │
  └──────────────────────────────┬──────────────────────────────┘
                                 │
                                 ▼
  [Return to Desk 4 for Clean Surgical Edit Attempt]
```

This protocol forces the Architect to discard false assumptions while maintaining bounded, deterministic execution (capped at 2 plan backtracks maximum).

---

## 7. Mission Control Dashboard Specification

To give developers visibility into the mini-office operations, Orchestrator implements a two-phase Mission Control interface:

### Phase 2A: Terminal Live TUI (`Rich.Live`)
A self-contained terminal interface rendering real-time operational status without starting extra servers:

```text
┌─ Mini Software Office: Mission Control ─────────────────────────┐
│ Active Run: run_fd8f86df | Repo: /customs/labarugi (Branch: fix)│
├──────────────────────────────────┬──────────────────────────────┤
│ Desks Status                     │ Live Telemetry               │
│ • [✓] Desk 1: Triage (Gemini)    │ Total Tokens : 25,096        │
│ • [✓] Desk 2: QA Repro (Gemini)  │ Est. Cost    : $0.0387       │
│ • [✓] Desk 3: Architect (R1)     │ Elapsed Time : 42.4s         │
│ • [●] Desk 4: Coder (V3) [Edit 1]│ Active Model : deepseek-chat │
│ • [ ] Desk 5: Reviewer (Gemini)  │ Phase Status : RUNNING       │
├──────────────────────────────────┴──────────────────────────────┤
│ Live Code Diff Stream                                           │
│  resources/js/app.js                                            │
│  - <i class="eye-icon-duplicate"></i>                           │
│  + <i class="eye-icon-single" id="pwdToggle"></i>               │
└─────────────────────────────────────────────────────────────────┘
```

### Phase 2B: Local Web Mission Control (FastAPI/HTML)
- Real-time SSE (Server-Sent Events) streaming run state to a local dashboard (`http://localhost:5000`).
- Visual side-by-side Before/After screenshot comparison.
- Historical run catalog with token burn charts and one-click Git branch checkout.
