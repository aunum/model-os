from __future__ import annotations
import re
from dataclasses import dataclass

from modelos.virtual.container.id import ImageID


@dataclass
class NVS:
    """Name, version, scheme of the environment"""

    name: str
    version: str
    scheme: str = "py"

    @classmethod
    def parse(cls, s: str) -> NVS:
        """Parse the given string to an NVS

        Args:
            s (str): String to parse

        Returns:
            NVS: An NVS
        """
        tag_split = s.split(".")

        if tag_split[0] != "env":
            raise ValueError(f"namever '{s}' is not a environment")

        scheme = tag_split[1]
        name = tag_split[2]

        version_split = tag_split[3:]
        version = ".".join(version_split)

        return NVS(name, version, scheme)

    def __str__(self):
        return f"env.{self.scheme}.{self.name}.{self.version}"


class EnvID:
    """Environment ID"""

    scheme: str
    name: str
    version: str
    host: str
    repo: str

    def __init__(self, name: str, version: str, scheme: str, host: str, repo: str) -> None:
        """An environment ID

        Args:
            name (str): Name of the env
            version (str): Version of the env
            scheme (str): Scheme of the env
            host (str): Host of the env
            repo (str): Repository of the env
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

    def __str__(self):
        return f"{self.host}/{self.repo}:{str(self.nvs())}"


def nvs_from_uri(uri: str) -> NVS:
    """Grab the NVS from the URI

    Args:
        uri (str): URI to split

    Returns:
        NVS: An NVS
    """
    if uri.startswith("s3://"):
        raise ValueError("s3 not yet supported")

    elif uri.startswith("gs://"):
        raise ValueError("gs not yet supported")

    elif uri.startswith("oci://"):
        uri_parts = uri.split(":")
        if len(uri_parts) < 2:
            raise ValueError(f"uri given has no tag: {uri}")
        id = ImageID.from_ref(uri)
        return NVS.parse(id.tag)

    else:
        uri_parts = uri.split(":")
        if len(uri_parts) < 2:
            raise ValueError(f"uri given has no tag: {uri}")
        id = ImageID.from_ref(uri)
        return NVS.parse(id.tag)
