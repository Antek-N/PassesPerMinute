from dataclasses import dataclass, field

# Record structure:
# - tuple: arbitrary metadata (e.g., file info)
# - tuple[str, ...]: path parts (e.g., ("pkg", "subpkg"))
# - str: identifier/name
# - bool: status flag
Record = tuple[tuple, tuple[str, ...], str, bool]


@dataclass
class Context:
    """
    Holds the in-memory representation of a package hierarchy. (tree structure)

    Tracks:
      - Created folder paths.
      - Relationships between parent folders → child directories/modules.
      - Records associated with discovered entities.
    """

    # Set of folder paths already created (each as a tuple of path parts).
    created_folders: set[tuple[str, ...]] = field(default_factory=set)

    # Map: parent folder > set of child directories.
    children_directories: dict[tuple[str, ...], set[tuple[str, ...]]] = field(default_factory=dict)

    # Map: parent folder > list of child modules.
    children_modules: dict[tuple[str, ...], list[tuple[str, ...]]] = field(default_factory=dict)

    # Collected records for all discovered items (see Record type alias).
    records: list[Record] = field(default_factory=list)

    def ensure_folder(self, parts: list[str]) -> None:
        """
        Ensure that a folder path is registered in the context.

        If the folder path is not yet known:
          - Add it to created_folders.
          - Initialize its entry in children_directories and children_modules.

        :param parts: Path components for the folder (e.g., ["pkg", "subpkg"]).
        :return: None
        """
        key = tuple(parts)

        if key not in self.created_folders:
            self.created_folders.add(key)
            self.children_directories.setdefault(key, set())
            self.children_modules.setdefault(key, [])
