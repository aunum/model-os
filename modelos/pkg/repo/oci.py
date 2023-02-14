from typing import List, Optional, Union
import logging
from pathlib import Path

from opencontainers.distribution.reggie import NewClient
from semver import VersionInfo
from docker.auth import resolve_repository_name
import ocifacts as of

from modelos.pkg.repo.remote import RemotePkgRepo
from modelos.pkg.id import PkgID, NVS
from modelos.pkg.info import PkgInfo
from modelos.pkg.scheme import DEFAULT_SCHEME
from modelos.virtual.container.registry import get_oci_client, get_repo_tags, delete_repo_tag, get_img_labels
from modelos.local import pkg_home
from modelos.virtual.container.id import ImageID


class OCIPkgRepo(RemotePkgRepo):
    """OCI based package repository"""

    client: NewClient
    registry: str
    name: str
    _uri: str

    def __init__(self, uri: str) -> None:
        """Connect to an OCI based pkg repo

        Args:
            uri (str): OCI registry URI to connect to e.g. aunum/ml-project or docker.io/aunum/ml-project
        """
        self.client = get_oci_client(uri)
        self._uri = uri

        self.registry, self.name = resolve_repository_name(uri)

    @classmethod
    def parse(cls, uri: str) -> PkgID:
        """Parse a URI into a package ID

        Args:
            uri (str): URI of the pkg

        Returns:
            PkgID: A package ID
        """
        id = ImageID.from_ref(uri)
        nvs = PkgID.parse_nvs(id.tag)

        return PkgID(nvs.name, nvs.version, nvs.scheme, id.host, id.repository)

    @classmethod
    def build_uri(cls, id: PkgID) -> str:
        """Generate a URI for the pkg id

        Args:
            id (PkgID): ID to generate URI for

        Returns:
            str: A URI
        """
        uri = f"{id.repo}:pkg.{id.scheme}.{id.name}.{id.version}"
        if id.host != "docker.io":
            uri = f"{id.host}/{uri}"
        return uri

    def uri(self) -> str:
        """Generate a URI for the repo

        Returns:
            str: A URI
        """
        return self._uri

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
        id = info.id()
        uri = self.build_uri(id)
        of.push(uri, files, labels=info.flat_labels())
        logging.info(f"successfully pushed '{uri}'")

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
        nvs = NVS(name, version, scheme)
        id = self.build_id(nvs)
        uri = self.build_uri(id)
        local = self.local_path(scheme, name, version)
        of.pull(uri, local)
        return

    def info(self, name: str, version: str, scheme: str = DEFAULT_SCHEME) -> PkgInfo:
        """Info for the pkg

        Args:
            name (str): Name of the pkg
            version (str): Version of the pkg
            scheme (str, optional): Scheme of the pkg. Defaults to 'fs'

        Returns:
            PkgInfo: Pkg info
        """
        nvs = NVS(name, version, scheme)
        id = self.build_id(nvs)
        uri = self.build_uri(id)
        labels = get_img_labels(uri)
        return PkgInfo.from_flat(labels)

    def names(self, scheme: str = DEFAULT_SCHEME) -> List[str]:
        """Names of the packages in the repo

        Args:
            scheme (str, optional): Scheme of the pkg. Defaults to 'fs'

        Returns:
            List[str]: Names of packages
        """
        names = set()
        for tag in get_repo_tags(self._uri, self.client):
            try:
                nvs = PkgID.parse_nvs(tag)
                if nvs.scheme == scheme:
                    names.add(nvs.name)
            except Exception:
                continue

        return list(names)

    def versions(self, name: str, scheme: str = DEFAULT_SCHEME) -> List[str]:
        """Versions of a package

        Args:
            name (str): Name of the package
            scheme (str, optional): Scheme of the pkg. Defaults to 'fs'

        Returns:
            List[str]: List of package versions
        """
        versions = []
        for tag in get_repo_tags(self._uri, self.client):
            try:
                nvs = PkgID.parse_nvs(tag)
                if nvs.name != name:
                    continue
                if nvs.scheme != scheme:
                    continue
                versions.append(nvs.version)
            except Exception:
                continue

        return versions

    def latest(self, name: str, scheme: str = DEFAULT_SCHEME) -> Optional[str]:
        """Latest release

        Args:
            name (str): Name of the package
            scheme (str, optional): Scheme of the pkg. Defaults to 'fs'

        Returns:
            Optional[str]: Latest release, or None if no releases
        """
        tags = get_repo_tags(self._uri, self.client)

        latest_version: Optional[VersionInfo] = None
        for tag in tags:
            try:
                nvs = PkgID.parse_nvs(tag)
                if nvs.name != name:
                    continue
                if nvs.scheme != scheme:
                    continue
                info = VersionInfo.parse(nvs.version[1:])
                if latest_version is None:
                    latest_version = info

                if info > latest_version:
                    latest_version = info
            except Exception:
                continue

        if latest_version is None:
            return None

        return f"v{str(latest_version)}"

    def releases(self, name: str, scheme: str = DEFAULT_SCHEME) -> List[str]:
        """Releases for the package

        Args:
            name (str): Name of the package
            scheme (str, optional): Scheme of the pkg. Defaults to 'fs'

        Returns:
            List[str]: A list of releases
        """
        tags = get_repo_tags(self._uri, self.client)

        releases: List[str] = []
        for tag in tags:
            try:
                nvs = PkgID.parse_nvs(tag)
                VersionInfo.parse(nvs.version[1:])
                if name == nvs.name and nvs.scheme == scheme:
                    releases.append(tag)
            except Exception:
                continue

        return releases

    def ids(self) -> List[PkgID]:
        """List of pkgid of all packages

        Returns:
            List[str]: A list of pkgid
        """
        tags = get_repo_tags(self._uri, self.client)

        ids: List[PkgID] = []
        for tag in tags:
            try:
                nvs = PkgID.parse_nvs(tag)
                id = self.build_id(nvs)
                ids.append(id)
            except Exception:
                continue

        return ids

    def delete(self, name: str, version: str, scheme: str = DEFAULT_SCHEME) -> None:
        """Delete a pkg

        Args:
            name (str): Name of the pkg
            version (Optional[str], optional): Versions to delete, use 'all' for all versions. Defaults to None.
            scheme (str, optional): Scheme of the pkg. Defaults to 'fs'
        """
        tags = get_repo_tags(self._uri, self.client)

        for tag in tags:
            try:
                nvs = PkgID.parse_nvs(tag)
                if name == nvs.name and version == nvs.version and nvs.scheme == scheme:
                    delete_repo_tag(self._uri, tag)
                    logging.info(f"deleted repo tag {tag}")
                    return
            except Exception:
                continue

        raise ValueError(f"could not find tag with name '{name}' and version '{version}' to delete")

    def clean(self, name: str, scheme: str = DEFAULT_SCHEME, releases: bool = False) -> None:
        """Delete unused pkgs

        Args:
            name (str): Name of the pkg
            scheme (str, optional): Scheme of the pkg. Defaults to 'fs'
            releases (bool, optional): Whether to delete releases. Defaults to False.
        """

        tags = get_repo_tags(self._uri, self.client)

        for tag in tags:
            try:
                nvs = PkgID.parse_nvs(tag)
                if name != nvs.name:
                    continue
                if scheme != nvs.scheme:
                    continue
                if not releases:
                    VersionInfo.parse(nvs.version)
            except Exception:
                continue
            delete_repo_tag(self._uri, tag)
            logging.info(f"deleted repo tag {tag}")

        return None

    def build_id(self, nvs: NVS) -> PkgID:
        """Build a PkgID for the given name / version

        Args:
            name (str): Name of the package

        Returns:
            PkgID: A PkgID
        """
        return PkgID(
            nvs.name,
            nvs.version,
            nvs.scheme,
            self.registry,
            self.name,
        )

    def local_path(self, name: Optional[str], version: Optional[str] = None, scheme: str = DEFAULT_SCHEME) -> str:
        """Local path of the pkg

        Args:
            name (Optional[str], optional): Name of the pkg
            version (Optional[str], optional): Version of the pkg
            scheme (str, optional): Scheme of the pkg. Defaults to 'fs'

        Returns:
            str: Local path of the pkg
        """
        out_path = Path(pkg_home()).joinpath(self.registry)

        repo_parts = self.name.split("/")
        for part in repo_parts:
            out_path = out_path.joinpath(part)

        out_path = out_path.joinpath(scheme)
        if name:
            out_path = out_path.joinpath(name)
        if version:
            out_path = out_path.joinpath(version)
        out = str(out_path)

        return out

    def __str__(self):
        return self.uri
