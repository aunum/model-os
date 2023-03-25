from __future__ import annotations
from dataclasses import dataclass
import yaml
from typing import Type


@dataclass
class LocalMeta:
    """Local object metadata stored in the same directory as the object def"""

    name: str
    """Name of the object"""

    object_uri: str
    """URI for the object"""

    cls_hash: str
    """Class hash"""

    @classmethod
    def filename(cls, name: str) -> str:
        return f"{name}_meta.yaml"

    @classmethod
    def read(cls: Type[LocalMeta], path: str) -> LocalMeta:
        with open(path, "r") as f:
            dct = yaml.safe_load(f.read())
            return cls(dct["name"], dct["object_uri"], dct["cls_hash"])

    def write(self) -> None:
        with open(self.filename(self.name), "w+") as f:
            f.write(yaml.dump(self))
