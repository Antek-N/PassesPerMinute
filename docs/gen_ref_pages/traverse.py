import os
from collections.abc import Iterable
from pathlib import Path

from context import Context
from helpers import is_private


def _walk_dirs(package_dir: Path, include_private: bool) -> Iterable[tuple[Path, list[str]]]:
    """
    Walk the filesystem tree starting at package_dir and yield
    (relative_dir, subdirs) pairs.

    Rules:
      - Private subdirectories (names starting with "_") are removed in-place
        unless include_private=True.
      - Entire directories marked private are skipped completely.

    :param package_dir: Path to the root package (e.g., src/mypkg).
    :param include_private: Whether to include private directories.
    :return: Iterator of (relative_dir, subdirs).

    Example:
        "src/mypkg" > [(Path("mypkg"), ["subdir1", "subdir2"])]
    """
    source_dir = package_dir.parent

    # Walk filesystem tree starting at package_dir
    for current_dirpath, subdirs, _ in os.walk(package_dir):
        relative_dir = Path(current_dirpath).relative_to(source_dir)

        # Remove unnecessary catalogues (pycache, build, dist)
        subdirs[:] = [dirname for dirname in subdirs if dirname != "__pycache__" and dirname not in {"build", "dist"}]

        # Remove private subdirectories in-place if not including them
        if not include_private:
            subdirs[:] = [dirname for dirname in subdirs if not dirname.startswith("_")]

        # Skip the current directory if it's marked private
        if is_private(relative_dir):
            continue

        yield relative_dir, subdirs


def _parts_for(relative_dir: Path, package_name: str) -> list[str]:
    """
    Convert a relative path into parts; fallback to package_name for the root.

    :param relative_dir: Path relative to the source directory.
    :param package_name: Top-level package name.
    :return: List of path components.

    Examples:
        "mypkg/subdir" > ["mypkg", "subdir"]
        "." (root) > ["mypkg"]
    """
    return list(relative_dir.parts) or [package_name]


def _register_folder(ctx: Context, folder_parts: list[str]) -> tuple[str, ...]:
    """
    Ensure the given folder exists in Context and return it as a tuple key.

    :param ctx: Shared Context object.
    :param folder_parts: List of folder path components.
    :return: Tuple representation of the folder path.

    Example:
        ["mypkg", "subdir"] > ("mypkg", "subdir")
    """
    ctx.ensure_folder(folder_parts)
    return tuple(folder_parts)


def _register_children(ctx: Context, parent_parts: list[str], child_names: Iterable[str]) -> None:
    """
    Register each child subdirectory of a given parent folder in Context.

    :param ctx: Shared Context object.
    :param parent_parts: Parent folder path components.
    :param child_names: Iterable of subdirectory names.
    :return: None

    Example:
        ["mypkg"], ["a", "b"] > {("mypkg", "a"), ("mypkg", "b")}
    """
    parent_t = tuple(parent_parts)
    # Register each child subdirectory
    for dirname in sorted(child_names):
        child_parts = parent_parts + [dirname]
        ctx.ensure_folder(child_parts)
        ctx.children_directories[parent_t].add(tuple(child_parts))


def traverse_directories(
    package_dir: Path,
    package_name: str,
    include_private: bool,
    ctx: Context,
) -> None:
    """
    Walk through the package directory tree and populate the Context
    with discovered folders and their relationships.

    Rules:
      - Private directories (names starting with "_") are skipped unless
        include_private=True.
      - Each valid folder is registered in ctx.created_folders.
      - Parent > child directory relationships are stored in ctx.children_directories.

    :param package_dir: Path to the root package (e.g., src/mypkg).
    :param package_name: Top-level package name.
    :param include_private: Whether to include private directories.
    :param ctx: Shared Context object to update.
    :return: None

    Example:
        "src/mypkg" > {("mypkg",)}
    """
    for relative_dir, subdirs in _walk_dirs(package_dir, include_private=include_private):
        # Convert the path into parts; fallback to package_name for root
        folder_parts = _parts_for(relative_dir, package_name)
        _register_folder(ctx, folder_parts)

        # Register each child subdirectory
        _register_children(ctx, folder_parts, subdirs)
