import os
import tempfile
import unittest
from codemorph.parser import CodeParser

class TestCodeParser(unittest.TestCase):
    def setUp(self):
        self.parser = CodeParser()

    def test_parse_simple_file(self):
        # Create a temporary python file
        code_content = """# Sample code
def add(a: int, b: int) -> int:
    \"\"\"Adds two numbers.\"\"\"
    return a + b

@some_decorator
class Calculator:
    \"\"\"A simple calculator class.\"\"\"
    def subtract(self, a, b):
        return a - b
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code_content)
            temp_path = f.name

        try:
            nodes = self.parser.parse_file(temp_path)
            
            # We expect: 1 function ('add'), 1 class ('Calculator'), 1 method ('Calculator.subtract')
            # Depending on parser type (ast/tree-sitter), they should be extracted.
            self.assertTrue(len(nodes) >= 2)
            
            node_names = [n.name for n in nodes]
            self.assertIn("add", node_names)
            self.assertIn("Calculator", node_names)
            
            # Check docstrings
            add_node = next(n for n in nodes if n.name == "add")
            self.assertEqual(add_node.docstring, "Adds two numbers.")
            self.assertEqual(add_node.type, "function")
            
            calc_node = next(n for n in nodes if n.name == "Calculator")
            self.assertEqual(calc_node.docstring, "A simple calculator class.")
            self.assertEqual(calc_node.type, "class")
            
        finally:
            os.remove(temp_path)

if __name__ == "__main__":
    unittest.main()
