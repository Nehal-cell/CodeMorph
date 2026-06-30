import os
import sys
import json
import logging
from rich.console import Console
from rich.table import Table

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from codemorph.extractor import IntentExtractor, LLMClient
from codemorph.models import IntentNode

console = Console()

def run_evaluation(suite_path: str):
    console.print(f"[bold blue]CodeMorph Evaluation Harness[/bold blue]")
    
    if not os.path.exists(suite_path):
        console.print(f"[bold red]Error: Suite file not found at {suite_path}[/bold red]")
        sys.exit(1)

    with open(suite_path, "r", encoding="utf-8") as f:
        suite = json.load(f)

    functions = suite.get("functions", [])
    if not functions:
        console.print("[yellow]No functions found in suite to evaluate.[/yellow]")
        return

    # Use Mock LLM if no keys are in environment for local testability
    llm_client = LLMClient()
    extractor = IntentExtractor(llm_client=llm_client)

    console.print(f"Loaded {len(functions)} functions. Running evaluation...")
    
    results = []
    correct = 0

    table = Table(title="Evaluation Harness Metrics")
    table.add_column("Function Name", style="cyan")
    table.add_column("Expected Role", style="green")
    table.add_column("Extracted Role", style="magenta")
    table.add_column("Match", justify="center")

    for func in functions:
        # Construct temporary IntentNode
        node = IntentNode(
            name=func["name"],
            type="function" if "class" not in func["code"] else "class",
            code=func["code"],
            filepath="dummy.py",
            line_range=(1, len(func["code"].splitlines()))
        )

        role, intent = extractor.extract_intent(node)
        
        is_match = (role.lower() == func["expected_role"].lower())
        if is_match:
            correct += 1
            match_str = "[bold green]✓[/bold green]"
        else:
            match_str = "[bold red]✗[/bold red]"

        table.add_row(func["name"], func["expected_role"], role, match_str)
        results.append({
            "name": func["name"],
            "expected": func["expected_role"],
            "actual": role,
            "match": is_match
        })

    console.print(table)
    
    accuracy = (correct / len(functions)) * 100
    console.print(f"\n[bold]Total Functions Evaluated:[/bold] {len(functions)}")
    console.print(f"[bold]Correct Classifications:[/bold] {correct}")
    console.print(f"[bold]Accuracy Rate:[/bold] [yellow]{accuracy:.2f}%[/yellow]")

    # Check P0 threshold:
    if llm_client.provider != "mock" and accuracy < 85.0:
         console.print("[bold red]Warning: Classification accuracy is below the P0 target of 85%.[/bold red]")
    else:
         console.print("[bold green]Success: Classification accuracy meets performance targets.[/bold green]")

if __name__ == "__main__":
    suite_file = os.path.join(os.path.dirname(__file__), "benchmark_suite.json")
    run_evaluation(suite_file)
