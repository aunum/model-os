from typing import Optional
import subprocess
import sys

from modelos.pkg import Pkg
from modelos.project import Project

PYTHON_SCHEME = "py"


def module_name(name: str, version: str) -> str:
    """Module name for the python package

    Args:
        name (str): Name of the package
        version (str): Version of the package

    Returns:
        str: Module name for the package
    """
    ver = version.replace(".", "_").replace("-", "_")
    return f"{name}_{ver}"


class PythonPkg(Pkg):
    """A Python package"""

    def module_name(self) -> str:
        """Module name for the package

        Returns:
            str: Name of the modules
        """
        id = self.id()
        return module_name(id.name, id.version)

    def install(self) -> str:
        """Install as a python package

        Returns:
            str: The Python module name
        """
        out = subprocess.check_output([sys.executable, "-m", "pip", "install", "-e", self.root_dir()])

        for line in out.split():
            print(line.decode())

        return self.module_name()

    def publish(self, pypi_url: Optional[str] = None) -> str:
        """Publish to pypi"""
        raise NotImplementedError()

    def project(self) -> Project:
        """Get the Python project for the pkg"""
        return Project(self.root_dir())
