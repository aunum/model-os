from __future__ import annotations


class Env:
    """A remote Python environment"""

    @classmethod
    def build(cls) -> Env:
        return cls()
