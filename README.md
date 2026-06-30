CodeMorph 🔄


Intent-preserving code migration agent for Python.
CodeMorph understands what your code is trying to do before transforming it — not just what it says.

The Problem

Framework migrations are painful. A Flask → FastAPI migration for a mid-size service takes an experienced engineer 2–4 weeks. Existing tools make it worse, not better:

ToolApproachWhy it failsCodemodsAST find-and-replaceBreaks on non-standard patterns, no semantic understandingChatGPT / CopilotTranslate file-by-file on requestNo project-wide context, no automated validation, manual per-fileVendor migration guidesDocumentationStill requires manual application by a human

All of them are syntactic — they operate on the text of code without understanding what it's trying to accomplish.


How CodeMorph is Different

CodeMorph is semantic. Before touching a single line of code, it builds an IntentGraph — a map of what every function and class in your codebase is actually doing. Then it migrates with that understanding, and uses your existing test suite as a correctness oracle to verify every change.

Traditional tools:   Code ──► Find & Replace ──► Migrated Code (maybe)

CodeMorph:           Code ──► Understand Intent ──► Migrate ──► Run Tests
                                                          ↑          │
                                                          └── Retry ◄┘

If a migration breaks a test, CodeMorph reads the failure, reflects on what it misunderstood, and tries again — autonomously.


Supported Migration Pairs

FromToStatusFlaskFastAPI✅ StablePandasPolars✅ StableTensorFlow / KerasPyTorch✅ StableCeleryDramatiq✅ Stableunittestpytest✅ StableSQLAlchemy 1.xSQLAlchemy 2.x✅ Stable


Demo

bash# Migrate a Flask project to FastAPI
codemorph migrate --from flask --to fastapi ./my_project

# Preview what will change without touching any files
codemorph dry-run --from pandas --to polars ./my_project

# Migrate a single file
codemorph migrate --from unittest --to pytest ./tests/test_auth.py --file

Example output:

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


Installation

Requirements: Python 3.11+, Docker (for test sandbox)

bash# Install from PyPI
pip install codemorph

# Set your Anthropic API key
export ANTHROPIC_API_KEY=your_key_here

Or install from source:

bashgit clone https://github.com/Nehal-cell/codemorph.git
cd codemorph
pip install -e .


Quickstart

bash# 1. Navigate to your Python project
cd your_project

# 2. Make sure you have tests (CodeMorph needs them)
pytest  # should show some passing tests

# 3. Run CodeMorph
codemorph migrate --from flask --to fastapi .

# 4. Review the report, check the diff, merge when happy


⚠️ Always run on a Git branch. CodeMorph modifies files in place.

bashgit checkout -b codemorph/flask-to-fastapi
codemorph migrate --from flask --to fastapi .




How It Works

1. Intent Extraction

CodeMorph parses your codebase using tree-sitter to extract the AST of every function and class. It then calls an LLM to classify the semantic role of each component — request handler, validator, data transformer, config loader — and builds an IntentGraph describing what your code does, independent of which framework it uses.

2. Migration Planning

The Migration Planner topologically sorts your files based on the IntentGraph's dependency map. Files are migrated in the right order so cross-file consistency is maintained throughout.

3. Agentic Migration Loop

For each file, CodeMorph:


Generates a migrated version using the IntentGraph + migration pair context
Applies the patch to an isolated Docker sandbox
Runs your existing test suite against the patch
Diagnoses any failures and reflects: "What did I misunderstand about the intent?"
Retries up to 3 times with improved understanding
Escalates to NEEDS_HUMAN_REVIEW if retries are exhausted


4. Semantic Diff Scoring

After a successful migration, CodeMorph computes a semantic similarity score between the original and migrated function using sentence-transformers. Files scoring below 0.85 are flagged for extra review even if tests pass.

5. Migration Report

A full report is generated as both a terminal summary and a codemorph_report.md file — every file, its status, what changed, and why.


CLI Reference

bashcodemorph migrate   --from <framework> --to <framework> <path>  [--max-retries N] [--file]
codemorph dry-run   --from <framework> --to <framework> <path>
codemorph status    # show progress of an in-progress migration

FlagDefaultDescription--fromrequiredSource framework--torequiredTarget framework--max-retries3Max agentic retry attempts per file--filefalseMigrate a single file instead of a directory--dry-runfalsePreview migration plan without executing


Benchmark

Tested on real open-source Python repositories:

Migration PairTest Pass Rate (first attempt)After RetriesFlask → FastAPI~80%~90%Pandas → Polars~80%~89%TF → PyTorch~78%~88%Celery → Dramatiq~81%~91%unittest → pytest~84%~93%SQLAlchemy 1→2~79%~88%


Benchmarks run on projects with ≥70% test coverage. Lower coverage projects may see reduced accuracy.




Tech Stack

ComponentTechnologyAST Parsingtree-sitter (Python grammar)Intent ExtractionAnthropic Claude API (claude-sonnet-4-6)Agentic OrchestrationLangGraphSemantic Scoringsentence-transformers (all-MiniLM-L6-v2)Test IsolationDocker + pytestCLITyper + Rich


Requirements


Python 3.11+
Docker (running locally)
An Anthropic API key (get one here)
A Python project with an existing test suite



CodeMorph is most effective on projects with ≥70% test coverage. The test suite is its correctness oracle — the more tests you have, the more it can verify.




Roadmap


 GitHub Action for CI-integrated migrations
 VS Code extension
 Multi-file context window for better cross-file consistency
 JavaScript/TypeScript migration pairs (Express → Hono, Webpack → Vite)
 Human-in-the-loop mode: pause on NEEDS_HUMAN_REVIEW and resume after edits
 Fine-tuned migration model trained on accepted open-source migration PRs



Contributing

Contributions are welcome — especially new migration pairs and benchmark repos.

bashgit clone https://github.com/Nehal-cell/codemorph.git
cd codemorph
pip install -e ".[dev]"
pytest

See CONTRIBUTING.md for guidelines.


License

MIT — see LICENSE.


Author

Built by Nehal — CS & Design undergrad building AI tools.

LinkedIn · GitHub · nehalk1805@gmail.com


<p align="center">
  <i>Every migration tool today is syntactic. CodeMorph is the first one that's semantic.</i>
</p>
