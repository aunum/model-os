from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Type
from pathlib import Path
import os
import yaml
import json
from copy import deepcopy

from docker_image import reference

from modelos.pkg.id import PkgID
from modelos.util.path import list_files


@dataclass
class PkgInfo:
    """Package info"""

    name: str
    version: str
    scheme: str
    description: str
    repo: str
    labels: Dict[str, str]
    tags: List[str]
    file_hash: Dict[str, str]
    api_version: str = "v1"

    def flat_labels(self) -> Dict[str, str]:
        """Generate flat labels from info

        Returns:
            Dict[str, str]: A flat set of labels
        """
        out = deepcopy(self.labels)
        out["name"] = self.name
        out["version"] = self.version
        out["repo"] = self.repo
        out["scheme"] = self.scheme
        out["description"] = self.description
        out["tags"] = json.dumps(self.tags)
        out["file_hash"] = json.dumps(self.file_hash)
        out["api_version"] = self.api_version

        return out

    @classmethod
    def from_flat(cls: Type[PkgInfo], flat: Dict[str, str]) -> PkgInfo:
        """Create a pkginfo from a flat set of labels

        Args:
            flat (Dict[str, str]): A flat set of labels

        Returns:
            PkgInfo: A package info
        """
        name = flat.pop("name")
        version = flat.pop("version")
        desc = flat.pop("description")
        repo = flat.pop("repo")
        scheme = flat.pop("scheme")
        tags = json.loads(flat.pop("tags"))
        hashes = json.loads(flat.pop("file_hash"))
        api_ver = flat.pop("api_version")

        return cls(name, version, scheme, desc, repo, flat, tags, hashes, api_ver)

    def write_local(self, id: PkgID) -> None:
        """Write the pkg info to the local pkg

        Args:
            id (PkgID): ID of the pkg to write to
        """
        pkg_path = id.local_path()
        metadir = Path(pkg_path).joinpath(".mdl")
        meta_path = metadir.joinpath("./info.yaml")
        os.makedirs(metadir, exist_ok=True)
        with open(meta_path, "w") as f:
            yam_map = yaml.dump(self.__dict__)
            f.write(yam_map)

    def id(self) -> PkgID:
        host, repo = reference.Reference.split_docker_domain(self.repo)
        return PkgID(
            self.name,
            self.version,
            self.scheme,
            host,
            repo,
        )

    def show(self):
        print("---")
        out = self.__dict__
        out.pop("file_hash")

        print("contents: >")
        list_files(self.id().local_path())
        print("")
