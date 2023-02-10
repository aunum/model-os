from typing import List, Optional

from opencontainers.distribution.reggie import NewClient
from semver import VersionInfo

from modelos.pkg.repo.base import PkgRepo
from modelos.pkg.id import PkgID
from modelos.env.image.registry import get_oci_client, get_repo_tags


class OCIPkgRepo(PkgRepo):
    """OCI based package repository"""

    client: NewClient
    uri: str

    def __init__(self, uri: str) -> None:
        """Connect to an OCI based pkg repo

        Args:
            uri (str): URI to connect to
        """
        self.client = get_oci_client(uri)
        self.uri = uri

    def names(self) -> List[str]:
        """Names of the packages in the repo

        Returns:
            List[str]: Names of packages
        """
        names = set()
        for tag in get_repo_tags(self.uri, self.client):
            try:
                name, _ = PkgID.parse_tag(tag)
                names.add(name)
            except Exception:
                continue

        return list(names)

    def versions(self, name: str) -> List[str]:
        """Versions of a package

        Args:
            name (str): Name of the package

        Returns:
            List[str]: List of package versions
        """
        versions = []
        for tag in get_repo_tags(self.uri, self.client):
            try:
                nm, ver = PkgID.parse_tag(tag)
                if nm != name:
                    continue
                versions.append(ver)
            except Exception:
                continue

        return versions

    def latest(self, name: str) -> Optional[str]:
        """Latest release

        Args:
            name (str): Name of the package

        Returns:
            Optional[str]: Latest release, or None if no releases
        """
        tags = get_repo_tags(self.uri, self.client)

        latest_version: Optional[VersionInfo] = None
        for tag in tags:
            try:
                nm, ver = PkgID.parse_tag(tag)
                if nm != name:
                    continue
                info = VersionInfo.parse(ver[1:])
                if latest_version is None:
                    latest_version = info

                if info > latest_version:
                    latest_version = info
            except Exception:
                continue

        if latest_version is None:
            return None

        return f"v{str(latest_version)}"

    def releases(self, name: str) -> List[str]:
        """Releases for the package

        Args:
            name (str): Name of the package

        Returns:
            List[str]: A list of releases
        """
        tags = get_repo_tags(self.uri, self.client)

        releases: List[str] = []
        for tag in tags:
            try:
                _, ver = PkgID.parse_tag(tag)
                VersionInfo.parse(ver[1:])
                releases.append(tag)
            except Exception:
                continue

        return releases

    def ids(self) -> List[str]:
        """Ids of all packages

        Returns:
            List[str]: A list of ids
        """
        tags = get_repo_tags(self.uri, self.client)

        ids: List[str] = []
        for tag in tags:
            try:
                PkgID.parse_tag(tag)
                ids.append(tag)
            except Exception:
                continue

        return ids

    def delete(self, name: str, version: str) -> None:
        """Delete a pkg

        Args:
            name (str): Name of the pkg
            version (Optional[str], optional): Versions to delete, use 'all' for all versions. Defaults to None.
        """
        pass

    def clean(self) -> None:
        """Delete all non-releases"""
        pass
