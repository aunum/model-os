from dataclasses import dataclass
from typing import Dict, List
from pathlib import Path
import yaml

from modelos.pkg.id import PkgID


@dataclass
class PkgInfo:
    """Package info"""

    version: str
    description: str
    labels: Dict[str, str]
    tags: List[str]
    file_hash: Dict[str, str]

    def write(self, id: PkgID) -> None:
        pkg_path = id.to_path()
        metadir = Path(pkg_path).joinpath(".pkg")
        meta_path = metadir.joinpath("./info.yaml")
        with open(meta_path) as f:
            yam_map = yaml.dump(self.__dict__)
            f.write(yam_map)
