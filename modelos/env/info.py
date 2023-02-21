from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Type

from docker_image import reference

from .id import EnvID
from modelos.util.encoding import str_to_dict, str_to_list, dict_to_str, list_to_str


@dataclass
class EnvInfo:
    """Env info"""

    name: str
    version: str
    scheme: str
    description: str
    remote: str
    labels: Dict[str, str]
    tags: List[str]
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
        out["api_version"] = self.api_version

        return out

    @classmethod
    def from_flat(cls: Type[EnvInfo], flat: Dict[str, str]) -> EnvInfo:
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
        api_ver = flat.pop("api_version")

        return cls(name, version, scheme, desc, remote, labels, tags, api_ver)

    def id(self) -> EnvID:
        """ID for the info

        Returns:
            PkgID: A package ID
        """
        host, repo = reference.Reference.split_docker_domain(self.remote)
        return EnvID(
            self.name,
            self.version,
            self.scheme,
            host,
            repo,
        )
