from __future__ import annotations
from dataclasses import dataclass
from typing import Type


@dataclass
class RuntimeID:
    """A runtime ID"""

    name: str
    kind: str


@dataclass
class ProcessID:
    """A process ID is a runtime process identifier"""

    name: str
    namespace: str
    version: str
    protocol: str

    @classmethod
    def parse(cls: Type[ProcessID], s: str) -> ProcessID:
        """Parse the string into an ID

        Args:
            s (str): String to parse

        Raises:
            ValueError: If string cannot be parsed

        Returns:
            ProcessID: A process ID
        """
        parts = s.split("://")
        if len(parts) < 2:
            raise ValueError(f"malformed process id '{s}'")

        protocol = parts[0]

        nm_parts = parts[1].split(".")
        name = nm_parts[0]
        namespace = nm_parts[1]
        version = nm_parts[2]

        return cls(name, namespace, version, protocol)

    def __str__(self):
        return f"{self.protocol}://{self.name}.{self.namespace}.{self.version}"
