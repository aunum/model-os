from pathlib import Path
from typing import Dict, Any, Optional, List
import hashlib
import os
import inspect
import json

import git
import tomli
import modelos.util.rootpath as _rootpath
import distutils.core

DEFAULT_ARCHIVE_BASE_DIR = "./.mdl/archive"
SHORT_HASH_LENGTH = 7


def obj_in_project(obj: Any) -> bool:
    """Check if the object is in the current project

    Args:
        obj (Any): Object to check

    Raises:
        ValueError: If the root path cannot be detected

    Returns:
        bool: Whether it is in the current project
    """
    if obj.__module__ == "__main__":
        return True

    fp = Path(inspect.getfile(obj))

    if ".venv" in str(fp):
        return False

    r = _rootpath.detect()
    if r is None:
        raise ValueError("cannot detect root path")

    rpath = Path(r)

    return rpath in fp.parents


def obj_rel_path(obj: Any) -> str:
    """Object path relative to the project root

    Args:
        obj (Any): Object to find path

    Returns:
        str: The relative path
    """
    fp = Path(inspect.getfile(obj))
    r = _rootpath.detect()
    if r is None:
        raise ValueError("could not detect root path")
    rp = Path(r)

    local_path = str(fp.relative_to(rp))
    return local_path


def obj_module_path(obj: Any) -> str:
    """Get a module path for any given object

    Args:
        obj (Any): Object to get path for

    Returns:
        str: Relative path
    """
    local_path = obj_rel_path(obj)

    clean_path = os.path.splitext(local_path)[0]
    module_path = clean_path.replace("/", ".")
    return module_path


class Project:
    """A Python project"""

    rootpath: str

    def __init__(
        self, rootpath: Optional[str] = None, pattern: str = "requirements.txt|pyproject.toml|environment.yml"
    ) -> None:
        """Initialize a project

        Args:
            rootpath (str, optional): Root path of the project. Defaults to autodetect.
            pattern (str, optional): Pattern to find the root project.
                                     Default to 'requirements.txt|pyproject.toml|environment.yml'
        """

        if rootpath:
            self.rootpath = rootpath
        else:
            detected = _rootpath.detect(pattern=pattern)
            if not detected:
                raise ValueError("Project root path not detected or provided")

            self.rootpath = detected

    @classmethod
    def is_project(cls, pattern: str = "requirements.txt|pyproject.toml|environment.yml") -> bool:
        """Checks if this is a Python project

        Args:
            pattern (str, optional): Pattern to search for. Defaults
                                    to "requirements.txt|pyproject.toml|environment.yml".

        Returns:
            bool: Whether this is a Python project
        """
        detected = _rootpath.detect(pattern=pattern)
        if not detected:
            return False

        return True

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

    def has_requirements_file(self) -> bool:
        """Checks if the project has a requirements file

        Returns:
            bool: Whether the project has a requirements file
        """
        return _rootpath.has_requirements_file()

    def has_setup_script(self) -> bool:
        """Checks if the project has a setup script

        Returns:
            bool: Whether the project has a setup script
        """
        return _rootpath.has_setup_script()

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

        elif self.has_setup_script():
            setup = distutils.core.run_setup(os.path.join(self.rootpath, "setup.py"))
            env_files += json.dumps(setup.metadata.get_requires().sort())

        elif self.has_requirements_file():
            with open(os.path.join(self.rootpath, "requirements.txt"), "r") as f:
                env_files += f.read()

        elif self.is_conda_project():
            with open(os.path.join(self.rootpath, "environment.yml"), "r") as f:
                env_files += f.read()

        else:
            raise ValueError("unknown projecdt type")

        return env_files

    def get_deps(self) -> List[str]:
        """Get dependencies for the project

        Returns:
            List[str]: List of dependencies
        """

        if self.has_requirements_file():
            pth = os.path.join(self.rootpath, "requirements.txt")
            with open(pth, "r") as f:
                deps: List[str] = []
                lines = f.readlines()
                for line in lines:
                    deps.append(line.strip())

                return deps

        if self.is_poetry_project():
            pyproject_dict = self.load_pyproject()

            ret: List[str] = []
            try:
                pdeps = pyproject_dict["tool"]["poetry"]["dependencies"]
                for k, v in pdeps.items():
                    ret.append(f"{k}={v}")
            except KeyError:
                pass
            try:
                dev_deps = pyproject_dict["tool"]["poetry"]["dev-dependencies"]
                for k, v in dev_deps.items():
                    ret.append(f"{k}={v}")
            except KeyError:
                pass

            return ret

        if self.is_conda_project():
            raise NotImplementedError("Conda will be supported in the future")

        else:
            raise NotImplementedError("Unknown project type")
