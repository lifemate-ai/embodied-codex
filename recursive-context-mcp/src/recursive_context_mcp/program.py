"""Optional restricted program execution for RLM-style context inspection."""

from __future__ import annotations

import ast
import contextlib
import io
from typing import Any

SAFE_BUILTINS = {
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "range": range,
    "repr": repr,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
}

BANNED_NAMES = {"__import__", "compile", "eval", "exec", "globals", "locals", "open", "vars"}
BANNED_NODES = (
    ast.Import,
    ast.ImportFrom,
    ast.Global,
    ast.Nonlocal,
    ast.ClassDef,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
)


def validate_program(code: str) -> None:
    tree = ast.parse(code, mode="exec")
    for node in ast.walk(tree):
        if isinstance(node, BANNED_NODES):
            raise ValueError(f"Unsupported program node: {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id in BANNED_NAMES:
            raise ValueError(f"Unsupported program name: {node.id}")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError("Dunder attribute access is not allowed")


def execute_program(code: str, context_api: Any) -> tuple[Any, str]:
    """Execute a small inspection program and return result plus stdout.

    This is not a security boundary. The MCP server keeps it disabled by default and only enables
    it when RECURSIVE_CONTEXT_ENABLE_PROGRAMS=true.
    """

    validate_program(code)
    stdout = io.StringIO()
    globals_dict = {"__builtins__": SAFE_BUILTINS, "ctx": context_api}
    locals_dict: dict[str, Any] = {}
    with contextlib.redirect_stdout(stdout):
        exec(compile(code, "<recursive-context-program>", "exec"), globals_dict, locals_dict)
    return locals_dict.get("result"), stdout.getvalue()
