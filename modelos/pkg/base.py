from __future__ import annotations
from typing import List, Type, Dict, Optional, Union, IO, Any, Tuple
import os
from pathlib import Path
import logging
import shutil

from modelos.pkg.repo import RemotePkgRepo, LocalPkgRepo
from modelos.pkg.repo.uri import remote_pkgrepo_from_uri
from modelos.pkg.info import PkgInfo
from modelos.pkg.id import PkgID, NVS
from modelos.pkg.scheme import DEFAULT_SCHEME
from modelos.config import Config
from modelos.pkg.version import hash_all, hash_files, compare_file_hashes
from modelos.pkg.util import copy_any, rm_any
from modelos.util.version import bump_version


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
        dir_path: Optional[str] = None,
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
            dir_path (Optional[str], optional): Directory path with files to add. Defaults to None.
            description (Optional[str], optional): Description of the package. Defaults to None.
            version (Optional[str], optional): Version of the package. Defaults to None.
            scheme (str, optional): Scheme of the package. Defaults to 'fs'.
            labels (Optional[Dict[str, str]], optional): Labels for the package. Defaults to None.
            tags (Optional[List[str]], optional): Tags for the package. Defaults to None.
            remote (Optional[Union[RemotePkgRepo, str]], optional): Remote repo to use. Defaults to None.
            local (Optional[LocalPkgRepo], optional): Local repo to use. Defaults to None.
            config (Optional[Config], optional): Config to use to find repo. Defaults to None.
        """
        self._local, self._remote = self._get_repos(local, remote, config)

        if self.exists(name, version, scheme, self._remote, self._local, config):
            logging.info(f"found pkg '{name}'")
            try:
                pkg = self.pull(name, version, scheme=scheme, remote=self._remote, local=self._local, config=config)
            except Exception as e:
                raise ValueError(f"could not find pkg {name}:{version}: {e}")

        else:
            logging.info("creating new package")
            if description is None:
                raise ValueError("'description' parameter must be set when creating a new package")

            if dir_path is None:
                raise ValueError("'dir_path' parameter must be set when creating a new package")

            pkg = self.new(
                name,
                description,
                dir_path,
                version=version,
                scheme=scheme,
                labels=labels,
                tags=tags,
                remote=self._remote,
                local=self._local,
                config=config,
            )
        self._id = pkg._id
        self._root_dir = pkg._root_dir
        self._version = pkg._version

    @classmethod
    def new(
        cls,
        name: str,
        description: str,
        dir_path: str,
        version: Optional[str] = None,
        scheme: str = DEFAULT_SCHEME,
        labels: Optional[Dict[str, str]] = None,
        tags: Optional[List[str]] = None,
        remote: Optional[Union[RemotePkgRepo, str]] = None,
        local: Optional[LocalPkgRepo] = None,
        config: Optional[Config] = None,
    ) -> Pkg:
        """Create a new package

        Args:
            name (str): Name of the package
            description (str): Description of the package
            dir_path (str): Directory path with files to add to package
            version (Optional[str], optional): Version of the package. Defaults to auto versioning.
            scheme (str, optional): Scheme of the package. Defaults to 'fs'.
            labels (Optional[Dict[str, str]], optional): Labels for the package. Defaults to None.
            tags (Optional[List[str]], optional): Tags for the package. Defaults to None.
            remote (Optional[Union[RemotePkgRepo, str]], optional): Remote repo to use. Defaults to None.
            local (Optional[LocalPkgRepo], optional): Local repo to use. Defaults to None.
            config (Optional[Config], optional): Config for finding the repo. Defaults to None.

        Returns:
            Pkg: A package
        """
        if labels is None:
            labels = {}

        if tags is None:
            tags = []

        local, remote = cls._get_repos(local, remote, config)

        if version is None:
            version = hash_all(dir_path)

        id = remote.build_id(NVS(name, version, scheme))
        file_hashes = hash_files(dir_path)

        info = PkgInfo(name, version, scheme, description, remote.uri(), labels, tags, file_hashes)
        local.new(info, dir_path)

        pkg = cls.from_id(id)
        return pkg

    @classmethod
    def from_id(
        cls,
        id: PkgID,
        remote: Optional[Union[RemotePkgRepo, str]] = None,
        local: Optional[LocalPkgRepo] = None,
        config: Optional[Config] = None,
    ) -> Pkg:
        """Create a package from an ID

        Args:
            id (PkgID): ID to create package from
            remote (Optional[Union[RemotePkgRepo, str]], optional): Remote repo to use. Defaults to None.
            local (Optional[LocalPkgRepo], optional): Local repo to use. Defaults to None.
            config (Optional[Config], optional): Config to use

        Returns:
            Pkg: The package
        """
        local, remote = cls._get_repos(local, remote, config)
        pkg = object.__new__(cls)
        pkg._id = id
        out = local.find_path(id)
        pkg._root_dir = out
        pkg._version = id.version
        pkg._remote = remote_pkgrepo_from_uri(remote.uri())
        pkg._local = local

        return pkg

    def push(
        self,
        labels: Optional[Dict[str, str]] = None,
        tags: Optional[List[str]] = None,
        remote: Optional[Union[RemotePkgRepo, str]] = None,
        local: Optional[LocalPkgRepo] = None,
        config: Optional[Config] = None,
    ) -> None:
        """Push a package

        Args:
            labels (Optional[Dict[str, str]], optional): Labels to add. Defaults to None.
            tags (Optional[str], optional): Tags to add. Defaults to None
            remote (Optional[Union[RemotePkgRepo, str]], optional): Remote repo to use. Defaults to None.
            local (Optional[LocalPkgRepo], optional): Local repo to use. Defaults to None.
            config (Optional[Config], optional): Config to use
        """
        local, remote = self._get_inst_repos(local, remote, config)

        info = self.info()
        if not labels:
            labels = info.labels

        if not tags:
            tags = info.tags

        info = PkgInfo(
            self._id.name,
            self._id.version,
            self._id.scheme,
            info.description,
            remote.uri(),
            labels,
            tags,
            info.file_hash,
        )
        pth = local.find_path(self._id)

        remote.push(info, files=pth)

        return None

    @classmethod
    def pull(
        cls: Type[Pkg],
        name: Optional[str] = None,
        version: Optional[str] = None,
        scheme: str = DEFAULT_SCHEME,
        uri: Optional[str] = None,
        remote: Optional[Union[RemotePkgRepo, str]] = None,
        local: Optional[LocalPkgRepo] = None,
        config: Optional[Config] = None,
        force: bool = True,
    ) -> Pkg:
        """Pull a package

        Args:
            name (Optional[str], optional): Name of the pkg. Defaults to None.
            version (Optional[str], optional): Version of the pkg. If not provided will use latest stable.
            scheme (str, optional): Scheme of the package. Defaults to 'fs'
            uri (Optional[str], optional): URI of the pkg. Defaults to None.
            remote (Optional[Union[RemotePkgRepo, str]], optional): Remote repo to use. Defaults to None.
            local (Optional[LocalPkgRepo], optional): Local repo to use. Defaults to None.
            config (Optional[Config], optional): Config to use
            force (bool, optional): Whether to force pull

        Returns:
            Pkg: A package
        """
        id: PkgID
        local, remote = cls._get_repos(local, remote, config)
        if uri is None:
            if name is None:
                raise ValueError("name must be provided if URI is None")
            if version is None:
                version = cls._latest(name, scheme, remote)
                if version is None:
                    raise ValueError(f"could not find version '{version}' for '{name}'")
                logging.info(f"using version: {version}")
            id = remote.build_id(NVS(name, version, scheme))
        else:
            id = remote.parse(uri)

        out = local.find_path(id)
        if os.path.exists(out):
            if force:
                shutil.rmtree(out)
            else:
                logging.info("pkg already exists locally")
                return cls.from_id(id)

        remote.pull(id.name, id.version, out, id.scheme)
        logging.info(f"pulled pkg '{name}.{version}' to '{out}'")

        return cls.from_id(id)

    @classmethod
    def exists(
        cls,
        name: str,
        version: Optional[str] = None,
        scheme: str = DEFAULT_SCHEME,
        remote: Optional[Union[RemotePkgRepo, str]] = None,
        local: Optional[LocalPkgRepo] = None,
        config: Optional[Config] = None,
    ) -> bool:
        """Check if the package name exists

        Args:
            name (str): Name of the package
            version (Optional[str], optional): Version of the package. Defaults to None.
            scheme (str, optional): Scheme of the package. Defaults to 'fs'
            remote (Optional[Union[RemotePkgRepo, str]], optional): Remote repo to use. Defaults to None.
            local (Optional[LocalPkgRepo], optional): Local repo to use. Defaults to None.
            config (Optional[Config], optional): Config to use. Defaults to None.

        Returns:
            bool: Whether the package name exists
        """
        local, remote = cls._get_repos(local, remote, config)
        ids = remote.ids()

        for id in ids:
            try:
                if id.name == name and id.scheme == scheme:
                    if version:
                        if version == id.version:
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

    def remote(self) -> RemotePkgRepo:
        """Get the remote repo for this package

        Returns:
            RemotePkgRepo: A remote package repo
        """
        return self._remote

    def local(self) -> LocalPkgRepo:
        """Get the local repo for this package

        Returns:
            LocalPkgRepo: A local package repo
        """
        return self._local

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
        self._remote.delete(self._id.name, self._id.version, self._id.scheme)
        self._local.delete(self._id.name, self._id.version, self._id.scheme)
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
        return hash_all(self._root_dir)

    def latest(
        self,
        scheme: str = DEFAULT_SCHEME,
        remote: Optional[Union[RemotePkgRepo, str]] = None,
        config: Optional[Config] = None,
    ) -> Optional[str]:
        """Latest release for the package

        Args:
            remote (Optional[Union[RemotePkgRepo, str]], optional): Remote repo to use. Defaults to None.
            scheme (str, optional): Scheme of the package. Defaults to 'fs'
            config (Optional[Config], optional): Config to use. Defaults to None.

        Returns:
            Optional[str]: The latest semver release, or None if no version exists
        """
        if remote is None:
            if hasattr(self, "_remote"):
                remote = self._remote
        return self._latest(self._id.name, scheme, remote, config)

    def release(
        self,
        version: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None,
        tags: Optional[List[str]] = None,
        remote: Optional[Union[RemotePkgRepo, str]] = None,
        local: Optional[LocalPkgRepo] = None,
        config: Optional[Config] = None,
        push: bool = True,
    ) -> None:
        """Release the package

        Args:
            version (str, optional): Version of the release. Defaults to auto-versioning
            labels (Optional[Dict[str, str]], optional): Labels for the package. Defaults to None.
            tags (Optional[List[str]], optional): Tags for the package. Defaults to None.
            remote (Optional[Union[RemotePkgRepo, str]], optional): Remote repo to use. Defaults to None.
            local (Optional[LocalPkgRepo], optional): Local repo to use. Defaults to None.
            config (Optional[Config], optional): Config for finding the repo. Defaults to None.
            push (bool, optional): Whether to push remote as well. Defaults to True.
        """
        local, remote = self._get_inst_repos(local, remote, config)

        current_info = self.info()
        if version is None:
            latest = self.latest()
            if not latest:
                version = "v0.1.0"
                current_hashes = hash_files(self._root_dir)
                current_info.file_hash = current_hashes
            else:
                uri = remote.build_uri(self._id)
                latest_manifest = self.manifest(uri)
                current_hashes = hash_files(self._root_dir)
                latest_hashes = latest_manifest.file_hash
                version_bump = compare_file_hashes(latest_hashes, current_hashes)
                current_info.file_hash = current_hashes

                version = bump_version(latest, version_bump)
                if version == latest:
                    raise ValueError("The current package is the same as the latest release")

        current_info.version = version

        if labels is not None:
            current_info.labels = labels
        if tags is not None:
            current_info.tags = tags

        old_path = local.find_path(self._id)
        self._id.version = version
        os.rename(old_path, local.find_path(self._id))

        local.write_info(current_info)
        self._root_dir = local.find_path(self._id)

        if push:
            self.push(current_info.labels, current_info.tags, remote, local, config)

        logging.info(f"successfully released '{self._id.name}' at version '{version}'")

        return

    def info(self) -> PkgInfo:
        """Get current package info

        Returns:
            PkgInfo: Package info
        """
        return self._local.info(self._id.name, self._id.version, self._id.scheme)

    def show(self) -> None:
        """Show the package"""
        self._local.show(self._id)

    @classmethod
    def describe(
        cls,
        uri: str,
        remote: Optional[Union[RemotePkgRepo, str]] = None,
        config: Optional[Config] = None,
    ) -> None:
        """Describe the URI

        Args:
            uri (str): URI to describe
            remote (Optional[Union[RemotePkgRepo, str]], optional): Remote repo to use. Defaults to None.
            config (Optional[Config], optional): Config to use. Defaults to None.
        """
        _, remote = cls._get_repos(remote=remote, config=config)
        id = remote.parse(uri)
        remote.show(id)
        return

    @classmethod
    def manifest(
        cls,
        uri: str,
        remote: Optional[Union[RemotePkgRepo, str]] = None,
        config: Optional[Config] = None,
    ) -> PkgInfo:
        """Get info on remote package

        Args:
            uri (str): URI to get manifest for
            remote (Optional[Union[RemotePkgRepo, str]], optional): Remote repo to use. Defaults to None.
            config (Optional[Config], optional): Config to use. Defaults to None.

        Returns:
            PkgInfo: Package info
        """
        _, remote = cls._get_repos(remote=remote, config=config)
        id = remote.parse(uri)
        return remote.info(id.name, id.version, id.scheme)

    def clean(
        self,
        releases: bool = False,
        remote: Optional[Union[RemotePkgRepo, str]] = None,
        local: Optional[LocalPkgRepo] = None,
        include_remote: bool = True,
        config: Optional[Config] = None,
    ) -> None:
        """Clean the packages

        Args:
            releases (bool, optional): Clean releases as well. Defaults to False.
            remote (Optional[Union[RemotePkgRepo, str]], optional): Remote repo to use. Defaults to None.
            local (Optional[LocalPkgRepo], optional): Local repo to use. Defaults to None.
            include_remote (bool, optional): Whether to clean remote packages. Defaults to True.
            config (Optional[Config], optional) Config to use. Defaults to None.
        """
        self._clean(self._id.name, self._id.scheme, releases, remote, local, include_remote, config)

    @classmethod
    def _clean(
        cls,
        name: str,
        scheme: str = DEFAULT_SCHEME,
        releases: bool = False,
        remote: Optional[Union[RemotePkgRepo, str]] = None,
        local: Optional[LocalPkgRepo] = None,
        include_remote: bool = True,
        config: Optional[Config] = None,
    ) -> None:
        """Clean the packages

        Args:
            repo (PkgRepo): The package repo
            name (str): Name of the package
            scheme (str): Scheme of the package
            releases (bool, optional): Clean releases as well. Defaults to False.
            remote (Optional[Union[RemotePkgRepo, str]], optional): Remote repo to use. Defaults to None.
            local (Optional[LocalPkgRepo], optional): Local repo to use. Defaults to None.
            include_remote (bool, optional): Whether to clean remote packages. Defaults to True.
            config (Optional[Config], optional) Config to use. Defaults to None.
        """
        local, remote = cls._get_repos(local, remote, config)
        local.clean(name, scheme, releases)
        if include_remote:
            remote.clean(name, scheme, releases)

    def _get_inst_repos(
        self,
        local: Optional[LocalPkgRepo] = None,
        remote: Optional[Union[RemotePkgRepo, str]] = None,
        config: Optional[Config] = None,
    ) -> Tuple[LocalPkgRepo, RemotePkgRepo]:
        if remote is None:
            if hasattr(self, "_remote"):
                remote = self._remote

        if local is None:
            if hasattr(self, "_local"):
                local = self._local

        return self._get_repos(local, remote, config)

    @classmethod
    def _get_repos(
        cls,
        local: Optional[LocalPkgRepo] = None,
        remote: Optional[Union[RemotePkgRepo, str]] = None,
        config: Optional[Config] = None,
    ) -> Tuple[LocalPkgRepo, RemotePkgRepo]:
        if remote is None:
            if config is None:
                config = Config()

            remote = config.pkg_repo
            if remote is None:
                raise ValueError(
                    "could not find a configured repo url, must supply the `repo` parameter, "
                    + "or set either $MDL_PKG_REPO,"
                    + " add `tool.modelos.img_repo` to pyproject.toml, or add `pkg_repo` to mdl.yaml"
                )
        if isinstance(remote, str):
            remote = remote_pkgrepo_from_uri(remote)

        if local is None:
            local = LocalPkgRepo()

        return local, remote

    @classmethod
    def _latest(
        cls,
        name: str,
        scheme: str = DEFAULT_SCHEME,
        remote: Optional[Union[RemotePkgRepo, str]] = None,
        config: Optional[Config] = None,
    ) -> Optional[str]:
        _, remote = cls._get_repos(remote=remote, config=config)
        return remote.latest(name, scheme)


def push(
    dir_path: str,
    uri: str,
    description: str,
    labels: Optional[Dict[str, str]] = None,
    tags: Optional[List[str]] = None,
) -> Pkg:
    """Push a package

    Args:
        dir_path (str): Local directory filepath to push
        uri (str): URI to push to
        description (str): Description of the package
        labels(Dict[str, str], optional): Labels for the package
        tags (Optional[List[str]], optional): Tags for the package. Defaults to None.

    Returns:
        Pkg: A package
    """
    repo = remote_pkgrepo_from_uri(uri)
    id = repo.parse(uri)
    pkg = Pkg(id.name, dir_path, description, id.version, id.scheme, labels, tags, id.repo)
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
    name: str,
    scheme: str = DEFAULT_SCHEME,
    remote: Optional[Union[RemotePkgRepo, str]] = None,
    config: Optional[Config] = None,
) -> Optional[str]:
    """Latest release for the package

    Args:
        name (str): Name of the package
        scheme (str, optional): Scheme of the package. Defaults to 'fs'
        remote (Optional[Union[RemotePkgRepo, str]], optional): Remote repo to use. Defaults to None.
        config (Optional[Config], optional): Config to use. Defaults to None.

    Returns:
        Optional[str]: The latest semver release, or None if no version exists
    """
    return Pkg._latest(name, scheme, remote, config)


def clean(
    uri: str, name: str, scheme: str = DEFAULT_SCHEME, releases: bool = False, include_remote: bool = True
) -> None:
    """Clean the packages

    Args:
        uri (str): URI of the repo
        name (str): Name of the package
        scheme (str, optional): Scheme of the package. Defaults to 'fs'
        releases (bool, optional): Clean releases as well. Defaults to False.
        include_remote (bool, optional): Whether to clean remote packages. Defaults to True.
    """
    repo = remote_pkgrepo_from_uri(uri)
    Pkg._clean(name, scheme, releases, remote=repo, include_remote=include_remote)
