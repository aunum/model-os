from abc import ABC, abstractmethod
from typing import List, Optional, Union


from modelos.pkg.id import PkgID, NVS
from modelos.pkg.info import PkgInfo
from modelos.pkg.scheme import DEFAULT_SCHEME


class RemotePkgRepo(ABC):
    """A remote package repository"""

    @abstractmethod
    def names(self, scheme: str = DEFAULT_SCHEME) -> List[str]:
        """Names of the packages in the repo

        Args:
            scheme (str, optional): Scheme of the pkg. Defaults to 'fs'

        Returns:
            List[str]: Names of packages
        """
        pass

    @abstractmethod
    def versions(self, name: str, scheme: str = DEFAULT_SCHEME) -> List[str]:
        """Versions of a package

        Args:
            name (str): Name of the package
            scheme (str, optional): Scheme of the pkg. Defaults to 'fs'

        Returns:
            List[str]: List of package versions
        """
        pass

    @abstractmethod
    def push(
        self,
        info: PkgInfo,
        files: Union[str, List[str]],
    ) -> None:
        """Push a pkg

        Args:
            info (PkgInfo): Package info
            files (List[str]): Files to push
        """
        pass

    @abstractmethod
    def pull(
        self,
        name: str,
        version: str,
        scheme: str = DEFAULT_SCHEME,
    ) -> None:
        """Pull a pkg

        Args:
            name (str): Name of the pkg
            version (str): Version of the pkg
            scheme (str, optional): Scheme of the pkg
        """
        pass

    @abstractmethod
    def parse(self, uri: str) -> PkgID:
        """Parse a URI into a package ID

        Args:
            uri (str): URI of the pkg

        Returns:
            PkgID: A package ID
        """
        pass

    @classmethod
    @abstractmethod
    def build_uri(cls, id: PkgID) -> str:
        """Generate a URI for the pkg id

        Args:
            id (PkgID): ID to generate URI for

        Returns:
            str: A URI
        """
        pass

    @abstractmethod
    def uri(self) -> str:
        """Generate a URI for the repo

        Returns:
            str: A URI
        """
        pass

    @abstractmethod
    def info(self, name: str, version: str, scheme: str = DEFAULT_SCHEME) -> PkgInfo:
        """Info for the pkg

        Args:
            name (str): Name of the pkg
            version (str): Version of the pkg
            scheme (str, optional): Scheme of the pkg. Defaults to 'fs'

        Returns:
            PkgInfo: Pkg info
        """
        pass

    @abstractmethod
    def latest(self, name: str, scheme: str = DEFAULT_SCHEME) -> Optional[str]:
        """Latest release

        Args:
            name (str): Name of the package
            scheme (str, optional): Scheme of the pkg. Defaults to 'fs'

        Returns:
            Optional[str]: Latest release, or None if no releases
        """
        pass

    @abstractmethod
    def releases(self, name: str, scheme: str = DEFAULT_SCHEME) -> List[str]:
        """Releases for the package

        Args:
            name (str): Name of the package
            scheme (str, optional): Scheme of the pkg. Defaults to 'fs'

        Returns:
            List[str]: A list of releases
        """
        pass

    @abstractmethod
    def ids(self) -> List[PkgID]:
        """List of package IDs of all packages

        Returns:
            List[str]: A list of pkg ids
        """
        pass

    @abstractmethod
    def delete(self, name: str, version: str, scheme: str = DEFAULT_SCHEME) -> None:
        """Delete a pkg

        Args:
            name (str): Name of the pkg
            version (Optional[str], optional): Versions to delete, use 'all' for all versions. Defaults to None.
            scheme (str, optional): Scheme of the pkg. Defaults to 'fs'
        """
        pass

    @abstractmethod
    def clean(self, name: str, scheme: str = DEFAULT_SCHEME, releases: bool = False) -> None:
        """Delete unused pkgs

        Args:
            name (str): Name of the pkg
            scheme (str, optional): Scheme of the pkg. Defaults to 'fs'
            releases (bool, optional): Whether to delete releases. Defaults to False.
        """
        pass

    @abstractmethod
    def build_id(self, nvs: NVS) -> PkgID:
        """Build a PkgID for the given name / version

        Args:
            name (str): Name of the package

        Returns:
            PkgID: A PkgID
        """
        pass

    @abstractmethod
    def local_path(self, name: Optional[str], version: Optional[str] = None, scheme: str = DEFAULT_SCHEME) -> str:
        """Local path of the pkg

        Args:
            name (Optional[str], optional): Name of the pkg
            version (Optional[str], optional): Version of the pkg
            scheme (str, optional): Scheme of the pkg. Defaults to 'fs'

        Returns:
            str: Local path of the pkg
        """
        pass
