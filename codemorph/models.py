from typing import List, Dict, Tuple, Optional
from pydantic import BaseModel, Field

class IntentNode(BaseModel):
    name: str = Field(..., description="Name of the code unit (function/class name)")
    type: str = Field(..., description="Type of the unit: 'function', 'class', or 'module'")
    role: Optional[str] = Field(None, description="Semantic role (e.g., 'request_handler', 'validator', 'config')")
    intent: Optional[str] = Field(None, description="Detailed explanation of developer's intent")
    docstring: Optional[str] = Field(None, description="Original docstring of the unit")
    code: str = Field(..., description="Original source code snippet")
    dependencies: List[str] = Field(default_factory=list, description="List of internal dependency names or calls")
    filepath: str = Field(..., description="Path to the file containing this node")
    line_range: Tuple[int, int] = Field(..., description="Start and end line range (1-indexed)")

class IntentGraph(BaseModel):
    nodes: Dict[str, IntentNode] = Field(default_factory=dict, description="Mapping from 'filepath::node_name' to IntentNode")
    dependencies: Dict[str, List[str]] = Field(default_factory=dict, description="Adjacency list of node dependencies")

class MigrationTask(BaseModel):
    id: str = Field(..., description="Unique ID of the task (usually filepath)")
    filepath: str = Field(..., description="Path to the file to be migrated")
    dependencies: List[str] = Field(default_factory=list, description="List of filepaths this file depends on")
    status: str = Field("PENDING", description="Status of task: PENDING, IN_PROGRESS, MIGRATED, MIGRATED_WITH_WARNINGS, NEEDS_HUMAN_REVIEW")
    retries: int = Field(0, description="Number of retries attempted")
    reflection_history: List[str] = Field(default_factory=list, description="History of LLM reflections on test failures")
    semantic_diff_score: Optional[float] = Field(None, description="Semantic similarity between original and migrated files")

class TestFailure(BaseModel):
    test_name: str
    message: str
    traceback: Optional[str] = None

class TestResult(BaseModel):
    passed: bool
    total: int = 0
    passed_count: int = 0
    failed_count: int = 0
    failures: List[TestFailure] = Field(default_factory=list)
    output: str = Field("", description="Raw stdout/stderr from test run")

class FileMigrationReport(BaseModel):
    filepath: str
    status: str
    changes: List[str] = Field(default_factory=list)
    intent_summary: str = ""
    test_pass_rate_before: float = 0.0
    test_pass_rate_after: float = 0.0
    semantic_diff_score: Optional[float] = None
    retries_needed: int = 0

class MigrationReport(BaseModel):
    total_files: int = 0
    migrated_files: int = 0
    needs_review_files: int = 0
    test_pass_rate_before: float = 0.0
    test_pass_rate_after: float = 0.0
    file_reports: List[FileMigrationReport] = Field(default_factory=list)
    estimated_review_time_mins: int = 0
