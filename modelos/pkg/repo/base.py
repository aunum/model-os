from abc import ABC, abstractmethod
from typing import List, Optional


from modelos.pkg.id import PkgID


class PkgRepo(ABC):
    """Package repository"""

    @abstractmethod
    def names(self) -> List[str]:
        """Names of the packages in the repo

        Returns:
            List[str]: Names of packages
        """
        pass

    @abstractmethod
    def versions(self, name: str) -> List[str]:
        """Versions of a package

        Args:
            name (str): Name of the package

        Returns:
            List[str]: List of package versions
        """
        pass

    @abstractmethod
    def latest(self, name: str) -> Optional[str]:
        """Latest release

        Args:
            name (str): Name of the package

        Returns:
            Optional[str]: Latest release, or none if no releases
        """
        pass

    @abstractmethod
    def releases(self, name: str) -> List[str]:
        """Releases for the package

        Args:
            name (str): Name of the package

        Returns:
            List[str]: A list of releases
        """
        pass

    @abstractmethod
    def ids(self) -> List[str]:
        """Ids of all packages

        Returns:
            List[str]: A list of ids
        """

    @abstractmethod
    def delete(self, name: str, version: str) -> None:
        """Delete a pkg

        Args:
            name (str): Name of the pkg
            version (Optional[str], optional): Versions to delete, use 'all' for all versions. Defaults to None.
        """
        pass

    @abstractmethod
    def clean(self) -> None:
        """Delete all non-releases"""
        pass

    @abstractmethod
    def build_id(self, name: str, version: str) -> PkgID:
        """Build a PkgID for the given name / version

        Args:
            name (str): Name of the package
            version (str): Version of the package

        Returns:
            PkgID: A PkgID
        """
        pass
