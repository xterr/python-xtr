"""The application package the makers write into, not found by the import system."""

from __future__ import annotations

from .maker_error import MakerError

__all__ = ["AppPackageNotFoundError"]


class AppPackageNotFoundError(MakerError):
    """The application package the makers write into, not found by the import system.

    Raised the first time a maker needs the package, never while the container
    is built, so the console keeps running and the message can say which
    setting to change.

    Attributes:
        root_package: The package that was looked for.
        project_dir: The project the makers write into.
    """

    root_package: str
    project_dir: str

    def __init__(self, root_package: str, project_dir: str) -> None:
        """Record the package that was looked for, and the project it was looked for from."""
        self.root_package = root_package
        self.project_dir = project_dir
        message = (
            f"the application package {root_package!r} of {project_dir} cannot be imported; "
            "install the project into its environment, or set MakerConfig.root_package to "
            "the package to write into"
        )
        super().__init__(message)
