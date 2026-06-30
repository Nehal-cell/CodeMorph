import logging
from typing import List, Dict, Set
from codemorph.models import IntentGraph, MigrationTask

logger = logging.getLogger(__name__)

class MigrationPlanner:
    def __init__(self):
        pass

    def create_plan(self, intent_graph: IntentGraph) -> List[MigrationTask]:
        """Maps node-level dependencies to file-level dependencies and performs topological sort."""
        # 1. Map node keys to files and gather all unique files
        all_files: Set[str] = set()
        node_to_file: Dict[str, str] = {}
        
        for key, node in intent_graph.nodes.items():
            node_to_file[key] = node.filepath
            all_files.add(node.filepath)

        # 2. Build file-level adjacency list
        file_deps: Dict[str, Set[str]] = {f: set() for f in all_files}
        for node_key, dep_keys in intent_graph.dependencies.items():
            src_file = node_to_file.get(node_key)
            if not src_file:
                continue
            for dep_key in dep_keys:
                dst_file = node_to_file.get(dep_key)
                if dst_file and dst_file != src_file:
                    file_deps[src_file].add(dst_file)

        # 3. Topological Sort with Cycle Detection (DFS)
        visited: Set[str] = set()
        visiting: Set[str] = set()
        ordered_files: List[str] = []

        def dfs(file_path: str):
            if file_path in visiting:
                logger.warning(f"Circular dependency detected involving file: {file_path}")
                return
            if file_path in visited:
                return

            visiting.add(file_path)
            # Visit dependencies first
            for dep in file_deps.get(file_path, []):
                dfs(dep)
            
            visiting.remove(file_path)
            visited.add(file_path)
            ordered_files.append(file_path)

        for file_path in all_files:
            if file_path not in visited:
                dfs(file_path)

        # 4. Construct MigrationTask list
        plan: List[MigrationTask] = []
        for file_path in ordered_files:
            deps = list(file_deps.get(file_path, []))
            plan.append(
                MigrationTask(
                    id=file_path,
                    filepath=file_path,
                    dependencies=deps,
                    status="PENDING"
                )
            )

        return plan
