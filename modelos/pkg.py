from __future__ import annotations
from typing import List


class Pkg:
    """A package is a versioned filesystem"""

    def __init__(self) -> None:
        pass

    @classmethod
    def push(cls) -> str:
        raise NotImplementedError()

    def pull(self) -> Pkg:
        raise NotImplementedError()

    def ls(self) -> List[str]:
        raise NotImplementedError()

    def open(self):
        raise NotImplementedError()
