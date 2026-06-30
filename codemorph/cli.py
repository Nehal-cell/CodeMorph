import os
import json
import logging
import typer
from typing import Optional
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table
from rich.panel import Panel

from codemorph.extractor import IntentExtractor, LLMClient
from codemorph.planner import MigrationPlanner
from codemorph.loop import AgenticLoop
from codemorph.scorer import SemanticScorer
from codemorph.reporter import ReportGenerator
from codemorph.models import FileMigrationReport

# Configure Typer App
app = typer.Typer(help="CodeMorph: Intent-Preserving Code Migration Agent")
console = Console()

def setup_logging(verbose: bool):
    """Sets up Rich-based beautiful logs."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, console=console)]
    )

@app.command()
def dry_run(
    directory: str = typer.Argument(..., help="Path to the codebase directory to scan"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show debug logs")
):
    """Scan code structure, build intent graph, and show the topological migration plan."""
    setup_logging(verbose)
    console.print(f"[bold blue]Starting dry-run for directory:[/bold blue] {directory}")
    
    if not os.path.exists(directory):
        console.print(f"[bold red]Error: Directory does not exist:[/bold red] {directory}")
        raise typer.Exit(code=1)

    # 1. Build Intent Graph (in mock mode to avoid LLM cost on dry-run)
    console.print("[yellow]1. Scanning AST and extracting semantic roles (Dry-Run Mode)...[/yellow]")
    mock_client = LLMClient(provider="mock")
    extractor = IntentExtractor(llm_client=mock_client)
    intent_graph = extractor.build_intent_graph(directory)

    # 2. Compile topological plan
    console.print("[yellow]2. Generating dependency plan...[/yellow]")
    planner = MigrationPlanner()
    plan = planner.create_plan(intent_graph)

    if not plan:
        console.print("[yellow]No Python files found to migrate.[/yellow]")
        return

    # 3. Print topological order
    console.print("\n[bold green]Topological Migration Execution Order:[/bold green]")
    for i, task in enumerate(plan):
        deps_str = f" (Depends on: {', '.join(task.dependencies)})" if task.dependencies else ""
        console.print(f"  {i+1}. [cyan]{task.filepath}[/cyan]{deps_str}")

@app.command()
def status(
    directory: str = typer.Argument(..., help="Path to the codebase directory to inspect")
):
    """Show the progress of an active or completed migration."""
    status_path = os.path.join(directory, ".codemorph_status.json")
    if not os.path.exists(status_path):
        console.print("[yellow]No migration history or active status found in this directory.[/yellow]")
        return

    try:
        with open(status_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        console.print(f"[bold red]Error reading status file: {e}[/bold red]")
        return

    console.print(Panel(
        f"[bold]Migration Status:[/bold] {data.get('status')}\n"
        f"[bold]Progress:[/bold] {data.get('completed')}/{data.get('total')} files completed\n"
        f"[bold]Current Action:[/bold] {data.get('current_action', 'None')}",
        title="CodeMorph Active Status",
        expand=False
    ))

    if data.get("tasks"):
        table = Table(title="Migration Queue")
        table.add_column("File Path", style="cyan")
        table.add_column("Status", style="magenta")
        for t in data["tasks"]:
            table.add_row(t.get("filepath", "Unknown"), t.get("status", "PENDING"))
        console.print(table)

@app.command()
def migrate(
    directory: str = typer.Argument(..., help="Path to the codebase directory to migrate"),
    src_framework: str = typer.Option(..., "--from", help="Source framework (e.g. flask, pandas, unittest)"),
    dst_framework: str = typer.Option(..., "--to", help="Destination framework (e.g. fastapi, polars, pytest)"),
    single_file: Optional[str] = typer.Option(None, "--file", help="Migrate a single file only"),
    max_retries: int = typer.Option(3, "--max-retries", help="Max correction retries per file"),
    use_docker: bool = typer.Option(True, "--docker/--no-docker", help="Run tests in Docker container vs local subprocess"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show debug logs")
):
    """Executes the agentic migration loop across the project files."""
    setup_logging(verbose)
    console.print(f"[bold blue]Starting migration: {src_framework} ➔ {dst_framework}[/bold blue]")
    
    if not os.path.exists(directory):
        console.print(f"[bold red]Error: Directory does not exist:[/bold red] {directory}")
        raise typer.Exit(code=1)

    # Instantiate core systems
    llm_client = LLMClient()
    extractor = IntentExtractor(llm_client=llm_client)
    planner = MigrationPlanner()
    agent_loop = AgenticLoop(workspace_dir=directory, llm_client=llm_client)
    scorer = SemanticScorer(llm_client=llm_client)
    reporter = ReportGenerator()

    # Step 1: Scan and build IntentGraph
    console.print("[yellow]Phase 1: Parsing AST and extracting developer intent...[/yellow]")
    intent_graph = extractor.build_intent_graph(directory)

    # Step 2: Compile migration plan
    console.print("[yellow]Phase 2: Generating topological task schedule...[/yellow]")
    all_tasks = planner.create_plan(intent_graph)

    # Filter tasks if single_file is requested
    tasks_to_run = all_tasks
    if single_file:
        single_abs = os.path.abspath(single_file)
        tasks_to_run = [t for t in all_tasks if os.path.abspath(t.filepath) == single_abs]
        if not tasks_to_run:
            console.print(f"[bold red]Error: Specified file {single_file} not found in dependency graph.[/bold red]")
            raise typer.Exit(code=1)

    if not tasks_to_run:
        console.print("[yellow]No files matched the migration requirements.[/yellow]")
        return

    # Helper to write status to file
    def write_status(status_str, current_act, completed_count):
        status_data = {
            "status": status_str,
            "total": len(tasks_to_run),
            "completed": completed_count,
            "current_action": current_act,
            "tasks": [{"filepath": t.filepath, "status": t.status} for t in all_tasks]
        }
        try:
            with open(os.path.join(directory, ".codemorph_status.json"), "w", encoding="utf-8") as sf:
                json.dump(status_data, sf, indent=2)
        except Exception:
            pass

    write_status("RUNNING", "Running initial test baseline", 0)

    # Step 3: Run baseline test suite
    console.print("[yellow]Phase 3: Running initial test suite to calculate baseline...[/yellow]")
    initial_test = agent_loop.sandbox.run_tests(use_docker=use_docker)
    test_pass_before = 1.0 if initial_test.passed else (
        initial_test.passed_count / initial_test.total if initial_test.total > 0 else 0.0
    )
    console.print(f"Baseline Test Pass Rate: {test_pass_before*100:.1f}% ({initial_test.passed_count}/{initial_test.total} passed)")

    # Step 4: Execute migration loop per task
    console.print("[yellow]Phase 4: Running Agentic Migration Loop...[/yellow]")
    file_reports = []

    for i, task in enumerate(tasks_to_run):
        write_status("RUNNING", f"Migrating {task.filepath}", len(file_reports))

        # Read code before migration for semantic scoring
        with open(task.filepath, "r", encoding="utf-8") as f:
            original_code = f.read()

        # Run loop
        migrated_task = agent_loop.migrate_file(
            task=task,
            src_framework=src_framework,
            dst_framework=dst_framework,
            intent_graph=intent_graph,
            max_retries=max_retries,
            use_docker=use_docker
        )

        # Read code after migration
        with open(task.filepath, "r", encoding="utf-8") as f:
            migrated_code = f.read()

        # Run tests to check after-migration pass rate for this file
        test_after = agent_loop.sandbox.run_tests(use_docker=use_docker)
        test_pass_after = 1.0 if test_after.passed else (
            test_after.passed_count / test_after.total if test_after.total > 0 else 0.0
        )

        # Compute semantic similarity
        sem_score = None
        if migrated_task.status in ("MIGRATED", "MIGRATED_WITH_WARNINGS"):
            sem_score = scorer.compute_similarity(original_code, migrated_code)

        # Gather node descriptions in this file from intent graph
        file_nodes = [
            node for node in intent_graph.nodes.values()
            if os.path.abspath(node.filepath) == os.path.abspath(task.filepath)
        ]
        intent_summary = "; ".join([n.intent or "" for n in file_nodes])

        file_reports.append(
            FileMigrationReport(
                filepath=task.filepath,
                status=migrated_task.status,
                changes=[f"Migrated from {src_framework} to {dst_framework}"],
                intent_summary=intent_summary,
                test_pass_rate_before=test_pass_before, # simplified repository baseline
                test_pass_rate_after=test_pass_after,
                semantic_diff_score=sem_score,
                retries_needed=migrated_task.retries
            )
        )
        write_status("RUNNING", f"Completed {task.filepath}", len(file_reports))

    write_status("COMPLETED", "Migration complete", len(file_reports))

    # Step 5: Compile and output reports
    console.print("[yellow]Phase 5: Compilation of migration reports...[/yellow]")
    summary_report = reporter.compile_report(file_reports)
    
    # Print console report
    reporter.print_terminal_table(summary_report)

    # Write files
    md_content = reporter.generate_markdown(summary_report)
    json_content = reporter.generate_json(summary_report)

    md_report_path = os.path.join(directory, "codemorph_report.md")
    json_report_path = os.path.join(directory, "codemorph_report.json")

    with open(md_report_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    with open(json_report_path, "w", encoding="utf-8") as f:
        f.write(json_content)

    console.print(f"[bold green]Migration complete![/bold green] Reports written to:")
    console.print(f"  - Markdown summary: [cyan]{md_report_path}[/cyan]")
    console.print(f"  - JSON data log: [cyan]{json_report_path}[/cyan]")

if __name__ == "__main__":
    app()
