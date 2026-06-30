import os
import logging
from typing import List, Dict, Optional, Tuple

from codemorph.models import MigrationTask, IntentGraph, TestResult, TestFailure
from codemorph.extractor import LLMClient
from codemorph.sandbox import SandboxManager

logger = logging.getLogger(__name__)

MIGRATION_CONTEXTS = {
    ("flask", "fastapi"): """
- Flask to FastAPI Web Migration:
  - Convert Flask app creation `app = Flask(__name__)` to `app = FastAPI()`.
  - Map endpoints: `@app.route('/path', methods=['GET'])` to `@app.get('/path')`.
  - Map POST: `@app.route('/path', methods=['POST'])` to `@app.post('/path')`.
  - Flask `request.json` / `request.args` should be converted to FastAPI parameters or Pydantic request bodies.
  - Use `async def` for route handlers to support async operations in FastAPI.
  - Response parsing: Flask returning `jsonify(...)` or tuples should return Pydantic models or standard dicts/lists.
""",
    ("pandas", "polars"): """
- Pandas to Polars Migration:
  - Replace `import pandas as pd` with `import polars as pl`.
  - Convert `pd.read_csv(...)` to `pl.read_csv(...)` or `pl.scan_csv(...)`.
  - Replace Pandas indexing/selection `.loc` or `.iloc` with Polars expressions.
  - Convert groupby and aggregate `.groupby('col').agg({'val': 'sum'})` to Polars expressions `.group_by('col').agg(pl.col('val').sum())`.
  - Leverage Polars lazy evaluation: use `.lazy()` followed by operations and `.collect()` where appropriate.
""",
    ("tensorflow", "pytorch"): """
- TensorFlow/Keras to PyTorch ML Migration:
  - Convert models subclassing `tf.keras.Model` or `tf.keras.layers.Layer` to subclasses of `torch.nn.Module`.
  - Convert Keras constructor layers (e.g., `layers.Dense(units)`) to PyTorch modules (`nn.Linear(in_features, out_features)`) defined in `__init__`.
  - Rename the execution method `call(self, inputs)` to `forward(self, x)`.
  - Translate tensor operations (e.g., `tf.reduce_mean` -> `torch.mean`, `tf.concat` -> `torch.cat`).
""",
    ("celery", "dramatiq"): """
- Celery to Dramatiq Task Queue Migration:
  - Replace celery task definitions `@app.task` with `@dramatiq.actor`.
  - Replace task execution calls `task.delay(args)` or `task.apply_async(args)` with `task.send(args)`.
  - Replace broker configuration parameters with Dramatiq broker setups (e.g., `RabbitmqBroker` or `RedisBroker`).
""",
    ("unittest", "pytest"): """
- Unittest to Pytest Testing Migration:
  - Remove inheritance from `unittest.TestCase` and make test classes plain classes or use module-level test functions.
  - Replace `setUp(self)` and `tearDown(self)` with pytest fixtures (`@pytest.fixture`).
  - Replace assertion calls (e.g., `self.assertEqual(a, b)`, `self.assertTrue(x)`) with raw python assert statements (`assert a == b`, `assert x`).
""",
    ("sqlalchemy1", "sqlalchemy2"): """
- SQLAlchemy 1.x to 2.x ORM Migration:
  - Replace query style `session.query(User).filter_by(name=name).first()` with modern execute/select: `session.execute(select(User).filter_by(name=name)).scalars().first()`.
  - Convert declarative mapping definitions to 2.0 style using `Mapped` and `mapped_column` type annotations.
  - Ensure session management handles transaction lifecycles explicitly.
"""
}

class AgenticLoop:
    def __init__(self, workspace_dir: str, llm_client: Optional[LLMClient] = None):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.llm = llm_client or LLMClient()
        self.sandbox = SandboxManager(self.workspace_dir)

    def migrate_file(
        self,
        task: MigrationTask,
        src_framework: str,
        dst_framework: str,
        intent_graph: IntentGraph,
        max_retries: int = 3,
        use_docker: bool = True
    ) -> MigrationTask:
        """Executes the generate-test-reflect-retry loop for a single file."""
        logger.info(f"Starting migration for {task.filepath} ({src_framework} -> {dst_framework})")
        
        # Load original content
        with open(task.filepath, "r", encoding="utf-8") as f:
            original_code = f.read()

        # Gather node descriptions in this file from intent graph
        file_nodes = [
            node for node in intent_graph.nodes.values()
            if os.path.abspath(node.filepath) == os.path.abspath(task.filepath)
        ]

        intent_summary = "\n".join([
            f"- Component '{n.name}' ({n.type}) role: {n.role or 'other'}. Intent: {n.intent or 'None'}"
            for n in file_nodes
        ])

        # Get relevant context
        migration_context = MIGRATION_CONTEXTS.get(
            (src_framework.lower(), dst_framework.lower()), 
            f"- Migrate code from {src_framework} syntax to {dst_framework} syntax."
        )

        task.status = "IN_PROGRESS"
        
        for attempt in range(max_retries + 1):
            task.retries = attempt
            logger.info(f"Attempt {attempt}/{max_retries} for {task.filepath}")

            # 1. Generate code
            generated_code = self._generate_code(
                filepath=task.filepath,
                original_code=original_code,
                intent_summary=intent_summary,
                migration_context=migration_context,
                reflection_history=task.reflection_history
            )

            # 2. Write file
            with open(task.filepath, "w", encoding="utf-8") as f:
                f.write(generated_code)

            # 3. Run tests
            test_result = self.sandbox.run_tests(use_docker=use_docker)
            logger.info(f"Tests status: Passed={test_result.passed}, Failures={test_result.failed_count}")

            if test_result.passed:
                logger.info(f"Successfully migrated {task.filepath} on attempt {attempt}.")
                task.status = "MIGRATED" if attempt == 0 else "MIGRATED_WITH_WARNINGS"
                return task

            # 4. If failed and we have retries left, reflect and diagnostic
            if attempt < max_retries:
                reflection = self._reflect_on_failure(
                    generated_code=generated_code,
                    test_failures=test_result.failures,
                    raw_output=test_result.output
                )
                logger.info(f"Generated reflection for next attempt: {reflection[:100]}...")
                task.reflection_history.append(reflection)
            else:
                # Retries exhausted
                logger.warning(f"Failed to migrate {task.filepath} after {max_retries} retries.")
                task.status = "NEEDS_HUMAN_REVIEW"
                
                # Annotate file with warning headers explaining failures
                self._annotate_file_with_warnings(task.filepath, generated_code, test_result.failures)

        return task

    def _generate_code(
        self,
        filepath: str,
        original_code: str,
        intent_summary: str,
        migration_context: str,
        reflection_history: List[str]
    ) -> str:
        """Call LLM to generate migrated file code."""
        prompt = f"""You are an expert code migrator. Your goal is to migrate the following python file to a new framework while preserving its exact business logic and semantic intent.

File: {filepath}

--- SEMANTIC INTENT OF COMPONENTS ---
{intent_summary}

--- MIGRATION GUIDELINES ---
{migration_context}

--- ORIGINAL CODE ---
```python
{original_code}
```
"""
        if reflection_history:
            prompt += "\n--- PREVIOUS ATTEMPTS AND TEST FAILURES ---\n"
            for i, refl in enumerate(reflection_history):
                prompt += f"\n[Attempt {i+1} Failure Reflection]:\n{refl}\n"
            prompt += "\nPlease correct the issues identified in the reflections above. Do not repeat the same mistakes."

        prompt += """
Provide the fully migrated, complete code for the file. Ensure the syntax is completely valid and imports are corrected.
Provide ONLY the raw python code in your response, without markdown wrapping or comments external to the code. Do not include ```python or ``` wrapping.
"""
        
        system_prompt = "You are an expert agentic code migration tool. Return only clean, runnable python code."
        code = self.llm.generate(prompt, system_prompt=system_prompt)
        
        # Clean up any residual markdown formatting
        code = code.strip()
        if code.startswith("```python"):
            code = code[9:]
        if code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]
        return code.strip()

    def _reflect_on_failure(self, generated_code: str, test_failures: List[TestFailure], raw_output: str) -> str:
        """Call LLM to reflect on test failures and generate correction plan."""
        failures_summary = ""
        for tf in test_failures[:5]: # Limit to first 5 failures to manage context size
            failures_summary += f"\n- Test Name: {tf.test_name}\n  Error: {tf.message}\n  Traceback:\n{tf.traceback or 'No traceback available'}\n"

        prompt = f"""You generated the following migrated Python code, but the test suite failed.

--- GENERATED CODE ---
```python
{generated_code}
```

--- TEST FAILURES ---
{failures_summary}

--- RAW TEST CONSOLE OUTPUT ---
{raw_output[:2000]}

Please analyze why the generated code caused these test failures.
Provide a clear explanation of:
1. What went wrong (e.g., missing imports, wrong function signature, incorrect handler returns, etc.).
2. The specific changes needed to fix the code.

Keep your response concise and focused on the solution.
"""
        system_prompt = "You are a debugging assistant explaining test failures and outlining corrections."
        return self.llm.generate(prompt, system_prompt=system_prompt)

    def _annotate_file_with_warnings(self, filepath: str, code: str, failures: List[TestFailure]):
        """Prepends warnings and test failure messages to the top of the migrated file."""
        warning_comment = "# ======================================================================\n"
        warning_comment += "# ⚠️ CODEMORPH WARNING: NEEDS MANUAL DEVELOPER REVIEW\n"
        warning_comment += "# This file was migrated automatically, but the test suite failed.\n"
        warning_comment += "# Please review and fix the remaining failures below.\n"
        warning_comment += "# ======================================================================\n"
        
        for i, tf in enumerate(failures[:3]):
            warning_comment += f"#\n# Failure {i+1}: {tf.test_name}\n"
            warning_comment += f"# Error: {tf.message}\n"
            
        warning_comment += "# ======================================================================\n\n"
        
        annotated_code = warning_comment + code
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(annotated_code)
