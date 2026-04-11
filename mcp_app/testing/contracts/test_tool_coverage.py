"""Tool coverage audit — every SDK method called by a tool must have tests."""

from pathlib import Path

from mcp_app.testing.audit import audit_tool_coverage


def test_every_tool_has_sdk_test_coverage(app):
    """For each tool, every SDK method it calls must appear in SDK tests."""
    sdk_tests_path = None

    if hasattr(app, 'sdk_package') and app.sdk_package is not None:
        pkg_dir = Path(app.sdk_package.__file__).parent
        # Look for tests/unit/sdk/ relative to the repo root
        repo_root = pkg_dir
        while repo_root.parent != repo_root:
            candidate = repo_root / "tests" / "unit" / "sdk"
            if candidate.exists():
                sdk_tests_path = candidate
                break
            repo_root = repo_root.parent

    if sdk_tests_path is None or not sdk_tests_path.exists():
        import pytest
        pytest.skip("SDK tests path not found — cannot audit coverage")

    missing = audit_tool_coverage(app.tools_module, sdk_tests_path)
    assert not missing, (
        f"Tools with SDK methods lacking test coverage:\n"
        + "\n".join(f"  {tool}: {methods}" for tool, methods in missing.items())
        + "\n\nAdd unit tests in tests/unit/sdk/ that reference the named SDK methods."
    )
