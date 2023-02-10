from __future__ import annotations
from typing import Type, Tuple
import re
from pathlib import Path

from modelos.env.image.id import ImageID
from modelos.local import pkg_home


class PkgID:
    """Package ID"""

    name: str
    version: str
    host: str
    repo: str

    def __init__(self, name: str, version: str, host: str, repo: str) -> None:
        """A Package ID

        Args:
            name (str): Name of the pkg
            version (str): Version of the pkg
            host (str): Host of the repo
            repo (str): Repository of the pkg
        """
        if not re.fullmatch("([A-Za-z0-9\\-]+)", name):
            raise ValueError("Invalid name, must only be letters, numbers and hypens")
        self.name = name
        self.version = version
        self.repo = repo
        self.host = host

    @classmethod
    def parse(cls: Type[PkgID], uri: str) -> PkgID:
        """Parse a package URI

        Args:
            uri (str): URI to parse

        Returns:
            PkgID: An ID
        """

        id = ImageID.from_ref(uri)
        name, version = cls.parse_tag(id.tag)

        return PkgID(name, version, id.host, id.repository)

    @classmethod
    def parse_tag(cls, tag: str) -> Tuple[str, str]:
        """Parse tag into name / version

        Args:
            tag (str): Tag to parse

        Returns:
            Tuple[str, str]: Name and version
        """
        tag_split = tag.split(".")

        if tag_split[0] != "pkg":
            raise ValueError(f"tag '{tag}' is not a package")

        name = tag_split[1]

        version_split = tag_split[2:]
        version = ".".join(version_split)

        return name, version

    def to_uri(self) -> str:
        """Convert to URI

        Returns:
            str: A URI
        """
        uri = f"{self.repo}:pkg.{self.name}.{self.version}"
        if self.host != "docker.io":
            uri = f"{self.host}/{uri}"
        return uri

    def to_path(self) -> str:
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
        return self.to_uri()
