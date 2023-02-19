from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Type

from docker_image import reference

from modelos.pkg.id import PkgID
from modelos.pkg.util import str_to_dict, str_to_list, dict_to_str, list_to_str


@dataclass
class PkgInfo:
    """Package info"""

    name: str
    version: str
    scheme: str
    description: str
    remote: str
    labels: Dict[str, str]
    tags: List[str]
    file_hash: Dict[str, str]
    api_version: str = "v1"

    def flat_labels(self) -> Dict[str, str]:
        """Generate flat labels from info

        Returns:
            Dict[str, str]: A flat set of labels
        """
        out = {}
        out["name"] = self.name
        out["version"] = self.version
        out["remote"] = self.remote
        out["scheme"] = self.scheme
        out["description"] = self.description
        out["labels"] = dict_to_str(self.labels)
        out["tags"] = list_to_str(self.tags)
        out["file_hash"] = dict_to_str(self.file_hash)
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
        remote = flat.pop("remote")
        scheme = flat.pop("scheme")
        labels = str_to_dict(flat.pop("labels"))
        tags = str_to_list(flat.pop("tags"))
        hashes = str_to_dict(flat.pop("file_hash"))
        api_ver = flat.pop("api_version")

        return cls(name, version, scheme, desc, remote, labels, tags, hashes, api_ver)

    def id(self) -> PkgID:
        """ID for the info

        Returns:
            PkgID: A package ID
        """
        host, repo = reference.Reference.split_docker_domain(self.remote)
        return PkgID(
            self.name,
            self.version,
            self.scheme,
            host,
            repo,
        )
