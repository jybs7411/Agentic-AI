"""The tool registry: every action the agent can take is a Python function marked with @tool.

How it works:
- The function's docstring tells the AI what the tool does and what each argument means.
- The type hints (str, int, bool, list[str]) become the argument types the AI must use.
- `risk` decides whether you must approve the action first:
    risk=None               -> safe, runs automatically
    risk="reason"           -> always asks you first, showing the reason
    risk=function(args)     -> decides per call; returns a reason to ask, or None if safe
"""

import inspect
import re
import typing
from dataclasses import dataclass, field
from typing import Callable, Optional, Union

RiskRule = Union[None, str, Callable[[dict], Optional[str]]]

_JSON_TYPES = {str: "string", int: "integer", float: "number", bool: "boolean", dict: "object"}


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
        return self.risk(self.coerce(args))

    def schema(self) -> dict:
        """The tool described in the OpenAI 'function calling' format."""
        hints = typing.get_type_hints(self.func)
        properties, required = {}, []
        for name, param in inspect.signature(self.func).parameters.items():
            prop = _json_schema(hints.get(name, str))
            if name in self.arg_docs:
                prop["description"] = self.arg_docs[name]
            if param.default is inspect.Parameter.empty:
                required.append(name)
            properties[name] = prop
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {"type": "object", "properties": properties, "required": required},
            },
        }

    def coerce(self, args: dict) -> dict:
        """Keep only known arguments and fix common type slips (e.g. "30" for 30), which small
        local models make often."""
        hints = typing.get_type_hints(self.func)
        accepted = inspect.signature(self.func).parameters
        clean = {}
        for key, value in args.items():
            if key not in accepted:
                continue
            clean[key] = _coerce_value(value, hints.get(key))
        return clean

    def call(self, args: dict):
        return self.func(**self.coerce(args))


def _json_schema(annotation) -> dict:
    origin = typing.get_origin(annotation)
    if origin in (list, typing.List):
        (item,) = typing.get_args(annotation) or (str,)
        return {"type": "array", "items": _json_schema(item)}
    return {"type": _JSON_TYPES.get(annotation, "string")}


def _coerce_value(value, annotation):
    try:
        if annotation is bool and isinstance(value, str):
            return value.strip().lower() in ("true", "1", "yes", "y")
        if annotation is int and not isinstance(value, bool):
            return int(float(value))
        if annotation is float:
            return float(value)
        if annotation is str and not isinstance(value, str):
            return str(value)
        if typing.get_origin(annotation) is list and isinstance(value, str):
            return [value]
    except (TypeError, ValueError):
        pass
    return value


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
    description = " ".join(parts[0].split())
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
    from agent.tools import apps, files, memory_tools, screen, system  # noqa: F401

    return REGISTRY
