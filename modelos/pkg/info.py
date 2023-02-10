from dataclasses import dataclass
from typing import Dict, List


@dataclass
class PkgInfo:
    """Package info"""

    version: str
    description: str
    labels: Dict[str, str]
    tags: List[str]
    file_hash: Dict[str, str]
