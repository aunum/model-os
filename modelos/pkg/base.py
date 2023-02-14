from __future__ import annotations
from typing import List, Type, Dict, Optional, Union, IO, Any
import os
from pathlib import Path
import logging
import shutil
import yaml
import json

from semver import VersionInfo

from modelos.pkg.repo import RemotePkgRepo, LocalPkgRepo, remote_pkgrepo_from_uri
from modelos.pkg.info import PkgInfo
from modelos.pkg.id import PkgID, NVS
from modelos.pkg.scheme import DEFAULT_SCHEME
from modelos.config import Config
from modelos.util.path import list_files
from modelos.pkg.version import hash_all, hash_files, compare_file_hashes, bump_version
from modelos.pkg.util import copy_any, rm_any


class Pkg:
    """A package is a versioned filesystem"""

    _root_dir: str
    _id: PkgID
    _remote: RemotePkgRepo
    _local: LocalPkgRepo
    _version: str

    def __init__(
        self,
        name: str,
        files: Optional[Union[List[str], str]] = None,
        description: Optional[str] = None,
        version: Optional[str] = None,
        scheme: str = DEFAULT_SCHEME,
        labels: Optional[Dict[str, str]] = None,
        tags: Optional[List[str]] = None,
        remote: Optional[Union[RemotePkgRepo, str]] = None,
        local: Optional[LocalPkgRepo] = None,
        config: Optional[Config] = None,
    ) -> None:
        """A versioned filesystem

        Args:
            name (str): Name of the package
            files (Optional[List[str]], optional): Files to add. Defaults to None.
            description (Optional[str], optional): Description of the package. Defaults to None.
            version (Optional[str], optional): Version of the package. Defaults to None.
            scheme (str, optional): Scheme of the package. Defaults to 'fs'.
            labels (Optional[Dict[str, str]], optional): Labels for the package. Defaults to None.
            tags (Optional[List[str]], optional): Tags for the package. Defaults to None.
            remote (Optional[Union[RemotePkgRepo, str]], optional): Remote repo to use. Defaults to None.
            local (Optional[Union[LocalPkgRepo, str]], optional): Local repo to use. Defaults to None.
            config (Optional[Config], optional): Config to use to find repo. Defaults to None.
        """
        if isinstance(files, str):
            files = [files]

        self._repo = self._get_repo(repo, config)

        if self.exists(name, version, scheme, self._repo):
            logging.info(f"found pkg '{name}'")
            try:
                pkg = self.pull(name, version, repo=self._repo)
            except Exception as e:
                raise ValueError(f"could not find pkg {name}:{version}: {e}")

        else:
            logging.info("creating new package")
            if description is None:
                raise ValueError("'description' parameter must be set when creating a new package")

            if files is None:
                raise ValueError("'files' parameter must be set when creating a new package")

            pkg = self.new(
                name, description, files, version=version, labels=labels, tags=tags, repo=self._repo, scheme=scheme
            )
        self._id = pkg._id
        self._root_dir = pkg._root_dir
        self._version = pkg._version

    @classmethod
    def new(
        cls,
        name: str,
        description: str,
        files: Union[List[str], str],
        version: Optional[str] = None,
        scheme: str = DEFAULT_SCHEME,
        labels: Optional[Dict[str, str]] = None,
        tags: Optional[List[str]] = None,
        repo: Optional[Union[PkgRepo, str]] = None,
        config: Optional[Config] = None,
    ) -> Pkg:
        """Create a new package

        Args:
            name (str): Name of the package
            description (str): Description of the package
            files (List[str]): Files to add to the package
            version (Optional[str], optional): Version of the package. Defaults to auto versioning.
            scheme (str, optional): Scheme of the package. Defaults to 'fs'.
            labels (Optional[Dict[str, str]], optional): Labels for the package. Defaults to None.
            tags (Optional[List[str]], optional): Tags for the package. Defaults to None.
            repo (Optional[Union[PkgRepo, str]], optional): Repo for the package. Defaults to None.
            config (Optional[Config], optional): Config for finding the repo. Defaults to None.

        Returns:
            Pkg: A package
        """
        if isinstance(files, str):
            files = [files]
        if labels is None:
            labels = {}

        if tags is None:
            tags = []

        repo = cls._get_repo(repo, config)

        if version is None:
            version = hash_all(files)

        id = repo.build_id(NVS(name, version, scheme))

        verdir = cls._pkg_local_dir(id)
        os.makedirs(verdir, exist_ok=True)

        for fp in files:
            copy_any(fp, id.local_path())

        file_hashes = hash_files(files)

        info = PkgInfo(name, version, scheme, description, str(repo), labels, tags, file_hashes)

        info.write_local(id)

        pkg = cls.from_id(id)
        return pkg

    @classmethod
    def from_id(
        cls,
        id: PkgID,
        repo: Optional[Union[PkgRepo, str]] = None,
        config: Optional[Config] = None,
    ) -> Pkg:
        """Create a package from an ID

        Args:
            id (PkgID): ID to create package from
            repo (Optional[Union[PkgRepo, str]], optional): Repo to use. Defaults to None.
            config (Optional[Config], optional): Config to use

        Returns:
            Pkg: The package
        """
        repo = cls._get_repo(repo, config)
        pkg = object.__new__(cls)
        pkg._id = id
        out = id.local_path()
        pkg._root_dir = out
        pkg._version = id.version
        pkg._repo = pkgrepo_from_uri(repo.uri())

        return pkg

    def push(
        self,
        labels: Optional[Dict[str, str]] = None,
        tags: Optional[List[str]] = None,
        repo: Optional[Union[PkgRepo, str]] = None,
        config: Optional[Config] = None,
    ) -> None:
        """Push a package

        Args:
            labels (Optional[Dict[str, str]], optional): Labels to add. Defaults to None.
            tags (Optional[str], optional): Tags to add. Defaults to None
            repo (Optional[Union[PkgRepo, str]], optional): Repo to use. Defaults to None.
            config (Optional[Config], optional): Config to use
        """
        if repo is None:
            if hasattr(self, "_repo"):
                repo = self._repo
        repo = self._get_repo(repo, config)

        info = self.info()
        if not labels:
            labels = info.labels

        if not tags:
            tags = info.tags

        info = PkgInfo(
            self._id.name, self._id.version, self._id.scheme, info.description, str(repo), labels, tags, info.file_hash
        )

        repo.push(info, files=self._root_dir)

        return None

    @classmethod
    def pull(
        cls: Type[Pkg],
        name: Optional[str] = None,
        version: Optional[str] = None,
        scheme: str = DEFAULT_SCHEME,
        uri: Optional[str] = None,
        repo: Optional[Union[PkgRepo, str]] = None,
        config: Optional[Config] = None,
        force: bool = True,
    ) -> Pkg:
        """Pull a package

        Args:
            name (Optional[str], optional): Name of the pkg. Defaults to None.
            version (Optional[str], optional): Version of the pkg. If not provided will use latest stable.
            scheme (str, optional): Scheme of the package. Defaults to 'fs'
            uri (Optional[str], optional): URI of the pkg. Defaults to None.
            repo (Optional[Union[PkgRepo, str]], optional): Repo of the package. Defaults to the local config option.
            config (Optional[Config], optional): Config to use
            force (bool, optional): Whether to force pull

        Returns:
            Pkg: A package
        """
        id: PkgID
        repo = cls._get_repo(repo, config)
        if uri is None:
            if name is None:
                raise ValueError("name must be provided if URI is None")
            if version is None:
                version = cls._latest(name, scheme, repo)
                if version is None:
                    raise ValueError(f"could not find version '{version}' for '{name}'")
                logging.info(f"using version: {version}")
            id = repo.build_id(NVS(name, version, scheme))
        else:
            id = repo.parse(uri)

        out = id.local_path()

        if os.path.exists(out):
            if force:
                shutil.rmtree(out)
            else:
                logging.info("pkg already exists locally")
                return cls.from_id(id)

        repo.pull(id.name, id.version)
        logging.info(f"pulled pkg '{name}.{version}' to '{out}'")

        return cls.from_id(id)

    @classmethod
    def exists(
        cls,
        name: str,
        version: Optional[str] = None,
        scheme: str = DEFAULT_SCHEME,
        repo: Optional[Union[PkgRepo, str]] = None,
        config: Optional[Config] = None,
    ) -> bool:
        """Check if the package name exists

        Args:
            name (str): Name of the package
            version (Optional[str], optional): Version of the package. Defaults to None.
            scheme (str, optional): Scheme of the package. Defaults to 'fs'
            repo (Optional[Union[PkgRepo, str]], optional): Repo to use. Defaults to None.
            config (Optional[Config], optional): Config to use. Defaults to None.

        Returns:
            bool: Whether the package name exists
        """
        repo = cls._get_repo(repo, config)
        ids = repo.ids()

        for id in ids:
            try:
                nvs = PkgID.parse_nvs(id)
                if nvs.name == name and nvs.scheme == scheme:
                    if version:
                        if version == nvs.version:
                            return True
                    else:
                        return True
            except Exception:
                continue

        return False

    def ls(self, dir: str = "./") -> List[str]:
        """List the package contents

        Args:
            dir (str): Directory to list within the package

        Returns:
            List[str]: List of contents
        """
        return os.listdir(Path(self._root_dir).joinpath(dir))

    def add(self, filepath: str) -> None:
        """Add a filepath to the package

        Args:
            filepath (str): Filepath to add
        """
        copy_any(filepath, self._root_dir)

    def repo(self) -> PkgRepo:
        """Get the repo for this package

        Returns:
            PkgRepo: A package repo
        """
        return self._repo

    def read(self, filepath: str) -> str:
        """Read a file from the package

        Args:
            filepath (str): Filepath to read

        Returns:
            str: Contents
        """
        with open(Path(self._root_dir).joinpath(filepath), "r") as f:
            return f.read()

    def readlines(self, filepath: str) -> List[str]:
        """Read a file from the package as lines

        Args:
            filepath (str): Filepath to read

        Returns:
            List[str]: File lines
        """
        with open(Path(self._root_dir).joinpath(filepath), "r") as f:
            return f.readlines()

    def cp(self, src: str, dest: str) -> None:
        """Copy the src to the dest, to reference the package use pkg://mydir/file.txt

        Args:
            src (str): Copy from
            dest (str): Copy to
        """
        if src.startswith("pkg://"):
            src = src.lstrip("pkg://")
            src = str(Path(self._root_dir).joinpath(src))

        if dest.startswith("pkg://"):
            dest = src.lstrip("pkg://")
            dest = str(Path(self._root_dir).joinpath(dest))

        copy_any(src, dest)

    def rm(self, filepath: str) -> None:
        """Remove the relative filepath from the package

        Args:
            filepath (str): The relative filepath
        """
        rm_any(str(Path(self._root_dir).joinpath(filepath)))

    def root_dir(self) -> str:
        """Root dir of the package

        Returns:
            str: Filepath
        """
        return self._root_dir

    def id(self) -> PkgID:
        """ID of the package

        Returns:
            PkgID: ID
        """
        return self._id

    def delete(self) -> None:
        """Delete the package

        Returns:
            PkgID: ID
        """
        self._repo.delete(self._id.name, self._id.version)
        shutil.rmtree(self._id.local_path())
        logging.info(f"deleted '{str(self._id)}'")

    def open(self, filepath: str, mode: str = "r") -> IO[Any]:
        """Open a file in a package

        Args:
            filepath (str): The filepath to open
            mode (str): Mode to open file in

        Returns:
            IO[Any]: An IO
        """

        return open(Path(self._root_dir).joinpath(filepath), mode)

    def all_files(self, relative: bool = True) -> List[str]:
        """All files in the package

        Args:
            relative (str): Whether to return relative paths

        Returns:
            List[str]: List of filepaths
        """
        file_set = set()

        for dir_, _, files in os.walk(self.root_dir()):
            if os.path.basename(os.path.normpath(dir_)) == ".mdl":
                continue
            for file_name in files:
                if relative:
                    dir_ = os.path.relpath(dir_, self.root_dir())
                rel_file = os.path.join(dir_, file_name)
                rel_file = os.path.normpath(rel_file)
                file_set.add(rel_file)

        return list(file_set)

    def hash(self) -> str:
        """Calculate the version hash based on the package contents

        Returns:
            str: A SHA256 version hash
        """
        return hash_all(self.all_files(relative=False))

    def latest(
        self, scheme: str = DEFAULT_SCHEME, repo: Optional[Union[PkgRepo, str]] = None, config: Optional[Config] = None
    ) -> Optional[str]:
        """Latest release for the package

        Args:
            repo (Optional[Union[PkgRepo, str]], optional): Repo to use. Defaults to None.
            scheme (str, optional): Scheme of the package. Defaults to 'fs'
            config (Optional[Config], optional): Config to use. Defaults to None.

        Returns:
            Optional[str]: The latest semver release, or None if no version exists
        """
        if repo is None:
            if hasattr(self, "_repo"):
                repo = self._repo
        return self._latest(self._id.name, scheme, repo, config)

    def release(
        self,
        version: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None,
        tags: Optional[List[str]] = None,
        repo: Optional[Union[PkgRepo, str]] = None,
        config: Optional[Config] = None,
        remote: bool = True,
    ) -> None:
        """Release the package

        Args:
            version (str, optional): Version of the release. Defaults to auto-versioning
            labels (Optional[Dict[str, str]], optional): Labels for the package. Defaults to None.
            tags (Optional[List[str]], optional): Tags for the package. Defaults to None.
            repo (Optional[Union[PkgRepo, str]], optional): Repo for the package. Defaults to None.
            config (Optional[Config], optional): Config for finding the repo. Defaults to None.
            remote (bool, optional): Whether to push remote as well. Defaults to True.
        """
        if repo is None:
            if hasattr(self, "_repo"):
                repo = self._repo
        repo = self._get_repo(repo, config)

        current_info = self.info()
        if version is None:
            latest = self.latest()
            print("got latest: ", latest)
            if not latest:
                version = "v0.1.0"
                current_hashes = hash_files(self.all_files(relative=False))
                current_info.file_hash = current_hashes
            else:
                uri = repo.build_uri(self._id)
                latest_manifest = self.manifest(uri)
                print("latest manifest: ", latest_manifest.__dict__)
                current_hashes = hash_files(self.all_files(relative=False))
                latest_hashes = latest_manifest.file_hash
                version_bump = compare_file_hashes(current_hashes, latest_hashes)
                current_info.file_hash = current_hashes

                version = bump_version(latest, version_bump)
                if version == latest:
                    raise ValueError("The current package is the same as the latest release")

        current_info.version = version

        if labels is not None:
            current_info.labels = labels
        if tags is not None:
            current_info.tags = tags

        old_path = self._id.local_path()
        self._id.version = version
        os.rename(old_path, self._id.local_path())

        current_info.write_local(self._id)
        self._root_dir = self._id.local_path()

        if remote:
            self.push(current_info.labels, current_info.tags, repo, config)

        logging.info(f"successfully released '{self._id.name}' at version '{version}'")

        return

    def info(self) -> PkgInfo:
        """Get current package info

        Returns:
            PkgInfo: Package info
        """
        meta_path = self._pkg_local_dir(self._id).joinpath("./info.yaml")
        with open(meta_path, "r") as f:
            loaded = yaml.load(f, Loader=yaml.FullLoader)
            if "tags" in loaded:
                loaded_tags = loaded["tags"]
                if isinstance(loaded_tags, str):
                    loaded["tags"] = json.loads(loaded["tags"])
            return PkgInfo(**loaded)

    def show(self) -> None:
        """Show the package"""

        info = self.info().__dict__
        info.pop("file_hash")

        print("---")
        print(yaml.dump(info))
        print("contents: >")
        list_files(self._id.local_path())
        print("")

    @classmethod
    def describe(
        cls,
        uri: str,
        repo: Optional[Union[PkgRepo, str]] = None,
        config: Optional[Config] = None,
    ) -> None:
        """Describe the URI

        Args:
            uri (str): URI to describe
        """
        info = cls.manifest(uri)
        info.show()
        return

    @classmethod
    def manifest(
        cls,
        uri: str,
        repo: Optional[Union[PkgRepo, str]] = None,
        config: Optional[Config] = None,
    ) -> PkgInfo:
        """Get info on remote package

        Args:
            uri (str): URI to get a manifest for
        """
        repo = cls._get_repo(repo, config)
        id = repo.parse(uri)
        return repo.info(id.name, id.version)

    def clean(self, releases: bool = False, remote: bool = True) -> None:
        """Clean the packages

        Args:
            releases (bool, optional): Clean releases as well. Defaults to False.
            remote (bool, optional): Whether to clean remote packages. Defaults to True.
        """
        self._clean(self._repo, self._id.name, self._id.scheme, releases, remote)

    @classmethod
    def _clean(
        cls, repo: PkgRepo, name: str, scheme: str = DEFAULT_SCHEME, releases: bool = False, remote: bool = True
    ) -> None:
        """Clean the packages

        Args:
            repo (PkgRepo): The package repo
            name (str): Name of the package
            scheme (str): Scheme of the package
            releases (bool, optional): Clean releases as well. Defaults to False.
            remote (bool, optional): Whether to clean remote packages. Defaults to True.
        """
        local_pth = repo.local_path(name)
        for nm in os.listdir(local_pth):
            dir_pth = os.path.join(local_pth, nm)
            if os.path.isdir(dir_pth):
                is_release = False
                try:
                    VersionInfo.parse(nm[1:])
                    is_release = True
                except Exception:
                    pass
                if not releases and is_release:
                    continue
                shutil.rmtree(dir_pth)
                logging.info(f"deleted local pkg '{dir_pth}'")

        if remote:
            repo.clean(name, scheme, releases)

    @classmethod
    def _get_repo(cls, repo: Optional[Union[PkgRepo, str]] = None, config: Optional[Config] = None) -> PkgRepo:
        if repo is None:
            if config is None:
                config = Config()

            repo = config.image_repo
            if repo is None:
                raise ValueError(
                    "could not find a configured repo url, must supply the `repo` parameter, "
                    + "or set either $MDL_IMAGE_REPO,"
                    + " add `tool.modelos.image_repo` to pyproject.toml, or add `image_repo` to mdl.yaml"
                )
        if isinstance(repo, PkgRepo):
            return repo

        return pkgrepo_from_uri(repo)

    @classmethod
    def _pkg_local_dir(cls, id: PkgID) -> Path:
        pkg_path = id.local_path()
        verdir = Path(pkg_path).joinpath(".mdl")
        return verdir

    @classmethod
    def _latest(
        cls,
        name: str,
        scheme: str = DEFAULT_SCHEME,
        repo: Optional[Union[PkgRepo, str]] = None,
        config: Optional[Config] = None,
    ) -> Optional[str]:
        repo = Pkg._get_repo(repo, config)
        ids = repo.ids()
        latest_version: Optional[VersionInfo] = None
        for id in ids:
            try:
                nvs = PkgID.parse_nvs(id)
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


def push(
    files: Union[List[str], str],
    uri: str,
    description: str,
    labels: Optional[Dict[str, str]] = None,
    tags: Optional[List[str]] = None,
) -> Pkg:
    """Push a package

    Args:
        files (str): Local filepath(s) to push
        uri (str): URI to push to
        description (str): Description of the package
        labels(Dict[str, str], optional): Labels for the package
        tags (Optional[List[str]], optional): Tags for the package. Defaults to None.

    Returns:
        Pkg: A package
    """
    repo = pkgrepo_from_uri(uri)
    id = repo.parse(uri)
    pkg = Pkg(id.name, files, description, id.version, id.scheme, labels, tags, id.repo)
    pkg.push()
    return pkg


def pull(uri: str) -> Pkg:
    """Pull a package

    Args:
        uri (str): URI to pull

    Returns:
        Pkg: A package
    """
    return Pkg.pull(uri)


def ls(uri: str, dir: str = "./") -> List[str]:
    """List files in a package

    Args:
        uri (str): URI to package
        dir (str, optional): Directory to list. Defaults to "./".

    Returns:
        List[str]: List of contents
    """
    pkg = Pkg.pull(uri)
    return pkg.ls(dir)


def open_pkg(uri: str, filepath: str, mode: str) -> IO[Any]:
    """Open a filepath in a package URI

    Args:
        uri (str): URI to open file in
        filepath (str): Filepath in the package
        mode (str): Mode to open the package in

    Returns:
        IO[Any]: An IO
    """
    pkg = Pkg.pull(uri)
    return pkg.open(filepath, mode)


def describe(uri: str) -> None:
    """Describe the uri

    Args:
        uri (str): URI to describe
    """
    return Pkg.describe(uri)


def latest(
    name: str, scheme: str = DEFAULT_SCHEME, repo: Optional[Union[PkgRepo, str]] = None, config: Optional[Config] = None
) -> Optional[str]:
    """Latest release for the package

    Args:
        name (str): Name of the package
        scheme (str, optional): Scheme of the package. Defaults to 'fs'
        repo (Optional[Union[PkgRepo, str]], optional): Repo to use. Defaults to None.
        config (Optional[Config], optional): Config to use. Defaults to None.

    Returns:
        Optional[str]: The latest semver release, or None if no version exists
    """
    return Pkg._latest(name, scheme, repo, config)


def clean(uri: str, name: str, scheme: str = DEFAULT_SCHEME, releases: bool = False, remote: bool = True) -> None:
    """Clean the packages

    Args:
        uri (str): URI of the repo
        name (str): Name of the package
        scheme (str, optional): Scheme of the package. Defaults to 'fs'
        releases (bool, optional): Clean releases as well. Defaults to False.
        remote (bool, optional): Whether to clean remote packages. Defaults to True.
    """
    repo = pkgrepo_from_uri(uri)
    Pkg._clean(repo, name, scheme, releases, remote)
