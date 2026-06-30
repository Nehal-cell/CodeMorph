import json
import logging
from typing import List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from codemorph.models import MigrationReport, FileMigrationReport

logger = logging.getLogger(__name__)

class ReportGenerator:
    def __init__(self):
        self.console = Console()

    def compile_report(self, file_reports: List[FileMigrationReport]) -> MigrationReport:
        """Aggregates individual file reports into a summary MigrationReport."""
        total = len(file_reports)
        migrated = sum(1 for r in file_reports if r.status in ("MIGRATED", "MIGRATED_WITH_WARNINGS"))
        review = sum(1 for r in file_reports if r.status == "NEEDS_HUMAN_REVIEW")
        
        # Calculate rates
        test_pass_before = sum(r.test_pass_rate_before for r in file_reports) / total if total > 0 else 0.0
        test_pass_after = sum(r.test_pass_rate_after for r in file_reports) / total if total > 0 else 0.0
        
        # Estimate review time
        # MIGRATED = 3 mins, MIGRATED_WITH_WARNINGS = 10 mins, NEEDS_HUMAN_REVIEW = 30 mins
        est_time = 0
        for r in file_reports:
            if r.status == "MIGRATED":
                est_time += 3
            elif r.status == "MIGRATED_WITH_WARNINGS":
                est_time += 10
            elif r.status == "NEEDS_HUMAN_REVIEW":
                est_time += 30

        return MigrationReport(
            total_files=total,
            migrated_files=migrated,
            needs_review_files=review,
            test_pass_rate_before=test_pass_before,
            test_pass_rate_after=test_pass_after,
            file_reports=file_reports,
            estimated_review_time_mins=est_time
        )

    def generate_markdown(self, report: MigrationReport) -> str:
        """Generates a markdown formatted summary."""
        md = f"""# CodeMorph Migration Report

## Executive Summary
- **Total Files Scanned**: {report.total_files}
- **Successfully Migrated**: {report.migrated_files} / {report.total_files} ({ (report.migrated_files / report.total_files * 100) if report.total_files > 0 else 0.0:.1f}%)
- **Needs Human Review**: {report.needs_review_files}
- **Test Pass Rate (Before)**: {report.test_pass_rate_before * 100:.1f}%
- **Test Pass Rate (After)**: {report.test_pass_rate_after * 100:.1f}%
- **Estimated Review Time**: {report.estimated_review_time_mins} minutes

---

## File Details

| File Path | Status | Retries | Semantic Score | Intent Summary |
| :--- | :--- | :---: | :---: | :--- |
"""
        for f in report.file_reports:
            score_str = f"{f.semantic_diff_score:.2f}" if f.semantic_diff_score is not None else "N/A"
            md += f"| `{f.filepath}` | `{f.status}` | {f.retries_needed} | {score_str} | {f.intent_summary} |\n"

        return md

    def generate_json(self, report: MigrationReport) -> str:
        """Dumps the migration report to a JSON string."""
        return report.model_dump_json(indent=2)

    def print_terminal_table(self, report: MigrationReport):
        """Displays a Rich styled panel and table to stdout."""
        # 1. Print Summary Panel
        summary_text = (
            f"[bold]Total Files:[/bold] {report.total_files}\n"
            f"[bold green]Migrated:[/bold green] {report.migrated_files}\n"
            f"[bold red]Needs Review:[/bold red] {report.needs_review_files}\n"
            f"[bold]Test Pass Rate (Before/After):[/bold] {report.test_pass_rate_before*100:.1f}% -> {report.test_pass_rate_after*100:.1f}%\n"
            f"[bold yellow]Est. Review Time:[/bold yellow] {report.estimated_review_time_mins} minutes"
        )
        self.console.print(Panel(summary_text, title="CodeMorph Migration Summary", expand=False))

        # 2. Print Detailed Table
        table = Table(title="File Migration Breakdown")
        table.add_column("File Path", style="cyan")
        table.add_column("Status", style="magenta")
        table.add_column("Retries", justify="right", style="green")
        table.add_column("Semantic Score", justify="right", style="yellow")
        table.add_column("Intent Summary", style="dim")

        for f in report.file_reports:
            status_style = "green" if f.status in ("MIGRATED", "MIGRATED_WITH_WARNINGS") else "red"
            score_str = f"{f.semantic_diff_score:.2f}" if f.semantic_diff_score is not None else "N/A"
            table.add_row(
                f.filepath,
                f"[{status_style}]{f.status}[/{status_style}]",
                str(f.retries_needed),
                score_str,
                f.intent_summary[:60] + "..." if len(f.intent_summary) > 60 else f.intent_summary
            )

        self.console.print(table)
