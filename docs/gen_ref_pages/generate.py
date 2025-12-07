import ast
from pathlib import Path
from typing import TextIO

import mkdocs_gen_files
from config import INCLUDE_PRIVATE, LINKABLE_IMAGE_EXTENSIONS, SOURCE_DIR
from context import Context
from helpers import display_parts_for, is_private, sort_key_for


def _defined_public_members(source_file: Path, include_private: bool) -> list[str]:
    try:
        tree = ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file))
    except SyntaxError:
        return []
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            if include_private or not node.name.startswith("_"):
                names.append(node.name)
    return names


def _iter_public_python_files(package_dir: Path) -> list[Path]:
    """
    Recursively collect all public Python files within a package directory.

    - Excludes __init__.py files.
    - Excludes private files (names starting with "_").

    :param package_dir: Base package directory.
    :return: Sorted list of Python file paths.
    """
    files: list[Path] = []
    for python_file in package_dir.rglob("*.py"):
        if python_file.name == "__init__.py":
            continue
        if is_private(python_file):
            continue
        files.append(python_file)
    return sorted(files)


def _parts_from_source(python_file: Path) -> tuple[str, ...]:
    """
    Convert a Python file path under SOURCE_DIR into module parts.

    Example:
      src/pkg/module.py > ("pkg", "module")

    :param python_file: Path to a Python file under SOURCE_DIR.
    :return: Tuple of path components without an extension.
    """
    return tuple(python_file.relative_to(SOURCE_DIR).with_suffix("").parts)


def _write_backlink_if_needed(fh: TextIO, parts: list[str]) -> None:
    """
    Write a backlink to the parent index if the page is not top-level.

    :param fh: File handle to write to.
    :param parts: Current parts representing this page.
    :return: None
    """
    if len(parts) > 1:
        parent_label = display_parts_for(parts[:-1])[-1]
        fh.write(f"[⬅ Back to {parent_label}](../index.md)\n\n")


def _record_page(ctx: Context, display_parts: list[str], doc_path: Path, is_directory: bool) -> None:
    """
    Add a record of a generated page to the context.

    :param ctx: Shared Context object.
    :param display_parts: Human-readable parts for display.
    :param doc_path: Path to the generated documentation file.
    :param is_directory: Whether the record refers to a directory index.
    :return: None
    """
    display_tuple = tuple(display_parts)
    doc_rel_path = doc_path.relative_to("reference").as_posix()
    ctx.records.append((sort_key_for(display_parts), display_tuple, doc_rel_path, is_directory))


def _display_sort_key(parts_like: tuple[str, ...]) -> tuple:
    """
    Compute a sort key for display purposes.

    :param parts_like: Tuple of path parts.
    :return: Sort key tuple.
    """
    return sort_key_for(display_parts_for(list(parts_like)))


def _write_module_page(doc_path: Path, module_path: str, parent_parts: tuple[str, ...], source_file: Path) -> None:
    """
    Generate a documentation page for a single module.

    :param doc_path: Target documentation path (index.md).
    :param module_path: Dotted module path (e.g., "pkg.module").
    :param parent_parts: Path parts for the parent package.
    :param source_file: Path to the source Python file.
    :return: None
    """
    mkdocs_gen_files.set_edit_path(doc_path, source_file)

    members = _defined_public_members(source_file, INCLUDE_PRIVATE)

    with mkdocs_gen_files.open(doc_path, "w") as fh:
        if parent_parts:
            _write_backlink_if_needed(fh, list(parent_parts) + ["_placeholder_"])
        fh.write(f"::: {module_path}\n")
        if members:
            fh.write("    options:\n")
            fh.write("      members:\n")
            for name in members:
                fh.write(f"      - {name}\n")


def _collect_static_files(source_folder_fs: Path) -> list[Path]:
    """
    Collect non-Python static files in a source folder.

    - Skips private files (names starting with "_").
    - Includes only non-.py files.

    :param source_folder_fs: Filesystem path to the source folder.
    :return: List of static file paths.
    """
    static_files: list[Path] = []
    if source_folder_fs.exists():
        for source_file in sorted(source_folder_fs.iterdir()):
            if source_file.name.startswith("_"):
                continue
            if source_file.is_file() and source_file.suffix != ".py":
                static_files.append(source_file)
    return static_files


def _emit_static_files_list(
    parts: list[str],
    static_files: list[Path],
    file_handle: TextIO,
) -> None:
    """
    Emit a section listing static files for a given folder.

    - Copies static files into `reference/.../_files/`.
    - Links images if the extension is in LINKABLE_IMAGE_EXTENSIONS.

    :param parts: Path parts of the folder.
    :param static_files: List of static file paths.
    :param file_handle: File handle to write documentation into.
    :return: None
    """
    if not static_files:
        return

    file_handle.write("## 🗃️ Static Files\n\n")

    for file_path in static_files:
        destination = Path("reference", *parts, "_files", file_path.name)

        # Copy file content into the documentation tree
        with mkdocs_gen_files.open(destination, "wb") as out_file:
            out_file.write(file_path.read_bytes())

        # Build relative link
        relative_link = f"_files/{file_path.name}"
        ext = file_path.suffix.lower()

        # Display images as clickable links
        if ext in LINKABLE_IMAGE_EXTENSIONS:
            file_handle.write(f"- [{file_path.name}]({relative_link})\n")
        else:
            file_handle.write(f"- {file_path.name}\n")

    file_handle.write("\n")


def _write_directory_page(
    ctx: Context,
    parts: list[str],
    subdirectories: list[tuple[str, ...]],
    modules: list[tuple[str, ...]],
    static_files: list[Path],
) -> Path:
    """
    Generate a documentation index page for a directory.

    Includes:
      - Backlink to parent if applicable.
      - Subdirectory links.
      - Module links.
      - Static file listings.

    :param ctx: Context to update with record.
    :param parts: Path parts of the directory.
    :param subdirectories: List of subdirectory paths.
    :param modules: List of module paths.
    :param static_files: List of static file paths in this directory.
    :return: Path to generated index.md file.
    """
    doc_path = Path("reference", *parts, "index.md")

    mkdocs_gen_files.set_edit_path(doc_path, SOURCE_DIR.joinpath(*parts, "__init__.py"))

    with mkdocs_gen_files.open(doc_path, "w") as file_handle:
        _write_backlink_if_needed(file_handle, parts)

        file_handle.write(f"# `{'.'.join(parts)}`\n\n")

        if subdirectories:
            file_handle.write("## 📁 Subdirectories\n\n")
            for child in subdirectories:
                label = display_parts_for(list(child))[-1]
                file_handle.write(f"- [{label}]({child[-1]}/index.md)\n")
            file_handle.write("\n")

        if modules:
            file_handle.write("## 📄 Modules\n\n")
            for child in modules:
                label = display_parts_for(list(child))[-1]
                file_handle.write(f"- [{label}]({child[-1]}/index.md)\n")
            file_handle.write("\n")

        _emit_static_files_list(parts, static_files, file_handle)

        # Fallback if directory is empty
        if not subdirectories and not modules and not static_files:
            file_handle.write("_This section has no subdirectories, modules, or static files yet._\n")

    _record_page(ctx, display_parts_for(parts), doc_path, is_directory=True)
    return doc_path


def generate_module_pages(package_dir: Path, ctx: Context) -> None:
    """
    Generate documentation pages for all public modules under a package.

    :param package_dir: Root package directory.
    :param ctx: Context object to update.
    :return: None
    """
    for python_file in _iter_public_python_files(package_dir):
        parts = _parts_from_source(python_file)
        parent_parts = parts[:-1]

        # Ensure parent folder exists in context
        ctx.ensure_folder(list(parent_parts))

        # Add this module under its parent
        ctx.children_modules.setdefault(parent_parts, []).append(parts)

        module_path = ".".join(parts)
        doc_path = Path("reference", *parts, "index.md")

        # Write module page and record it
        _write_module_page(doc_path, module_path, parent_parts, python_file)
        _record_page(ctx, display_parts_for(list(parts)), doc_path, is_directory=False)


def generate_directory_pages(ctx: Context) -> None:
    """
    Generate documentation index pages for all discovered directories.

    :param ctx: Context object holding traversal state.
    :return: None
    """
    for key in sorted(ctx.created_folders):
        parts = list(key)
        parts_tuple = tuple(parts)

        source_folder_fs = SOURCE_DIR.joinpath(*parts)
        source_folder_fs = SOURCE_DIR.joinpath(*parts)
        static_files = _collect_static_files(source_folder_fs)

        # Gather subdirectories and modules for this folder
        subdirectories = sorted(
            ctx.children_directories.get(parts_tuple, set()),
            key=_display_sort_key,
        )
        modules = sorted(
            ctx.children_modules.get(parts_tuple, []),
            key=_display_sort_key,
        )

        # Write directory index page
        _write_directory_page(ctx, parts, subdirectories, modules, static_files)
