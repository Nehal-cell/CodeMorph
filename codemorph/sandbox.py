import os
import logging
import subprocess
import xml.etree.ElementTree as ET
from typing import Optional
from codemorph.models import TestResult, TestFailure

logger = logging.getLogger(__name__)

class SandboxManager:
    def __init__(self, workspace_dir: str):
        self.workspace_dir = os.path.abspath(workspace_dir)

    def run_tests(self, use_docker: bool = True) -> TestResult:
        """Executes the test suite in the workspace using Docker or local subprocess fallback."""
        report_path = os.path.join(self.workspace_dir, ".codemorph_report.xml")
        
        # Clean up existing report
        if os.path.exists(report_path):
            try:
                os.remove(report_path)
            except Exception as e:
                logger.warning(f"Could not remove old test report: {e}")

        raw_output = ""
        success = False

        if use_docker:
            try:
                success, raw_output = self._run_in_docker(report_path)
            except Exception as e:
                logger.warning(f"Docker execution failed: {e}. Falling back to local execution.")
                success, raw_output = self._run_locally(report_path)
        else:
            success, raw_output = self._run_locally(report_path)

        # Parse test results from XML
        return self._parse_report(report_path, raw_output)

    def _run_in_docker(self, report_path: str) -> tuple[bool, str]:
        """Runs pytest inside a Docker container."""
        import docker
        
        client = docker.from_env()
        # Ensure report.xml filename is relative inside /workspace
        report_rel = os.path.relpath(report_path, self.workspace_dir)
        
        # Run pytest inside docker container mapping workspace
        container = client.containers.run(
            image="python:3.11-slim",
            command=f"pip install pytest -q && pytest --junitxml={report_rel} .",
            volumes={self.workspace_dir: {"bind": "/workspace", "mode": "rw"}},
            working_dir="/workspace",
            stdout=True,
            stderr=True,
            detach=True
        )
        
        result = container.wait()
        logs = container.logs().decode("utf-8", errors="replace")
        container.remove()
        
        exit_code = result.get("StatusCode", 1)
        return exit_code == 0, logs

    def _run_locally(self, report_path: str) -> tuple[bool, str]:
        """Runs pytest locally via subprocess."""
        report_rel = os.path.relpath(report_path, self.workspace_dir)
        
        # Check if pytest is available in current environment
        cmd = ["pytest", f"--junitxml={report_rel}", "."]
        try:
            res = subprocess.run(
                cmd,
                cwd=self.workspace_dir,
                capture_output=True,
                text=True,
                timeout=60
            )
            return res.returncode == 0, res.stdout + "\n" + res.stderr
        except subprocess.TimeoutExpired as e:
            logger.error("Test execution timed out locally.")
            return False, "Timeout expired during test run."
        except FileNotFoundError:
            logger.error("pytest command not found locally. Please install pytest.")
            return False, "pytest not found on host path."

    def _parse_report(self, report_path: str, raw_output: str) -> TestResult:
        """Parses the generated JUnit XML report into a TestResult object."""
        if not os.path.exists(report_path):
            return TestResult(
                passed=False,
                output=raw_output,
                failures=[TestFailure(test_name="System Error", message="JUnit XML report was not generated.")]
            )

        try:
            tree = ET.parse(report_path)
            root = tree.getroot()

            if root.tag == "testsuites":
                total = sum(int(ts.attrib.get("tests", 0)) for ts in root.findall("testsuite"))
                failures_count = sum(int(ts.attrib.get("failures", 0)) for ts in root.findall("testsuite"))
                errors_count = sum(int(ts.attrib.get("errors", 0)) for ts in root.findall("testsuite"))
                skipped = sum(int(ts.attrib.get("skipped", 0)) for ts in root.findall("testsuite"))
            else:
                total = int(root.attrib.get("tests", 0))
                failures_count = int(root.attrib.get("failures", 0))
                errors_count = int(root.attrib.get("errors", 0))
                skipped = int(root.attrib.get("skipped", 0))

            failed_list = []
            for tc in root.findall(".//testcase"):
                failure = tc.find("failure")
                error = tc.find("error")
                issue = failure if failure is not None else error
                
                if issue is not None:
                    classname = tc.attrib.get("classname", "")
                    name = tc.attrib.get("name", "")
                    test_name = f"{classname}.{name}" if classname else name
                    msg = issue.attrib.get("message", "No message provided")
                    traceback = issue.text
                    
                    failed_list.append(
                        TestFailure(
                            test_name=test_name,
                            message=msg,
                            traceback=traceback
                        )
                    )

            passed_count = total - failures_count - errors_count - skipped
            passed = (failures_count == 0 and errors_count == 0 and total > 0)

            return TestResult(
                passed=passed,
                total=total,
                passed_count=passed_count,
                failed_count=failures_count + errors_count,
                failures=failed_list,
                output=raw_output
            )

        except Exception as e:
            logger.error(f"Failed to parse JUnit XML report: {e}")
            return TestResult(
                passed=False,
                output=raw_output,
                failures=[TestFailure(test_name="XML Parse Error", message=f"Failed to parse test XML: {e}")]
            )
        finally:
            # Clean up the XML report after parsing
            try:
                if os.path.exists(report_path):
                    os.remove(report_path)
            except Exception:
                pass
