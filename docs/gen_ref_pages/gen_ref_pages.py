"""
Automatic API Documentation Generator for MkDocs.

This script integrates with the `mkdocs-gen-files` plugin to dynamically
generate API reference documentation from a Python package located in
the source directory (by default `src/`, but this can be changed in `config.py`
via the `SOURCE_DIR` setting).

Workflow:
1. Detects the main package directory under `SOURCE_DIR` (logic in `config.py`).
2. Traverses the package structure (using `traverse.py`) to discover
   modules, subpackages, and static files.
3. Generates Markdown pages for:
   - Each Python module (using `::: module.path` blocks for mkdocstrings).
   - Each package/directory (with backlinks, subdirectory lists,
     module lists, and static file sections).
4. Stores navigation metadata in a `Context` object (`context.py`).
5. Builds navigation files:
   - `reference/index.md` → top-level reference index page,
   - `reference/SUMMARY.md` → literate navigation for MkDocs.

Usage (short form):
- Run this script as part of the MkDocs build process (`mkdocs build` or `mkdocs serve`).
- The script will automatically:
  - detect the target package,
  - create a documentation tree in the `reference/` directory,
  - prepare navigation for integration with MkDocs.

Usage (with MkDocs):
1) Install required packages:
   pip install mkdocs mkdocs-gen-files "mkdocstrings[python]"

2) Ensure your project layout looks for example like this:
   .
   ├─ mkdocs.yml
   ├─ docs/
   │  └─ gen_ref_pages/
   │     ├─ gen_ref_pages.py        # this script
   │     ├─ config.py
   │     ├─ context.py
   │     ├─ generate.py
   │     ├─ helpers.py
   │     └─ traverse.py
   ├─ src/                          # or another source dir set in config.SOURCE_DIR
   │  └─ <your_package>/...

3) Configure `mkdocs.yml` with plugins and navigation, e.g.:
   site_name: Your Documentation
   plugins:
     - search
     - gen-files:
         scripts:
           - docs/gen_ref_pages/gen_ref_pages.py   # path to this script
     - mkdocstrings:
         handlers:
           python:
             options:
               show_source: true
               docstring_style: google   # or "sphinx"/"numpy", depending on your style
   nav:
     - Reference: reference/              # generated reference section

4) Run:
   - Live preview: mkdocs serve
   - Build static site: mkdocs build

Customization:
- Configuration is located in `config.py`:
  - `SOURCE_DIR`: source directory where the package is located (default: `Path("src")`).
    You can change this to any other directory (e.g. `Path("packages")`).
  - `INCLUDE_PRIVATE`: whether to include private modules/packages (path parts starting with `_`).
  - `SECTION_TITLE_MAP` and `SECTION_ORDER`: control naming and ordering of sections in navigation.
  - `LINKABLE_IMAGE_EXTENSIONS`: which static files (in source directories) should be linked as clickable images.

This script is intended to be run automatically as part of the MkDocs build process.
You can place it anywhere in your repository and reference its path under `gen-files.scripts`.
"""

import sys
from pathlib import Path

# Ensure the current directory is on sys.path so local imports work correctly
THIS_DIR = Path(__file__).resolve().parent
THIS_DIR_STR = str(THIS_DIR)
if THIS_DIR_STR not in sys.path:
    sys.path.insert(0, THIS_DIR_STR)

import mkdocs_gen_files  # noqa E402
from config import INCLUDE_PRIVATE, find_package_dir  # noqa E402
from context import Context  # noqa E402
from generate import generate_directory_pages, generate_module_pages  # noqa E402
from traverse import traverse_directories  # noqa E402


def _build_nav(package_name: str, ctx: Context) -> None:
    """
    Build MkDocs navigation files from collected documentation records.

    - Creates `reference/index.md` with a title and introduction.
    - Creates `reference/SUMMARY.md` containing a literate navigation structure.

    :param package_name: Name of the discovered package.
    :param ctx: Context holding collected records from traversal.
    :return: None
    """
    nav = mkdocs_gen_files.Nav()

    # Sort collected records and populate the navigation
    for _, display, doc_rel_path, _ in sorted(ctx.records, key=lambda record: record[0]):
        nav[display] = doc_rel_path

    # Generate top-level index page
    with mkdocs_gen_files.open("reference/index.md", "w") as file_handle:
        file_handle.write(f"# Reference – `{package_name}`\n\n")
        file_handle.write("This section contains API documentation automatically " "generated from code.\n\n")

    # Generate SUMMARY.md for MkDocs navigation
    with mkdocs_gen_files.open("reference/SUMMARY.md", "w") as nav_file:
        nav_file.writelines(nav.build_literate_nav())


def main() -> None:
    """
    Entry point for documentation generation.

    - Finds the main package under `src/`.
    - Traverses directories to collect modules/folders.
    - Generates module and directory pages.
    - Builds MkDocs navigation files.

    :return: None
    """
    package_dir, package_name = find_package_dir(INCLUDE_PRIVATE)

    # Initialize a context object to hold traversal state and records
    ctx = Context()

    # Walk through directories and collect module/folder information
    traverse_directories(package_dir, package_name, INCLUDE_PRIVATE, ctx)

    # Generate documentation pages for modules and directories
    generate_module_pages(package_dir, ctx)
    generate_directory_pages(ctx)

    # Build navigation index files
    _build_nav(package_name, ctx)


# Run the main process when the script is executed
main()
