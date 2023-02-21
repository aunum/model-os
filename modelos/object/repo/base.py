from typing import Optional, List
from abc import ABC, abstractmethod

from modelos.object.id import ObjectID
from modelos.object.info import ObjectInfo


class ObjectRepo(ABC):
    """Object repository"""

    @abstractmethod
    def find(self, name: Optional[str], version: Optional[str]) -> List[ObjectID]:
        """Find environments

        Args:
            name (Optional[str]): Name of the object
            version (Optional[str]): Version of the object

        Returns:
            ObjectID: ID of the object
        """
        raise NotImplementedError()

    @abstractmethod
    def push(self, name: str, version: str) -> ObjectID:
        """Push the object remote

        Args:
            name (str): Name of the object
            version (str): Version of the object

        Returns:
            ObjectID: Object ID
        """
        raise NotImplementedError()

    @abstractmethod
    def pull(self, name: str, version: str) -> ObjectID:
        """Pull the object locally

        Args:
            name (str): Name of the object
            version (str): Version of the object

        Returns:
            ObjectID: Object ID
        """
        raise NotImplementedError()

    @abstractmethod
    def exists(self, name: str, version: str) -> bool:
        """Check if the object exists

        Args:
            name (str): Name of the object
            version (str): Version of the object

        Returns:
            bool: Whether the object exists
        """
        raise NotImplementedError()

    @abstractmethod
    def describe(self, name: str, version: str) -> ObjectInfo:
        """Describe the object

        Args:
            name (str): Name of the env
            version (str): Version of the env

        Returns:
            ObjectInfo: Info for the environment
        """
        pass

    @abstractmethod
    def parse_uri(self, uri: str) -> ObjectID:
        """Parse uri into an ObjectID

        Args:
            uri (str): URI to parse

        Returns:
            ObjectID: Object ID
        """
        pass
