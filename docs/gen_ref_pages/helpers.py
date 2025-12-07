from collections.abc import Iterable
from pathlib import Path

from config import INCLUDE_PRIVATE, SECTION_ORDER, SECTION_TITLE_MAP


def is_private(path: Path) -> bool:
    """
    Determine whether a given path should be considered private.

    Rules:
      - If INCLUDE_PRIVATE is True > nothing is private.
      - Otherwise, any path component starting with "_" marks it as private.

    :param path: Filesystem path.
    :return: True if the path is private, False otherwise.
    """
    return False if INCLUDE_PRIVATE else any(package_path.startswith("_") for package_path in path.parts)


def prettify(label: str) -> str:
    """
    Convert an identifier string into a user-friendly label.

    - Underscores are replaced with spaces.
    - Each word is capitalized.

    Example:
      "my_module" > "My Module"

    :param label: Original string.
    :return: Prettified version.
    """
    return label.replace("_", " ").title()


def display_parts_for(parts: list[str]) -> list[str]:
    """
    Build display-friendly parts for navigation from raw path parts.

    - Second element may be replaced by a mapped section title (SECTION_TITLE_MAP).
    - Remaining elements are prettified.

    Example:
      ["mypkg", "ui", "main_window"]
      > ["mypkg", "UI", "Main Window"]

    :param parts: Raw path components.
    :return: List of human-readable display parts.
    """
    display = list(parts)

    # Replace known section keys (e.g., "ui" > "UI")
    if len(display) >= 2 and display[1] in SECTION_TITLE_MAP:
        display[1] = SECTION_TITLE_MAP[display[1]]

    # Prettify remaining elements
    for i in range(1, len(display)):
        display[i] = prettify(display[i])

    return display


def sort_key_for(display_parts: Iterable[str]) -> tuple:
    """
    Build a sort key for consistent ordering of navigation items.

    Criteria:
      1. Section order (from SECTION_ORDER, default 999).
      2. Path length (shorter first).
      3. Alphabetical (case-insensitive).

    :param display_parts: Human-readable path parts.
    :return: Tuple usable as the sort key.
    """
    path_parts = list(display_parts)
    section = path_parts[1] if len(path_parts) >= 2 else ""

    return (
        SECTION_ORDER.get(section, 999),
        len(path_parts),
        tuple(part.lower() for part in path_parts),
    )
