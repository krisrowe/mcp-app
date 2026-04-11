"""Tool coverage audit — AST-based detection of untested SDK methods.

Walks each tool function's AST to find sdk.<method>() calls, then
checks that each method name appears in the SDK test directory.
"""

import ast
import inspect
from pathlib import Path
from types import ModuleType


def public_tools(tools_module: ModuleType) -> list:
    """Find all public async functions in a tools module."""
    return [
        obj for name, obj in inspect.getmembers(tools_module, inspect.isfunction)
        if inspect.iscoroutinefunction(obj) and not name.startswith("_")
    ]


def sdk_methods_called_by_tool(tool_func) -> set[str]:
    """Walk a tool function's AST and find sdk.<method>(...) calls."""
    src = inspect.getsource(tool_func)
    tree = ast.parse(src.lstrip())
    methods = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "sdk"):
            methods.add(node.func.attr)
    return methods


def audit_tool_coverage(tools_module: ModuleType, sdk_tests_path: Path) -> dict[str, list[str]]:
    """Check that every SDK method called by a tool has test coverage.

    Returns a dict of {tool_name: [untested_sdk_methods]}. Empty dict
    means full coverage.

    Args:
        tools_module: The app's tools module.
        sdk_tests_path: Path to the SDK test directory (e.g., tests/unit/sdk/).
    """
    if not sdk_tests_path.exists():
        return {"_error": [f"SDK tests path does not exist: {sdk_tests_path}"]}

    all_test_src = "\n".join(
        p.read_text() for p in sdk_tests_path.rglob("test_*.py")
    )

    missing = {}
    for tool in public_tools(tools_module):
        methods = sdk_methods_called_by_tool(tool)
        untested = [m for m in methods if m not in all_test_src]
        if untested:
            missing[tool.__name__] = untested

    return missing
