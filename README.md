# CodeMorph — Intent-Preserving Code Migration Agent

CodeMorph is an agentic code migration system that understands developer intent before transforming code. It uses LLMs (like Claude and Gemini) and AST analysis to migrate Python codebases across frameworks with automated correctness verification via existing test suites.

## Features
- **Intent Extraction Engine**: Parses python files using `tree-sitter`, classifies intent for functions/classes, and compiles an `IntentGraph`.
- **Topological Planner**: Automatically schedules migration tasks according to the dependency ordering.
- **Agentic Migration Loop**: Generates updates, runs tests inside a Docker sandbox (with local subprocess fallback), analyzes failures, and self-corrects up to 3 times.
- **Semantic Diff Scorer**: Measures semantic equivalence before and after migration using sentence embeddings.
- **Migration Report**: Emits detailed terminal Rich tables, markdown summaries, and JSON status files.

## Installation

```bash
pip install -e .
```

## Usage

```bash
# Perform a migration dry-run (generates plan and shows tasks)
codemorph dry-run ./my_project

# Run complete migration
codemorph migrate --from flask --to fastapi ./my_project
```
