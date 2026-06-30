import unittest
from codemorph.models import IntentNode, IntentGraph
from codemorph.planner import MigrationPlanner

class TestMigrationPlanner(unittest.TestCase):
    def setUp(self):
        self.planner = MigrationPlanner()

    def test_topological_sort(self):
        # file_c has no deps
        # file_b depends on file_c
        # file_a depends on file_b
        nodes = {
            "a::func_a": IntentNode(
                name="func_a", type="function", filepath="file_a.py",
                code="def func_a(): pass", line_range=(1, 2), dependencies=["func_b"]
            ),
            "b::func_b": IntentNode(
                name="func_b", type="function", filepath="file_b.py",
                code="def func_b(): pass", line_range=(1, 2), dependencies=["func_c"]
            ),
            "c::func_c": IntentNode(
                name="func_c", type="function", filepath="file_c.py",
                code="def func_c(): pass", line_range=(1, 2), dependencies=[]
            )
        }
        dependencies = {
            "a::func_a": ["b::func_b"],
            "b::func_b": ["c::func_c"],
            "c::func_c": []
        }
        graph = IntentGraph(nodes=nodes, dependencies=dependencies)
        
        plan = self.planner.create_plan(graph)
        
        # Expected execution order: c -> b -> a
        file_order = [task.filepath for task in plan]
        self.assertEqual(file_order, ["file_c.py", "file_b.py", "file_a.py"])

    def test_cycle_handling(self):
        # a depends on b, b depends on a
        nodes = {
            "a::func_a": IntentNode(
                name="func_a", type="function", filepath="file_a.py",
                code="def func_a(): pass", line_range=(1, 2), dependencies=["func_b"]
            ),
            "b::func_b": IntentNode(
                name="func_b", type="function", filepath="file_b.py",
                code="def func_b(): pass", line_range=(1, 2), dependencies=["func_a"]
            )
        }
        dependencies = {
            "a::func_a": ["b::func_b"],
            "b::func_b": ["a::func_a"]
        }
        graph = IntentGraph(nodes=nodes, dependencies=dependencies)
        
        plan = self.planner.create_plan(graph)
        
        # Should complete without error and return both files
        file_order = [task.filepath for task in plan]
        self.assertEqual(len(file_order), 2)
        self.assertIn("file_a.py", file_order)
        self.assertIn("file_b.py", file_order)

if __name__ == "__main__":
    unittest.main()
