# Contributing to CodeMorph

## Prerequisites
- Python 3.11+
- Docker (running locally)
- An Anthropic API key — get one at https://console.anthropic.com

## Local Setup
git clone https://github.com/Nehal-cell/codemorph.git
cd codemorph
pip install -e ".[dev]"
export ANTHROPIC_API_KEY=your_key_here

## Running Tests
pytest

## How to Add a New Migration Pair
1. Create a new file in src/migrations/pairs/
2. Define source and target patterns
3. Add test cases in tests/pairs/
4. Update the supported pairs table in README.md

## PR Guidelines
- Branch name: feature/your-feature or fix/your-fix
- One feature per PR
- All tests must pass before submitting
