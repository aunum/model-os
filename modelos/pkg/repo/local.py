from typing import List, Optional, Union
import os
import shutil
from pathlib import Path
import logging
import yaml

from semver import VersionInfo

from modelos.pkg.id import PkgID, NVS
from modelos.pkg.info import PkgInfo
from modelos.pkg.repo.util import split_uri
from modelos.pkg.scheme import DEFAULT_SCHEME
from modelos.local import pkg_home
from modelos.config import Config
from modelos.pkg.util import copy_any

# In the form .mdl/pkg/<host.repo>/<scheme>/<name>/<version>/.pkg/info.yaml


class LocalPkgRepo:
    """Local package repository"""

    root: str
    repo_uri: str
    repo_dir: str
    host: str
    repo: str

    def __init__(
        self, root: Optional[str] = None, repo_uri: Optional[str] = None, config: Optional[Config] = None
    ) -> None:
        if not root:
            root = pkg_home()
        else:
            if os.path.basename(root) != "pkg":
                root = os.path.join(root, "pkg")

        if not repo_uri:
            if not config:
                config = Config()
                repo = config.pkg_repo
                if repo is None:
                    repo = "local"

                self.repo_uri = repo

        self.root = os.path.normpath(root)
        self.repo_dir = self._repo_dir_name(self.repo_uri)
        self.host, self.repo = split_uri(self.repo_uri)

    def names(self, scheme: str = DEFAULT_SCHEME) -> List[str]:
        """Names of the packages in the repo

        Args:
            scheme (str, optional): Scheme of the pkg. Defaults to 'fs'

        Returns:
            List[str]: Names of packages
        """
        return os.listdir(self._scheme_path(scheme))

    def versions(self, name: str, scheme: str = DEFAULT_SCHEME) -> List[str]:
        """Versions of a package

        Args:
            name (str): Name of the package
            scheme (str, optional): Scheme of the pkg. Defaults to 'fs'

        Returns:
            List[str]: List of package versions
        """
        return os.listdir(self._name_path(name, scheme))

    def find_path(self, id: PkgID) -> str:
        """Find the path for the given ID

        Args:
            id (PkgID): Package ID

        Returns:
            str: A path
        """
        return self._version_path(id.name, id.version, id.scheme)

    def new(
        self,
        info: PkgInfo,
        files: Union[str, List[str]],
    ) -> None:
        """Push a pkg

        Args:
            info (PkgInfo): Package info
            files (List[str]): Files to push
        """
        vp = self._version_path(info.name, info.version, info.scheme)
        os.makedirs(vp, exist_ok=True)
        for fp in files:
            copy_any(fp, vp)
        logging.info(f"copied files to local path {vp}")
        return

    def parse(self, uri: str) -> PkgID:
        """Parse a URI into a package ID

        Args:
            uri (str): URI of the pkg

        Returns:
            PkgID: A package ID
        """
        rel = os.path.relpath(uri, self.root)
        nrel = os.path.normpath(rel)

        parts = Path(nrel).parts

        host = parts[0]
        repo = "/".join(parts[1:2])
        scheme = parts[3]
        name = parts[4]
        version = parts[4]

        return PkgID(
            name,
            version,
            scheme,
            host,
            repo,
        )

    def build_uri(self, id: PkgID) -> str:
        """Generate a URI for the pkg id

        Args:
            id (PkgID): ID to generate URI for

        Returns:
            str: A URI
        """

        return f"pkg://{self.repo_dir}/{id.scheme}/{id.name}/{id.version}"

    def uri(self) -> str:
        """Generate a URI for the repo

        Returns:
            str: A URI
        """
        return f"pkg://{self.repo_dir}"

    def info(self, name: str, version: str, scheme: str = DEFAULT_SCHEME) -> PkgInfo:
        """Info for the pkg

        Args:
            name (str): Name of the pkg
            version (str): Version of the pkg
            scheme (str, optional): Scheme of the pkg. Defaults to 'fs'

        Returns:
            PkgInfo: Pkg info
        """
        ver_path = self._version_path(name, version, scheme)
        path = Path(ver_path).joinpath(".pkg").joinpath("info.yaml")

        with open(path) as f:
            loaded = yaml.load(f.read(), Loader=yaml.FullLoader)
            return PkgInfo(**loaded)

    def latest(self, name: str, scheme: str = DEFAULT_SCHEME) -> Optional[str]:
        """Latest release

        Args:
            name (str): Name of the package
            scheme (str, optional): Scheme of the pkg. Defaults to 'fs'

        Returns:
            Optional[str]: Latest release, or None if no releases
        """
        nm_dir = self._name_path(name, scheme)

        latest_ver: Optional[VersionInfo] = None
        for version in os.listdir(nm_dir):
            try:
                info = VersionInfo.parse(version[1:])
                if latest_ver is None:
                    latest_ver = info
                if info > latest_ver:
                    info = latest_ver
            except Exception:
                continue

        if latest_ver is None:
            return None

        return f"v{str(latest_ver)}"

    def releases(self, name: str, scheme: str = DEFAULT_SCHEME) -> List[str]:
        """Releases for the package

        Args:
            name (str): Name of the package
            scheme (str, optional): Scheme of the pkg. Defaults to 'fs'

        Returns:
            List[str]: A list of releases
        """
        nm_dir = self._name_path(name, scheme)

        versions = []
        for version in os.listdir(nm_dir):
            try:
                info = VersionInfo.parse(version[1:])
                versions.append(f"v{info}")
            except Exception:
                continue

        return versions

    def ids(self, scheme: str = DEFAULT_SCHEME) -> List[PkgID]:
        """Ids of all packages

        Returns:
            List[str]: A list of ids
        """
        pkgs: List[PkgID] = []
        scheme_path = self._scheme_path(scheme)
        for name in os.listdir(scheme_path):
            for version in os.listdir(self._name_path(name, scheme)):
                pkgs.append(PkgID(name, version, scheme, self.host, self.repo))

        return pkgs

    def delete(self, name: str, version: str, scheme: str = DEFAULT_SCHEME) -> None:
        """Delete a pkg

        Args:
            name (str): Name of the pkg
            version (Optional[str], optional): Versions to delete, use 'all' for all versions. Defaults to None.
            scheme (str, optional): Scheme of the pkg. Defaults to 'fs'
        """
        ver_path = self._version_path(name, version, scheme)
        shutil.rmtree(ver_path)
        return

    def clean(self, name: str, scheme: str = DEFAULT_SCHEME, releases: bool = False) -> None:
        """Delete unused pkgs

        Args:
            name (str): Name of the pkg
            scheme (str, optional): Scheme of the pkg. Defaults to 'fs'
            releases (bool, optional): Whether to delete releases. Defaults to False.
        """
        for id in self.ids(scheme):
            if id.name != name:
                continue
            if id.scheme != scheme:
                continue
            if not releases:
                try:
                    VersionInfo.parse(id.version[1:])
                except Exception:
                    continue
            shutil.rmtree(self.find_path(id))
            logging.info(f"deleted id '{str(id)}'")

        return

    def build_id(self, nvs: NVS) -> PkgID:
        """Build a PkgID for the given name / version

        Args:
            name (str): Name of the package

        Returns:
            PkgID: A PkgID
        """
        return PkgID(nvs.name, nvs.version, nvs.scheme, self.host, self.repo)

    def _repo_dir_name(self, repo: str) -> str:
        return repo.replace("/", ".")

    def _repo_path(self) -> str:
        return os.path.join(self.root, self.repo_dir)

    def _scheme_path(self, scheme: str = DEFAULT_SCHEME) -> str:
        return os.path.join(self._repo_path(), scheme)

    def _name_path(self, name: str, scheme: str = DEFAULT_SCHEME) -> str:
        return os.path.join(self._scheme_path(scheme), name)

    def _version_path(self, name: str, version: str, scheme: str = DEFAULT_SCHEME) -> str:
        return os.path.join(self._name_path(name, scheme), version)
