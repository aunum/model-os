from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Type, Any, Optional
import json

from .id import ObjectID


@dataclass
class ObjectInfo:
    """Object info"""

    name: str
    version: str
    description: str
    env_sha: str
    uri: str
    server_entrypoint: str
    locked: bool
    ext: Optional[Dict[str, str]] = None


@dataclass
class ObjectArtifactInfo:
    """Object artifact info"""

    name: str
    version: str
    host: str
    repo: str
    protocol: str
    schema: Dict[str, Any]
    description: str
    server_entrypoint: str
    interface_hash: str
    class_hash: str
    instance_hash: str
    env_hash: str
    labels: Optional[Dict[str, str]] = None
    tags: Optional[List[str]] = None
    api_version: str = "v1"

    def flat_labels(self) -> Dict[str, str]:
        """Generate flat labels from info

        Returns:
            Dict[str, str]: A flat set of labels
        """
        if not self.labels:
            self.labels = {}

        if not self.tags:
            self.tags = []

        out = {}
        out["name"] = self.name
        out["version"] = self.version
        out["host"] = self.host
        out["repo"] = self.repo
        out["protocol"] = self.protocol
        out["description"] = self.description
        out["schema"] = json.dumps(self.schema)
        out["labels"] = json.dumps(self.labels)
        out["interface_hash"] = self.interface_hash
        out["class_hash"] = self.class_hash
        out["instance_hash"] = self.instance_hash
        out["env_hash"] = self.env_hash
        out["tags"] = json.dumps(self.tags)
        out["server_entrypoint"] = self.server_entrypoint
        out["api_version"] = self.api_version

        return out

    @classmethod
    def from_flat(cls: Type[ObjectArtifactInfo], flat: Dict[str, str]) -> ObjectArtifactInfo:
        """Create a pkginfo from a flat set of labels

        Args:
            flat (Dict[str, str]): A flat set of labels

        Returns:
            PkgInfo: A package info
        """
        name = flat.pop("name")
        version = flat.pop("version")
        host = flat.pop("host")
        repo = flat.pop("repo")
        protocol = flat.pop("protocol")
        desc = flat.pop("description")
        schema = json.loads(flat.pop("schema"))
        labels = json.loads(flat.pop("labels"))
        interface_hash = flat.pop("interface_hash")
        class_hash = flat.pop("class_hash")
        instance_hash = flat.pop("instance_hash")
        env_hash = flat.pop("env_hash")
        tags = json.loads(flat.pop("tags"))
        server_entrypoint = flat.pop("server_entrypoint")
        api_ver = flat.pop("api_version")

        return cls(
            name,
            version,
            host,
            repo,
            protocol,
            schema,
            desc,
            server_entrypoint,
            interface_hash,
            class_hash,
            instance_hash,
            env_hash,
            labels,
            tags,
            api_ver,
        )

    def id(self) -> ObjectID:
        """ID for the object

        Returns:
            ObjectID: An object ID
        """
        return ObjectID(
            self.name,
            self.version,
            self.host,
            self.repo,
            self.protocol,
        )
