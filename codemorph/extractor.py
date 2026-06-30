import os
import json
import logging
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from codemorph.models import IntentNode, IntentGraph
from codemorph.parser import CodeParser

logger = logging.getLogger(__name__)

class LLMClient:
    """Wrapper to interact with Anthropic, Gemini, or OpenAI based on available keys."""
    def __init__(self, provider: Optional[str] = None):
        self.provider = provider or os.environ.get("CODEMORPH_PROVIDER")
        self.client = None
        self.model = ""

        # Auto-detect provider if not specified
        if not self.provider:
            if os.environ.get("ANTHROPIC_API_KEY"):
                self.provider = "anthropic"
            elif os.environ.get("GEMINI_API_KEY"):
                self.provider = "gemini"
            elif os.environ.get("OPENAI_API_KEY"):
                self.provider = "openai"
            else:
                self.provider = "mock"
                logger.warning("No LLM API keys found (ANTHROPIC_API_KEY, GEMINI_API_KEY, or OPENAI_API_KEY). Running in Mock/Dry-Run mode.")

        # Initialize appropriate client
        if self.provider == "anthropic":
            import anthropic
            self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
            self.model = os.environ.get("CODEMORPH_MODEL", "claude-3-5-sonnet-20241022")
        elif self.provider == "gemini":
            from google import genai
            self.client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
            self.model = os.environ.get("CODEMORPH_MODEL", "gemini-2.5-flash")
        elif self.provider == "openai":
            import openai
            self.client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
            self.model = os.environ.get("CODEMORPH_MODEL", "gpt-4o-mini")
        else:
            self.provider = "mock"
            logger.info("Using mock LLM client.")

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Call the selected LLM provider and return response text."""
        if self.provider == "mock":
            # Return dummy JSON matching intent extractor requirements
            return json.dumps({
                "role": "business_logic",
                "intent": "Mock extracted intent description for testing and local dry-runs."
            })

        try:
            if self.provider == "anthropic":
                messages = [{"role": "user", "content": prompt}]
                kwargs = {
                    "model": self.model,
                    "max_tokens": 2048,
                    "messages": messages
                }
                if system_prompt:
                    kwargs["system"] = system_prompt
                response = self.client.messages.create(**kwargs)
                return response.content[0].text

            elif self.provider == "gemini":
                # For google-genai client
                contents = prompt
                config = {}
                if system_prompt:
                    from google.genai import types
                    config = types.GenerateContentConfig(system_instruction=system_prompt)
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=config
                )
                return response.text

            elif self.provider == "openai":
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})
                
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=2048
                )
                return response.choices[0].message.content or ""

        except Exception as e:
            logger.error(f"LLM API Call failed ({self.provider}): {e}")
            raise e

        return ""


class IntentExtractor:
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()
        self.parser = CodeParser()

    def extract_intent(self, node: IntentNode) -> Tuple[str, str]:
        """Call LLM to extract semantic role and intent for an IntentNode."""
        system_prompt = "You are an expert Python software architect analyzing code components to extract intent."
        prompt = f"""Analyze this Python code component and return a JSON object with the semantic role and intent.

Component Metadata:
- Filepath: {node.filepath}
- Name: {node.name}
- Type: {node.type}
- Docstring: {node.docstring or 'None'}

Code:
```python
{node.code}
```

Format your output as a JSON object:
{{
  "role": "<role_type>",
  "intent": "<detailed_explanation_of_intent>"
}}

Supported roles: 'request_handler', 'data_validator', 'database_model', 'business_logic', 'configuration', 'task_definition', 'test_case', 'utility', 'other'.

Provide ONLY the raw JSON object, without markdown blocks or additional conversational text.
"""
        try:
            response_text = self.llm.generate(prompt, system_prompt=system_prompt)
            # Strip markdown formatting if any
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            data = json.loads(response_text)
            return data.get("role", "other"), data.get("intent", "No intent description provided.")
        except Exception as e:
            logger.error(f"Failed to parse LLM intent for {node.name}: {e}")
            return "other", "Error extracting intent via LLM."

    def build_intent_graph(self, directory: str, max_workers: int = 4) -> IntentGraph:
        """Scan directory for python files, parse them, extract intent, and return IntentGraph."""
        # Find all python files
        py_files = []
        for root, _, files in os.walk(directory):
            # Skip virtual environments and hidden dirs
            if any(part in root.split(os.sep) for part in (".venv", "venv", ".git", "__pycache__")):
                continue
            for f in files:
                if f.endswith(".py"):
                    py_files.append(os.path.join(root, f))

        all_nodes: Dict[str, IntentNode] = {}
        
        # 1. Parse all files to extract raw nodes
        for filepath in py_files:
            nodes = self.parser.parse_file(filepath)
            for node in nodes:
                # Key: filepath::name
                key = f"{filepath}::{node.name}"
                all_nodes[key] = node

        # 2. Enrich nodes with LLM intent concurrently
        nodes_list = list(all_nodes.values())
        if nodes_list:
            logger.info(f"Extracting intent for {len(nodes_list)} nodes using LLM provider: {self.llm.provider}")
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_node = {executor.submit(self.extract_intent, node): node for node in nodes_list}
                for future in as_completed(future_to_node):
                    node = future_to_node[future]
                    try:
                        role, intent = future.result()
                        node.role = role
                        node.intent = intent
                    except Exception as exc:
                        logger.error(f"Node {node.name} generated an exception: {exc}")
                        node.role = "other"
                        node.intent = "Exception encountered during extraction."

        # 3. Build dependency graph
        # Map node name to their unique keys in all_nodes
        name_to_key = {}
        for key, node in all_nodes.items():
            name_to_key[node.name] = key
            # Also register name variations (e.g. function inside class)
            if "." in node.name:
                name_to_key[node.name.split(".")[-1]] = key

        dependencies: Dict[str, List[str]] = {}
        for key, node in all_nodes.items():
            dep_keys = []
            for dep in node.dependencies:
                if dep in name_to_key:
                    dep_keys.append(name_to_key[dep])
            dependencies[key] = list(set(dep_keys))

        return IntentGraph(nodes=all_nodes, dependencies=dependencies)
