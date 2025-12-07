from pathlib import Path

# Global configuration flags and constants
INCLUDE_PRIVATE = True  # Whether to include private packages (names starting with "_")
SOURCE_DIR = Path("src")  # Root source directory to search for packages

# Mapping from source subdirectories > human-readable section titles
SECTION_TITLE_MAP = {
    "services": "Services",
    "threads": "Threads",
    "ui": "UI",
    "utils": "Utils",
}

# Explicit ordering for sections when displaying documentation or indexes
SECTION_ORDER = {"Ui": 1, "Services": 2, "Threads": 3, "Utils": 4}

# File extensions that should be recognized as linkable images
LINKABLE_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".ico", ".gif"}


def _is_pkg_dir(path: Path) -> bool:
    """
    Check whether a given path points to a valid Python package directory.

    A valid package directory must:
      1. Be a directory.
      2. Contain an __init__.py file.

    :param path: Filesystem path to check.
    :return: True if the path is a Python package directory, False otherwise.
    """
    return path.is_dir() and (path / "__init__.py").exists()


def find_package_dir(include_private: bool = INCLUDE_PRIVATE) -> tuple[Path, str]:
    """
    Locate the first valid Python package directory under SOURCE_DIR.

    - Private packages (names starting with "_") can be excluded unless explicitly allowed.
    - If multiple candidates exist, the package with the lexicographically smallest name is chosen.

    :param include_private: Whether to allow private packages (default: global INCLUDE_PRIVATE).
    :return: Tuple (package_path, package_name).
    :raises SystemExit: If no valid package directory is found.
    """
    # Gather all package directories under SOURCE_DIR
    candidates = [
        package_path
        for package_path in SOURCE_DIR.iterdir()
        if _is_pkg_dir(package_path) and (include_private or not package_path.name.startswith("_"))
    ]

    # No valid package found > stop execution with an error message
    if not candidates:
        raise SystemExit("No package found in src/. Make sure you have something like " "src/yourpkg/__init__.py")

    # Pick the lexicographically smallest directory (deterministic choice)
    package_dir = min(candidates, key=lambda package_path: package_path.name)
    return package_dir, package_dir.name
