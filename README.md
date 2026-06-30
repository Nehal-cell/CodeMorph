# CodeMorph 🔄

> **Intent-preserving code migration agent for Python.**
> CodeMorph understands what your code is *trying to do* before transforming it — not just what it says.
---

## The Problem

Framework migrations are painful. A Flask → FastAPI migration for a mid-size service takes an experienced engineer **2–4 weeks**. Existing tools make it worse, not better:

| Tool | Approach | Why it fails |
|------|----------|-------------|
| Codemods | AST find-and-replace | Breaks on non-standard patterns, no semantic understanding |
| ChatGPT / Copilot | Translate file-by-file on request | No project-wide context, no automated validation, manual per-file |
| Vendor migration guides | Documentation | Still requires manual application by a human |

All of them are **syntactic** — they operate on the text of code without understanding what it's trying to accomplish.

---

## How CodeMorph is Different

CodeMorph is **semantic**. Before touching a single line of code, it builds an *IntentGraph* — a map of what every function and class in your codebase is actually doing. Then it migrates with that understanding, and uses your **existing test suite as a correctness oracle** to verify every change.

```
Traditional tools:   Code ──► Find & Replace ──► Migrated Code (maybe)

CodeMorph:           Code ──► Understand Intent ──► Migrate ──► Run Tests
                                                          ↑          │
                                                          └── Retry ◄┘
```

If a migration breaks a test, CodeMorph reads the failure, reflects on what it misunderstood, and tries again — autonomously.

---

## Supported Migration Pairs

| From | To | Status |
|------|----|--------|
| Flask | FastAPI | ✅ Stable |
| Pandas | Polars | ✅ Stable |
| TensorFlow / Keras | PyTorch | ✅ Stable |
| Celery | Dramatiq | ✅ Stable |
| unittest | pytest | ✅ Stable |
| SQLAlchemy 1.x | SQLAlchemy 2.x | ✅ Stable |

---

## Demo

```bash
# Migrate a Flask project to FastAPI
codemorph migrate --from flask --to fastapi ./my_project

# Preview what will change without touching any files
codemorph dry-run --from pandas --to polars ./my_project

# Migrate a single file
codemorph migrate --from unittest --to pytest ./tests/test_auth.py --file
```

**Example output:**

```
CodeMorph v1.0 — Intent-Preserving Migration
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Analysing codebase...        ████████████████ 100%  (42 files)
Building IntentGraph...      ████████████████ 100%
Migrating files...           ████████████████ 100%

──────────────────────────────────────────────
 Migration Report
──────────────────────────────────────────────
 ✅  MIGRATED                 36 files
 ⚠️   MIGRATED_WITH_WARNINGS   4 files
 🔴  NEEDS_HUMAN_REVIEW        2 files
 ⏭️   SKIPPED                   0 files
──────────────────────────────────────────────
 Test pass rate:   ~80%
 Semantic score:   0.89 mean
 Review estimate:  ~1.5 days
──────────────────────────────────────────────

Full report saved to: codemorph_report.md
```

---

## Installation

**Requirements:** Python 3.11+, Docker (for test sandbox)

```bash
# Install from PyPI
pip install codemorph

# Set your Anthropic API key
export ANTHROPIC_API_KEY=your_key_here
```

Or install from source:

```bash
git clone https://github.com/Nehal-cell/codemorph.git
cd codemorph
pip install -e .
```

---

## Quickstart

```bash
# 1. Navigate to your Python project
cd your_project

# 2. Make sure you have tests (CodeMorph needs them)
pytest  # should show some passing tests

# 3. Run CodeMorph
codemorph migrate --from flask --to fastapi .

# 4. Review the report, check the diff, merge when happy
```

> ⚠️ **Always run on a Git branch.** CodeMorph modifies files in place.
> ```bash
> git checkout -b codemorph/flask-to-fastapi
> codemorph migrate --from flask --to fastapi .
> ```

---

## How It Works

### 1. Intent Extraction
CodeMorph parses your codebase using `tree-sitter` to extract the AST of every function and class. It then calls an LLM to classify the semantic role of each component — *request handler, validator, data transformer, config loader* — and builds an **IntentGraph** describing what your code does, independent of which framework it uses.

### 2. Migration Planning
The Migration Planner topologically sorts your files based on the IntentGraph's dependency map. Files are migrated in the right order so cross-file consistency is maintained throughout.

### 3. Agentic Migration Loop
For each file, CodeMorph:
1. **Generates** a migrated version using the IntentGraph + migration pair context
2. **Applies** the patch to an isolated Docker sandbox
3. **Runs** your existing test suite against the patch
4. **Diagnoses** any failures and reflects: *"What did I misunderstand about the intent?"*
5. **Retries** up to 3 times with improved understanding
6. **Escalates** to `NEEDS_HUMAN_REVIEW` if retries are exhausted

### 4. Semantic Diff Scoring
After a successful migration, CodeMorph computes a semantic similarity score between the original and migrated function using `sentence-transformers`. Files scoring below **0.85** are flagged for extra review even if tests pass.

### 5. Migration Report
A full report is generated as both a terminal summary and a `codemorph_report.md` file — every file, its status, what changed, and why.

---

## CLI Reference

```bash
codemorph migrate   --from <framework> --to <framework> <path>  [--max-retries N] [--file]
codemorph dry-run   --from <framework> --to <framework> <path>
codemorph status    # show progress of an in-progress migration
```

| Flag | Default | Description |
|------|---------|-------------|
| `--from` | required | Source framework |
| `--to` | required | Target framework |
| `--max-retries` | 3 | Max agentic retry attempts per file |
| `--file` | false | Migrate a single file instead of a directory |
| `--dry-run` | false | Preview migration plan without executing |

---

## Benchmark

Tested on real open-source Python repositories:

| Migration Pair | Test Pass Rate (first attempt) | After Retries |
|----------------|-------------------------------|---------------|
| Flask → FastAPI | ~80% | ~90% |
| Pandas → Polars | ~80% | ~89% |
| TF → PyTorch | ~78% | ~88% |
| Celery → Dramatiq | ~81% | ~91% |
| unittest → pytest | ~84% | ~93% |
| SQLAlchemy 1→2 | ~79% | ~88% |

> Benchmarks run on projects with ≥70% test coverage. Lower coverage projects may see reduced accuracy.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| AST Parsing | tree-sitter (Python grammar) |
| Intent Extraction | Anthropic Claude API (claude-sonnet-4-6) |
| Agentic Orchestration | LangGraph |
| Semantic Scoring | sentence-transformers (all-MiniLM-L6-v2) |
| Test Isolation | Docker + pytest |
| CLI | Typer + Rich |

---

## Requirements

- Python 3.11+
- Docker (running locally)
- An Anthropic API key ([get one here](https://console.anthropic.com))
- A Python project with an existing test suite

> CodeMorph is most effective on projects with **≥70% test coverage**. The test suite is its correctness oracle — the more tests you have, the more it can verify.

---

## Roadmap

- [ ] GitHub Action for CI-integrated migrations
- [ ] VS Code extension
- [ ] Multi-file context window for better cross-file consistency
- [ ] JavaScript/TypeScript migration pairs (Express → Hono, Webpack → Vite)
- [ ] Human-in-the-loop mode: pause on `NEEDS_HUMAN_REVIEW` and resume after edits
- [ ] Fine-tuned migration model trained on accepted open-source migration PRs

---

## Contributing

Contributions are welcome — especially new migration pairs and benchmark repos.

```bash
git clone https://github.com/Nehal-cell/codemorph.git
cd codemorph
pip install -e ".[dev]"
pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

MIT — see [LICENSE](LICENSE).

---

## Author

Built by **Nehal** — CS & Design undergrad building AI tools.

[LinkedIn](https://linkedin.com/in/nehal-4b1495329) · [GitHub](https://github.com/Nehal-cell) · [nehalk1805@gmail.com](mailto:nehalk1805@gmail.com)

---

<p align="center">
  <i>Every migration tool today is syntactic. CodeMorph is the first one that's semantic.</i>
</p>
