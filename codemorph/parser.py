import os
import ast
import logging
from typing import List, Dict, Tuple, Optional, Set
from codemorph.models import IntentNode

logger = logging.getLogger(__name__)

# Try importing tree-sitter
HAS_TREE_SITTER = False
try:
    from tree_sitter import Language, Parser
    import tree_sitter_python as tspython
    HAS_TREE_SITTER = True
except ImportError:
    logger.warning("tree-sitter or tree-sitter-python not installed. Falling back to native AST parser.")

class ASTParserFallback(ast.NodeVisitor):
    """Fallback AST parser using standard library ast module."""
    def __init__(self, filepath: str, content: str):
        self.filepath = filepath
        self.content = content
        self.lines = content.splitlines()
        self.nodes: List[IntentNode] = []
        self.current_class: Optional[str] = None

    def _get_source(self, start_line: int, end_line: int) -> str:
        # ast is 1-indexed for line numbers
        return "\n".join(self.lines[start_line - 1 : end_line])

    def visit_ClassDef(self, node: ast.ClassDef):
        # Determine actual start line including decorators
        start_line = node.lineno
        if node.decorator_list:
            start_line = min(d.lineno for d in node.decorator_list)
        
        end_line = getattr(node, "end_lineno", node.lineno)
        code = self._get_source(start_line, end_line)
        docstring = ast.get_docstring(node)

        # Extract internal method names as dependencies / class structure
        methods = []
        for body_node in node.body:
            if isinstance(body_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(body_node.name)

        intent_node = IntentNode(
            name=node.name,
            type="class",
            docstring=docstring,
            code=code,
            dependencies=methods,
            filepath=self.filepath,
            line_range=(start_line, end_line)
        )
        self.nodes.append(intent_node)
        
        # Parse functions inside the class
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._process_func(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._process_func(node)

    def _process_func(self, node: ast.AST):
        start_line = node.lineno
        if node.decorator_list:
            start_line = min(d.lineno for d in node.decorator_list)
            
        end_line = getattr(node, "end_lineno", node.lineno)
        code = self._get_source(start_line, end_line)
        docstring = ast.get_docstring(node)

        # Find external dependency calls
        calls = []
        for subnode in ast.walk(node):
            if isinstance(subnode, ast.Call):
                if isinstance(subnode.func, ast.Name):
                    calls.append(subnode.func.id)
                elif isinstance(subnode.func, ast.Attribute):
                    calls.append(subnode.func.attr)

        name = f"{self.current_class}.{node.name}" if self.current_class else node.name
        intent_node = IntentNode(
            name=name,
            type="function",
            docstring=docstring,
            code=code,
            dependencies=list(set(calls)),
            filepath=self.filepath,
            line_range=(start_line, end_line)
        )
        self.nodes.append(intent_node)


class CodeParser:
    def __init__(self):
        self.parser = None
        if HAS_TREE_SITTER:
            try:
                # Initialize tree-sitter
                py_language = Language(tspython.language())
                self.parser = Parser()
                # Support newer tree-sitter API
                if hasattr(self.parser, "language"):
                    self.parser.language = py_language
                else:
                    self.parser.set_language(py_language)
            except Exception as e:
                logger.error(f"Failed to initialize tree-sitter parser: {e}. Falling back to standard AST.")
                self.parser = None

    def parse_file(self, filepath: str) -> List[IntentNode]:
        """Parses a Python file and extracts top-level functions, classes, and method definitions."""
        if not os.path.exists(filepath):
            logger.error(f"File not found: {filepath}")
            return []

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        if self.parser is None:
            return self._parse_with_ast_fallback(filepath, content)
        
        try:
            return self._parse_with_tree_sitter(filepath, content)
        except Exception as e:
            logger.error(f"Tree-sitter parse failed for {filepath}: {e}. Retrying with AST fallback.")
            return self._parse_with_ast_fallback(filepath, content)

    def _parse_with_ast_fallback(self, filepath: str, content: str) -> List[IntentNode]:
        try:
            tree = ast.parse(content)
            visitor = ASTParserFallback(filepath, content)
            visitor.visit(tree)
            return visitor.nodes
        except Exception as e:
            logger.error(f"AST parsing failed for {filepath}: {e}")
            return []

    def _parse_with_tree_sitter(self, filepath: str, content: str) -> List[IntentNode]:
        bytes_content = content.encode("utf-8")
        tree = self.parser.parse(bytes_content)
        
        nodes: List[IntentNode] = []
        root_node = tree.root_node
        
        def traverse(node, current_class: Optional[str] = None):
            if node.type == "decorated_definition":
                def_node = None
                for child in node.children:
                    if child.type in ("function_definition", "class_definition"):
                        def_node = child
                        break
                if def_node:
                    _process_def(node, def_node, current_class)
                return

            if node.type in ("function_definition", "class_definition"):
                _process_def(node, node, current_class)
                return

            for child in node.children:
                traverse(child, current_class)

        def _process_def(outer_node, def_node, current_class):
            if def_node.type == "class_definition":
                name_node = def_node.child_by_field_name("name")
                name = name_node.text.decode("utf-8") if name_node else "UnknownClass"
                start_line = outer_node.start_point[0] + 1
                end_line = outer_node.end_point[0] + 1
                code = bytes_content[outer_node.start_byte:outer_node.end_byte].decode("utf-8")
                docstring = self._extract_ts_docstring(def_node, bytes_content)
                
                methods = []
                body_node = def_node.child_by_field_name("body")
                if body_node:
                    for child in body_node.children:
                        child_target = child
                        if child.type == "decorated_definition":
                            for subchild in child.children:
                                if subchild.type == "function_definition":
                                    child_target = subchild
                        if child_target.type == "function_definition":
                            fname_node = child_target.child_by_field_name("name")
                            if fname_node:
                                methods.append(fname_node.text.decode("utf-8"))

                class_node = IntentNode(
                    name=name,
                    type="class",
                    docstring=docstring,
                    code=code,
                    dependencies=methods,
                    filepath=filepath,
                    line_range=(start_line, end_line)
                )
                nodes.append(class_node)
                
                if body_node:
                    for child in body_node.children:
                        traverse(child, current_class=name)

            elif def_node.type == "function_definition":
                name_node = def_node.child_by_field_name("name")
                name = name_node.text.decode("utf-8") if name_node else "UnknownFunc"
                if current_class:
                    name = f"{current_class}.{name}"
                
                start_line = outer_node.start_point[0] + 1
                end_line = outer_node.end_point[0] + 1
                code = bytes_content[outer_node.start_byte:outer_node.end_byte].decode("utf-8")
                docstring = self._extract_ts_docstring(def_node, bytes_content)
                
                calls = []
                self._find_calls(def_node, bytes_content, calls)
                
                func_node = IntentNode(
                    name=name,
                    type="function",
                    docstring=docstring,
                    code=code,
                    dependencies=list(set(calls)),
                    filepath=filepath,
                    line_range=(start_line, end_line)
                )
                nodes.append(func_node)

        traverse(root_node)
        return nodes

    def _extract_ts_docstring(self, node, bytes_content) -> Optional[str]:
        """Helper to extract docstring from a tree-sitter function or class node."""
        body = node.child_by_field_name("body")
        if not body or len(body.children) == 0:
            return None
        
        # Check first child of the body block
        first_child = body.children[0]
        # In tree-sitter, docstrings can be an expression_statement containing a string
        if first_child.type == "expression_statement":
            expr = first_child.children[0]
            if expr.type == "string":
                # Strip quotes
                text = expr.text.decode("utf-8")
                if text.startswith(('"""', "'''")):
                    return text[3:-3].strip()
                elif text.startswith(('"', "'")):
                    return text[1:-1].strip()
        return None

    def _find_calls(self, node, bytes_content, calls: List[str]):
        """Helper to find call expressions recursively in tree-sitter AST."""
        if node.type == "call":
            function_node = node.child_by_field_name("function")
            if function_node:
                if function_node.type == "identifier":
                    calls.append(function_node.text.decode("utf-8"))
                elif function_node.type == "attribute":
                    attribute_node = function_node.child_by_field_name("attribute")
                    if attribute_node:
                        calls.append(attribute_node.text.decode("utf-8"))
        
        for child in node.children:
            self._find_calls(child, bytes_content, calls)
