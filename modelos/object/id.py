from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Type

from semver import VersionInfo

from modelos.virtual.container.id import ImageID


@dataclass
class Version:
    """Version of the object"""

    interface: str
    """Version of the object interface, includes only the signatures of the client"""

    logic: str
    """Version of the object code and its dependencies"""

    state: str
    """Version of the object state based on its attributes"""

    @classmethod
    def parse(cls: Type[Version], s: str) -> Version:
        """Parse version string into a version

        Args:
            s (str): String to parse

        Raises:
            ValueError: If version cannot be parsed

        Returns:
            Version: A Version
        """
        if s[0] == "v":
            try:
                info = VersionInfo.parse(s[1:])
                return cls(info.major, info.minor, info.patch)
            except Exception:
                pass
        ver_parts = s.split("-")
        if len(ver_parts) != 3:
            raise ValueError(f"version '{s}' is an unexpected form")

        return cls(ver_parts[0], ver_parts[1], ver_parts[2])

    def is_semver(self) -> bool:
        """Tells if the version is a semver

        Returns:
            bool: Whether the version is a semver
        """
        try:
            VersionInfo.parse(f"{self.interface}.{self.logic}.{self.state}")
            return True
        except Exception:
            return False

    def __str__(self):
        if self.is_semver():
            return f"v{self.interface}.{self.logic}.{self.state}"
        return f"{self.interface}-{self.logic}-{self.state}"


@dataclass
class NV:
    """Name, version of the object"""

    name: str
    version: str

    @classmethod
    def parse(cls, s: str) -> NV:
        """Parse the given string to an NV

        Args:
            s (str): String to parse

        Returns:
            NV: An NV
        """
        tag_split = s.split(".")

        if tag_split[0] != "obj":
            raise ValueError(f"namever '{s}' is not a object")

        name = tag_split[1]

        version_split = tag_split[2:]
        version = ".".join(version_split)

        return NV(name, version)

    def parse_version(self) -> Version:
        """Parse the version string into a version object

        Raises:
            ValueError: If version cannot be parsed

        Returns:
            Version: A Version
        """
        return Version.parse(self.version)

    def __str__(self):
        return f"obj.{self.name}.{self.version}"


class ObjectID:
    """Object ID"""

    name: str
    version: str
    host: str
    repo: str

    def __init__(self, name: str, version: str, host: str, repo: str) -> None:
        """A Object ID

        Args:
            name (str): Name of the object
            version (str): Version of the object
            host (str): Host of the repo
            repo (str): Repository of the object
        """
        if not re.fullmatch("([A-Za-z0-9\\-]+)", name):
            raise ValueError("Invalid name, must only be letters, numbers and hypens")
        self.name = name
        self.version = version
        self.repo = repo
        self.host = host

    @classmethod
    def parse_nv(cls, nvs: str) -> NV:
        """Parse nvs string

        Args:
            nvs (str): NVS string to parse

        Returns:
            NVS: An NVS
        """
        return NV.parse(nvs)

    def nv(self) -> NV:
        """NV for this ID

        Returns:
            NV: The NV
        """
        return NV(self.name, self.version)

    def __str__(self):
        return f"{self.host}/{self.repo}:{str(self.nv())}"


def nv_from_uri(uri: str) -> NV:
    """Grab the NV from the URI

    Args:
        uri (str): URI to split

    Returns:
        NV: An NV
    """
    if uri.startswith("oci://"):
        uri_parts = uri.split(":")
        if len(uri_parts) < 2:
            raise ValueError(f"uri given has no tag: {uri}")
        id = ImageID.from_ref(uri)
        return NV.parse(id.tag)

    else:
        uri_parts = uri.split(":")
        if len(uri_parts) < 2:
            raise ValueError(f"uri given has no tag: {uri}")
        id = ImageID.from_ref(uri)
        return NV.parse(id.tag)
