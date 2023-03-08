from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Type, Optional

from modelos.virtual.container.id import ImageID


@dataclass
class Version:
    """Version of the object"""

    interface: str
    """Version of the object interface, includes only the signatures of the client"""

    logic: Optional[str] = None
    """Version of the object code and its dependencies"""

    state: Optional[str] = None
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
        sver_parts = s.split(".")
        if s[0] == "v" and s[1].isnumeric() and len(sver_parts[0]) < 5:
            interface = sver_parts[0][1:]

            logic: Optional[str] = None
            if len(sver_parts) > 1:
                logic = sver_parts[1]

            state: Optional[str] = None
            if len(sver_parts) > 2:
                state = sver_parts[2]

            return cls(interface, logic, state)

        ver_parts = s.split("-")

        interface = ver_parts[0]

        if len(interface) != 5:
            raise ValueError(f"malformed version '{s}', cannot parse")

        logic = None
        if len(ver_parts) > 1:
            logic = sver_parts[1]

        state = None
        if len(ver_parts) > 2:
            state = ver_parts[2]

        return cls(interface, logic, state)

    def is_semver(self) -> bool:
        """Tells if the version is a semver

        Returns:
            bool: Whether the version is a semver
        """
        if len(self.interface) < 5 and self.interface.isnumeric():
            return True
        return False

    def is_interface(self) -> bool:
        """Check if the version is an interface

        Returns:
            bool: Whether the version is an interface
        """
        if not self.logic and not self.state:
            return True
        return False

    def is_object(self) -> bool:
        """Check if the version is an object

        Returns:
            bool: Whether the version is an object
        """
        if self.logic and not self.state:
            return True
        return False

    def is_instance(self) -> bool:
        """Check if the version is an instance

        Returns:
            bool: Whether the version is an instance
        """
        if self.logic and self.state:
            return True
        return False

    def is_compatible(self, other: Version) -> bool:
        """Check whether the given version is compatible
        Will only check the non-zero fields in the current object.

        Args:
            other (Version): Version to compare with

        Returns:
            bool: Whether they are compatible
        """
        if self.interface != other.interface:
            return False

        if self.logic and self.logic != other.logic:
            return False

        if self.state and self.state != other.state:
            return False

        return True

    def __str__(self):
        if self.is_instance():
            if self.is_semver():
                return f"v{self.interface}.{self.logic}.{self.state}"
            return f"{self.interface}-{self.logic}-{self.state}"

        elif self.is_object():
            if self.is_semver():
                return f"v{self.interface}.{self.logic}"
            return f"{self.interface}-{self.logic}"

        else:
            if self.is_semver():
                return f"v{self.interface}"
            return f"{self.interface}"

    def __eq__(self, other: Version) -> bool:  # type: ignore
        return self.interface == other.interface and self.logic == other.logic and self.state == other.state


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
    protocol: str

    def __init__(self, name: str, version: str, host: str, repo: str, protocol: str) -> None:
        """A Object ID

        Args:
            name (str): Name of the object
            version (str): Version of the object
            host (str): Host of the repo
            repo (str): Repository of the object
            protocol (str): Protocol of the object
        """
        if not re.fullmatch("([A-Za-z0-9\\-]+)", name):
            raise ValueError("Invalid name, must only be letters, numbers and hypens")
        self.name = name
        self.version = version
        self.repo = repo
        self.host = host
        self.protocol = protocol

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
        if self.protocol == "oci":
            return f"{self.host}/{self.repo}:{str(self.nv())}"
        else:
            raise ValueError(f"unknown protocol {self.protocol}")


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
