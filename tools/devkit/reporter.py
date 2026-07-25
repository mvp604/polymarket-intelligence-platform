"""Console reporting utilities."""

from __future__ import annotations


LINE_WIDTH = 64


def print_header(title: str) -> None:
    """Print a consistent command section header."""

    print()
    print("=" * LINE_WIDTH)
    print(title)
    print("=" * LINE_WIDTH)


def print_result(
    label: str,
    successful: bool,
) -> None:
    """Print a standardized success or failure result."""

    status = "PASSED" if successful else "FAILED"
    print(f"{label}: {status}")
