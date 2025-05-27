"""Fixtures for tests."""

from collections.abc import Callable
from pathlib import Path

import pytest
from rich.console import Console

console = Console()


@pytest.fixture
def debug() -> Callable[[str | Path, str, bool, int], bool]:
    """Create a debug printing function for test development.

    Return a function that prints formatted debug output with clear visual separation and optional breakpoints. Useful for inspecting variables, file contents, or directory structures during test development.

    Returns:
        Callable[[str | Path, str, bool, int], bool]: Debug printing function with parameters:
            - value: Data to debug print (string or Path)
            - label: Optional header text
            - breakpoint: Whether to pause execution after printing
            - width: Maximum output width in characters
    """

    def _debug_inner(
        value: str | Path,
        label: str = "",
        *,
        breakpoint: bool = False,
        width: int = 80,
    ) -> bool:
        """Print formatted debug information during test development.

        Format and display debug output with labeled headers and clear visual separation. Supports printing file contents, directory structures, and variable values with optional execution breakpoints.

        Args:
            value (str | Path): Value to debug print. For Path objects, prints directory tree
            label (str): Optional header text for context
            breakpoint (bool, optional): Pause execution after printing. Defaults to False
            width (int, optional): Maximum output width. Defaults to 80

        Returns:
            bool: True unless breakpoint is True, then raises pytest.fail()
        """
        console.rule(label or "")

        # If a directory is passed, print the contents
        if isinstance(value, Path) and value.is_dir():
            for p in value.rglob("*"):
                console.print(p, width=width)
        else:
            console.print(value, width=width)

        console.rule()

        if breakpoint:
            return pytest.fail("Breakpoint")

        return True

    return _debug_inner
