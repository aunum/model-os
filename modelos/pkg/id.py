from __future__ import annotations
import re
from pathlib import Path
from dataclasses import dataclass
import yaml

from modelos.local import pkg_home


@dataclass
class NVS:
    """Name, version, scheme of the pkg"""

    name: str
    version: str
    scheme: str = "fs"

    @classmethod
    def parse(cls, s: str) -> NVS:
        """Parse the given string to an SNV

        Args:
            s (str): String to parse

        Returns:
            SNV: An SNV
        """
        tag_split = s.split(".")

        if tag_split[0] != "pkg":
            raise ValueError(f"namever '{s}' is not a package")

        scheme = tag_split[1]
        name = tag_split[2]

        version_split = tag_split[3:]
        version = ".".join(version_split)

        return NVS(scheme, name, version)

    def __str__(self):
        return f"pkg.{self.scheme}.{self.name}.{self.version}"


class PkgID:
    """Package ID"""

    scheme: str
    name: str
    version: str
    host: str
    repo: str

    def __init__(self, name: str, version: str, scheme: str, host: str, repo: str) -> None:
        """A Package ID

        Args:
            name (str): Name of the pkg
            version (str): Version of the pkg
            scheme (str): Scheme of the pkg
            host (str): Host of the repo
            repo (str): Repository of the pkg
        """
        if not re.fullmatch("([A-Za-z0-9\\-]+)", name):
            raise ValueError("Invalid name, must only be letters, numbers and hypens")
        self.name = name
        self.version = version
        self.repo = repo
        self.host = host
        self.scheme = scheme

    @classmethod
    def parse_nvs(cls, nvs: str) -> NVS:
        """Parse nvs string

        Args:
            nvs (str): NVS string to parse

        Returns:
            NVS: An NVS
        """
        return NVS.parse(nvs)

    def nvs(self) -> NVS:
        """NVS for this ID

        Returns:
            NVS: The NVS
        """
        return NVS(self.name, self.version, self.scheme)

    def local_path(self) -> str:
        """Convert the ID to a local path

        Returns:
            str: The local path
        """
        out_path = Path(pkg_home()).joinpath(self.host)

        repo_parts = self.repo.split("/")
        for part in repo_parts:
            out_path = out_path.joinpath(part)

        out_path = out_path.joinpath(self.name).joinpath(self.version)
        out = str(out_path)

        return out

    def __str__(self):
        return yaml.dump(self.__dict__)
