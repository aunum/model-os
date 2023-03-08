from abc import ABC, abstractmethod
from typing import Optional, List, Dict

from modelos.object.id import ObjectID, Version
from modelos.object.info import ObjectArtifactInfo


class ObjectRepo(ABC):
    """An object repository"""

    @classmethod
    @abstractmethod
    def parse(cls, uri: str) -> ObjectID:
        """Parse a URI into a object ID

        Args:
            uri (str): URI of the object

        Returns:
            ObjectID: An object ID
        """
        pass

    @abstractmethod
    def build_id(self, name: str, version: str) -> ObjectID:
        """Build ID for the object

        Args:
            name (str): Name of the object
            version (str): Version of the object

        Returns:
            ObjectID: The object ID
        """
        pass

    @classmethod
    @abstractmethod
    def build_uri(cls, id: ObjectID) -> str:
        """Generate a URI for the object id

        Args:
            id (ObjectID): ID to generate URI for

        Returns:
            str: A URI
        """
        pass

    @abstractmethod
    def host(self) -> str:
        """Host of the repo

        Returns:
            str: Host name
        """
        pass

    @abstractmethod
    def name(self) -> str:
        """Name of the repo

        Returns:
            str: Repo name
        """
        pass

    @abstractmethod
    def protocol(self) -> str:
        """Protocol of the repo

        Returns:
            str: Protocol
        """
        pass

    @abstractmethod
    def find(self, name: str, version: Optional[str]) -> List[ObjectID]:
        """Find the object

        Args:
            name (str): Name of the object
            version (Optional[str], optional): Version of the object

        Returns:
            List[ObjectID]: A list of objects
        """
        pass

    @abstractmethod
    def build(
        self,
        name: str,
        version: str,
        command: List[str],
        dev_dependencies: bool = False,
        clean: bool = True,
        labels: Optional[Dict[str, str]] = None,
    ) -> ObjectID:
        """Build the object

        Args:
            name (str): Name of the object
            version (str): Version of the object
            command (List[str]): Command to launch object.
            dev_dependencies (bool, optional): Whether to install dev dependencies. Defaults to False.
            clean (bool, optional): Whether to clean generated files. Defaults to True.
            labels (Dict[str, str], optional). Labels to add to the image. Defaults to None.

        Returns:
            ObjectID: The object ID
        """
        pass

    @abstractmethod
    def find_or_build(
        self,
        name: str,
        version: str,
        command: List[str],
        dev_dependencies: bool = False,
        clean: bool = True,
        labels: Optional[Dict[str, str]] = None,
    ) -> ObjectID:
        """Find or build the object

        Args:
            name (str): Name of the object
            version (str): Version of the object
            command (List[str]): Command to launch object.
            dev_dependencies (bool, optional): Whether to install dev dependencies. Defaults to False.
            clean (bool, optional): Whether to clean generated files. Defaults to True.
            labels (Dict[str, str], optional). Labels to add to the image. Defaults to None.

        Returns:
            ObjectID: The object ID
        """
        pass

    @abstractmethod
    def push(self, name: str, version: str) -> ObjectID:
        """Push the object to the remote

        Args:
            name (str): Name of the object
            version (str): Version of the object

        Returns:
            ObjectID: The object ID
        """
        pass

    @abstractmethod
    def pull(self, name: str, version: str) -> ObjectID:
        """Pull the object from remote

        Args:
            name (str): Name of the object
            version (str): Version of the object

        Returns:
            ObjectID: The object ID
        """
        pass

    @abstractmethod
    def info(self, name: str, version: str) -> ObjectArtifactInfo:
        """Info for the object artifact

        Args:
            name (str): Name of the object
            version (str): Version of the object

        Returns:
            ObjectArtifactInfo: Object info
        """
        pass

    @abstractmethod
    def show(self, id: ObjectID) -> None:
        """Show the object

        Args:
            id (ObjectID): ID of the object
        """
        pass

    @abstractmethod
    def names(self) -> List[str]:
        """Names of the objects in the repo

        Returns:
            List[str]: Names of objects
        """
        pass

    @abstractmethod
    def versions(self, name: str, compatible_with: Optional[Version] = None) -> List[str]:
        """Versions of a object

        Args:
            name (str): Name of the object
            compatible_with (Version): Only return versions compatible with the given version

        Returns:
            List[str]: List of object versions
        """
        pass

    @abstractmethod
    def latest(self, name: str) -> Optional[str]:
        """Latest release

        Args:
            name (str): Name of the object

        Returns:
            Optional[str]: Latest release, or None if no releases
        """
        pass

    @abstractmethod
    def releases(self, name: str) -> List[str]:
        """Releases for the object

        Args:
            name (str): Name of the object

        Returns:
            List[str]: A list of releases
        """
        pass

    @abstractmethod
    def ids(self) -> List[ObjectID]:
        """List of object ids of all objects

        Returns:
            List[str]: A list of object ids
        """
        pass

    @abstractmethod
    def delete(self, name: str, version: str) -> None:
        """Delete a object

        Args:
            name (str): Name of the object
            version (Optional[str], optional): Versions to delete, use 'all' for all versions. Defaults to None.
        """
        pass

    @abstractmethod
    def clean(self, name: str, releases: bool = False) -> None:
        """Delete unused objects

        Args:
            name (str): Name of the pkg
            releases (bool, optional): Whether to delete releases. Defaults to False.
        """
        pass
