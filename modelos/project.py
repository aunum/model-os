from pathlib import Path
from typing import Dict, Any, Optional
import hashlib
import os
import inspect

import git
import tomli
import modelos.util.rootpath as _rootpath

DEFAULT_ARCHIVE_BASE_DIR = "./.mdl/archive"
SHORT_HASH_LENGTH = 7


def obj_module_path(obj: Any) -> str:
    """Get a module path for any given object"""

    fp = Path(inspect.getfile(obj))
    r = _rootpath.detect()
    if r is None:
        raise ValueError("could not detect root path")
    rp = Path(r)

    local_path = str(fp.relative_to(rp))

    clean_path = os.path.splitext(local_path)[0]
    module_path = clean_path.replace("/", ".")
    return module_path


class Project:
    """A Python project"""

    rootpath: str

    def __init__(self, rootpath: Optional[str] = None) -> None:
        """Initialize a project

        Args:
            rootpath (str, optional): Root path of the project. Defaults to autodetect.
        """

        if rootpath:
            self.rootpath = rootpath
        else:
            detected = _rootpath.detect()
            if not detected:
                raise ValueError("Project root path not detected or provided")

            self.rootpath = detected

    def load_pyproject(self) -> Dict[str, Any]:
        """Load the pyproject file as a dictionary

        Returns:
            Dict[str, Any]: A dictionary of the pyproject
        """

        path = os.path.join(self.rootpath, "pyproject.toml")
        with open(path, "rb") as f:
            pyproject_dict = tomli.load(f)
            return pyproject_dict

    def is_poetry_project(self) -> bool:
        """Checks whether the project is a poetry project

        Returns:
            bool: Whether the project is a poetry project
        """

        if not _rootpath.is_pyproject():
            return False

        pyproject_dict = self.load_pyproject()

        is_poetry_project = False
        try:
            pyproject_dict["tool"]["poetry"]
            is_poetry_project = True
        except KeyError:
            pass

        return is_poetry_project

    def is_pip_project(self) -> bool:
        """Checks if the project is a pip project

        Returns:
            bool: Whether the project is a pip project
        """
        return _rootpath.is_pip_project()

    def is_conda_project(self) -> bool:
        """Checks whether the project is a conda project

        Returns:
            bool: Whether the project is a conda project
        """
        return _rootpath.is_conda_project()

    def rel_project_path(self, git_repo: git.Repo) -> str:
        """Project path relative to git repository

        Returns:
            str: Relative project path
        """

        return str(os.path.relpath(self.rootpath, str(git_repo.working_dir)))

    def env_sha(self) -> str:
        """Hash for the Python environment

        Returns:
            str: a SHA256 hash of the Python environment
        """

        env_files = self.env_code()

        h = hashlib.new("sha256")
        h.update(env_files.encode())

        return h.hexdigest()[-SHORT_HASH_LENGTH:]

    def env_code(self) -> str:
        """Environment code

        Returns:
            str: a SHA256 hash of the Python environment
        """

        env_files = ""

        if self.is_poetry_project():
            with open(os.path.join(self.rootpath, "poetry.lock"), "r") as f:
                env_files += f.read()

        if self.is_pip_project():
            with open(os.path.join(self.rootpath, "requirements.txt"), "r") as f:
                env_files += f.read()

        if self.is_conda_project():
            with open(os.path.join(self.rootpath, "environment.yml"), "r") as f:
                env_files += f.read()

        return env_files
