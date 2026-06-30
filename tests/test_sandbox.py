import os
import unittest
import tempfile
from codemorph.sandbox import SandboxManager

class TestSandboxManager(unittest.TestCase):
    def setUp(self):
        self.sandbox = SandboxManager(".")

    def test_parse_junit_xml_failures(self):
        xml_content = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" errors="0" failures="1" skipped="0" tests="2" time="0.089">
    <testcase classname="tests.test_app" name="test_add" time="0.002" />
    <testcase classname="tests.test_app" name="test_sub" time="0.005">
      <failure message="AssertionError: assert 1 == 2">
        traceback info here...
      </failure>
    </testcase>
  </testsuite>
</testsuites>
"""
        with tempfile.NamedTemporaryFile(suffix=".xml", mode="w", delete=False) as f:
            f.write(xml_content)
            temp_path = f.name

        try:
            result = self.sandbox._parse_report(temp_path, "raw console log output")
            
            self.assertFalse(result.passed)
            self.assertEqual(result.total, 2)
            self.assertEqual(result.passed_count, 1)
            self.assertEqual(result.failed_count, 1)
            self.assertEqual(len(result.failures), 1)
            
            failure = result.failures[0]
            self.assertEqual(failure.test_name, "tests.test_app.test_sub")
            self.assertEqual(failure.message, "AssertionError: assert 1 == 2")
            self.assertIn("traceback info", failure.traceback)
            
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

if __name__ == "__main__":
    unittest.main()
