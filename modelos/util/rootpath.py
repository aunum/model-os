import sys
import os
import re
import six
from typing import Optional, Dict, Any

import yaml
import tomli

from os import path, listdir


DEFAULT_PATH = "."
DEFAULT_ROOT_FILENAME_MATCH_PATTERN = ".git|requirements.txt|pyproject.toml|environment.yml"


def detect(current_path: Optional[str] = None, pattern: Optional[str] = None) -> Optional[str]:
    """
    Find project root path from specified file/directory path,
    based on common project root file pattern.
    Examples:
        import rootpath
        rootpath.detect()
        rootpath.detect(__file__)
        rootpath.detect('./src')
    """

    current_path = current_path or os.getcwd()
    current_path = path.abspath(path.normpath(path.expanduser(current_path)))
    pattern = pattern or DEFAULT_ROOT_FILENAME_MATCH_PATTERN

    if not path.isdir(current_path):
        current_path = path.dirname(current_path)

    def find_root_path(current_path, pattern=None):
        if isinstance(pattern, six.string_types):
            pattern = re.compile(pattern)

        detecting = True

        found_more_files = None
        found_root = None
        found_system_root = None

        file_names = None
        root_file_names = None

        while detecting:
            file_names = listdir(current_path)
            found_more_files = bool(len(file_names) > 0)

            if not found_more_files:
                detecting = False

                return None

            root_file_names = filter(pattern.match, file_names)
            root_file_names = list(root_file_names)

            found_root = bool(len(root_file_names) > 0)

            if found_root:
                detecting = False

                return current_path

            found_system_root = bool(current_path == path.sep)

            if found_system_root:
                return None

            system_root = sys.executable

            while os.path.split(system_root)[1]:
                system_root = os.path.split(system_root)[0]

            if current_path == system_root:
                return None

            current_path = path.abspath(path.join(current_path, ".."))

    return find_root_path(current_path, pattern)


def is_pyproject(current_path: Optional[str] = None, pattern: Optional[str] = None) -> bool:
    path = detect(current_path, pattern)
    if path is None:
        return False

    config_path = os.path.join(path, "pyproject.toml")

    if os.path.exists(config_path):
        return True

    return False


def is_conda_project(current_path: Optional[str] = None, pattern: Optional[str] = None) -> bool:
    path = detect(current_path, pattern)
    if path is None:
        return False

    config_path = os.path.join(path, "environment.yml")

    if os.path.exists(config_path):
        return True

    return False


def is_pip_project(current_path: Optional[str] = None, pattern: Optional[str] = None) -> bool:
    path = detect(current_path, pattern)
    if path is None:
        return False

    config_path = os.path.join(path, "requirements.txt")

    if os.path.exists(config_path):
        return True

    return False


def is_git_root(current_path: Optional[str] = None, pattern: Optional[str] = None) -> bool:
    path = detect(current_path, pattern)
    if path is None:
        return False

    config_path = os.path.join(path, ".git")

    if os.path.exists(config_path):
        return True

    return False


def has_mdl_repo(current_path: Optional[str] = None, pattern: Optional[str] = None) -> bool:
    path = detect(current_path, pattern)
    if path is None:
        return False

    config_path = os.path.join(path, "mdl.yaml")

    if os.path.exists(config_path):
        return True

    return False


def load_mdl_repo(current_path: Optional[str] = None, pattern: Optional[str] = None) -> Dict[str, Any]:
    path = detect(current_path, pattern)
    if path is None:
        raise ValueError("could not find root path")

    config_path = os.path.join(path, "mdl.yaml")

    with open(config_path, "r") as stream:
        return yaml.safe_load(stream)


def load_conda_yaml(current_path: Optional[str] = None, pattern: Optional[str] = None) -> Dict[str, Any]:
    path = detect(current_path, pattern)
    if path is None:
        raise ValueError("could not find root path")

    config_path = os.path.join(path, "environment.yml")

    with open(config_path, "r") as stream:
        return yaml.safe_load(stream)


def load_pyproject(current_path: Optional[str] = None, pattern: Optional[str] = None) -> Dict[str, Any]:
    path = detect(current_path, pattern)
    if path is None:
        raise ValueError("could not find root path")

    config_path = os.path.join(path, "pyproject.toml")

    with open(config_path, "rb") as f:
        return tomli.load(f)
