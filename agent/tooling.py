"""The tool registry: every action the agent can take is a Python function marked with @tool.

How it works:
- The function's docstring tells Gemini what the tool does and what each argument means.
- `risk` decides whether you must approve the action first:
    risk=None               -> safe, runs automatically
    risk="reason"           -> always asks you first, showing the reason
    risk=function(args)     -> decides per call; returns a reason to ask, or None if safe
"""

import inspect
import re
from dataclasses import dataclass, field
from typing import Callable, Optional, Union

from google.genai import types

RiskRule = Union[None, str, Callable[[dict], Optional[str]]]


@dataclass
class Tool:
    name: str
    func: Callable
    description: str
    arg_docs: dict = field(default_factory=dict)
    risk: RiskRule = None

    def risk_reason(self, args: dict) -> Optional[str]:
        """Return why this call needs your approval, or None if it is safe."""
        if self.risk is None:
            return None
        if isinstance(self.risk, str):
            return self.risk
        return self.risk(args)

    def declaration(self) -> types.FunctionDeclaration:
        decl = types.FunctionDeclaration.from_callable_with_api_option(
            callable=self.func, api_option="GEMINI_API"
        )
        decl.description = self.description
        if decl.parameters and decl.parameters.properties:
            for arg_name, schema in decl.parameters.properties.items():
                if arg_name in self.arg_docs:
                    schema.description = self.arg_docs[arg_name]
        return decl

    def call(self, args: dict):
        # Ignore arguments the model invented that the function doesn't accept.
        accepted = inspect.signature(self.func).parameters
        clean = {k: v for k, v in args.items() if k in accepted}
        return self.func(**clean)


REGISTRY: dict = {}


def tool(risk: RiskRule = None):
    """Decorator that registers a function as a tool the agent can use."""

    def register(func: Callable) -> Callable:
        description, arg_docs = _parse_docstring(func.__doc__ or "")
        REGISTRY[func.__name__] = Tool(
            name=func.__name__, func=func, description=description, arg_docs=arg_docs, risk=risk
        )
        return func

    return register


def _parse_docstring(doc: str):
    """Split a Google-style docstring into (description, {arg: description})."""
    doc = inspect.cleandoc(doc)
    parts = re.split(r"^Args:\s*$", doc, maxsplit=1, flags=re.MULTILINE)
    description = parts[0].strip()
    arg_docs = {}
    if len(parts) == 2:
        current = None
        for line in parts[1].splitlines():
            match = re.match(r"^\s{2,}(\w+):\s*(.*)$", line)
            if match:
                current = match.group(1)
                arg_docs[current] = match.group(2).strip()
            elif current and line.strip():
                arg_docs[current] += " " + line.strip()
    return description, arg_docs


def load_all_tools() -> dict:
    """Import every tool module so their @tool functions get registered."""
    from agent.tools import apps, files, memory_tools, system  # noqa: F401

    return REGISTRY
