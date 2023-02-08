from __future__ import annotations
from typing import List, Type, Dict, Optional
import re
import os
from pathlib import Path
import logging
import shutil

import ocifacts as of

from modelos.env.image.id import ImageID
from modelos.local import pkg_home
from modelos.env.image.registry import get_img_labels


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
            host (str): OCI host
            repo (str): OCI repo
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
        tag_split = id.tag.split(".")

        if tag_split[0] != "pkg":
            raise ValueError(f"uri '{uri}' is not a package")

        name = tag_split[1]

        version_split = tag_split[2:]
        version = ".".join(version_split)

        return PkgID(name, version, id.repository, id.host)

    def to_uri(self) -> str:
        """Convert to URI

        Returns:
            str: A URI
        """
        return f"{self.repo}:pkg.{self.name}.{self.version}"

    def __str__(self):
        return self.to_uri()


class Pkg:
    """A package is an immutable versioned filesystem"""

    _filepath: str
    _id: PkgID

    def __init__(
        self,
        filepath: str,
        id: PkgID,
    ) -> None:
        """A versioned immutable filesystem

        Args:
            filepath (str): Local path to the package
            id (PkgID): ID of the package
        """
        self._filepath = filepath
        self._id = id

    @classmethod
    def push(cls: Type[Pkg], filepath: str, uri: str, description: str, labels: Optional[Dict[str, str]] = None) -> Pkg:
        """Push a package

        Args:
            filepath (str): Filepath to push as a package
            uri (str): URI to push to
            description (str): Description of the package
            labels(Dict[str, str], optional): Labels for the package

        Returns:
            Pkg: A package
        """
        id = PkgID.parse(uri)
        pkg_path = cls._id_to_path(id)

        if not labels:
            labels = {}

        labels["description"] = description

        shutil.copytree(filepath, pkg_path)
        of.push(uri, filepath=pkg_path, labels=labels)

        return cls(pkg_path, id)

    @classmethod
    def pull(cls: Type[Pkg], uri: str) -> Pkg:
        """Pull a package

        Args:
            uri (str): URI to pull

        Returns:
            Pkg: A package
        """
        id = PkgID.parse(uri)
        out = cls._id_to_path(id)

        of.pull(uri, out)
        logging.info(f"pulled pkg '{uri}' to '{out}'")

        return cls(out, id)

    def ls(self, dir: str = "./") -> List[str]:
        """List the package contents

        Args:
            dir (str): Directory to list within the package

        Returns:
            List[str]: List of contents
        """
        return os.listdir(Path(self._filepath).joinpath(dir))

    def open(self):
        """Open a file in the package"""
        raise NotImplementedError()

    def filepath(self) -> str:
        """Local filepath of the package

        Returns:
            str: Filepath
        """
        return self._filepath

    def id(self) -> PkgID:
        """ID of the package

        Returns:
            PkgID: ID
        """
        return self._id

    @classmethod
    def describe(cls, uri: str) -> None:
        """Describe the URI

        Args:
            uri (str): URI to describe
        """
        pass

    @classmethod
    def _id_to_path(cls, id: PkgID) -> str:
        out_path = Path(pkg_home()).joinpath(id.host)

        repo_parts = id.repo.split("/")
        for part in repo_parts:
            out_path = out_path.joinpath(part)

        out_path = out_path.joinpath(id.name).joinpath(id.version)
        out = str(out_path)

        return out


def push(filepath: str, uri: str, description: str, labels: Optional[Dict[str, str]] = None) -> Pkg:
    """Push a package

    Args:
        filepath (str): Local filepath to push
        uri (str): URI to push to
        description (str): Description of the package
        labels(Dict[str, str], optional): Labels for the package

    Returns:
        Pkg: A package
    """
    return Pkg.push(filepath, uri, description, labels)


def pull(uri: str) -> Pkg:
    """Pull a package

    Args:
        uri (str): URI to pull

    Returns:
        Pkg: A package
    """
    return Pkg.pull(uri)


def ls(uri: str, dir: str = "./") -> List[str]:
    """List files in a package

    Args:
        uri (str): URI to package
        dir (str, optional): Directory to list. Defaults to "./".

    Returns:
        List[str]: List of contents
    """
    pkg = Pkg.pull(uri)
    return pkg.ls(dir)


def open(uri: str, filepath: str):
    pass


def describe(uri: str) -> None:
    """Describe the uri

    Args:
        uri (str): URI to describe
    """
    return Pkg.describe(uri)
