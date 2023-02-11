from __future__ import annotations
from typing import List, Type, Dict, Optional, Union
import os
from pathlib import Path
import logging
import shutil
import yaml
import json
from io import TextIOWrapper

from semver import VersionInfo
import ocifacts as of

from modelos.pkg.repo import PkgRepo, pkgrepo_from_uri
from modelos.pkg.info import PkgInfo
from modelos.pkg.id import PkgID
from modelos.config import Config
from modelos.util.path import list_files
from modelos.virtual.container.registry import get_repo_labels, get_repo_tags, delete_repo_tag
from modelos.pkg.version import hash_all, hash_files, compare_file_hashes, bump_version
from modelos.pkg.util import copy_any, rm_any

StrPath = Union[str, Path]


class Pkg:
    """A package is an versioned filesystem"""

    _root_dir: str
    _id: PkgID
    _repo: PkgRepo
    _version: str

    def __init__(
        self,
        name: str,
        files: Optional[Union[List[str], str]] = None,
        description: Optional[str] = None,
        version: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None,
        tags: Optional[List[str]] = None,
        repo: Optional[Union[PkgRepo, str]] = None,
        config: Optional[Config] = None,
    ) -> None:
        """A versioned filesystem

        Args:
            name (str): Name of the package
            files (Optional[List[str]], optional): Files to add. Defaults to None.
            description (Optional[str], optional): Description of the package. Defaults to None.
            version (Optional[str], optional): Version of the package. Defaults to None.
            labels (Optional[Dict[str, str]], optional): Labels for the package. Defaults to None.
            tags (Optional[List[str]], optional): Tags for the package. Defaults to None.
            repo (Optional[Union[PkgRepo, str]], optional): Repo to use. Defaults to None.
            config (Optional[Config], optional): Config to use to find repo. Defaults to None.
        """
        if isinstance(files, str):
            files = [files]

        self._repo = self._get_repo(repo, config)

        if self.exists(name):
            try:
                self.pull(name, version, repo=repo, config=config)
            except Exception as e:
                raise ValueError(f"could not find pkg {name}:{version}: {e}")

        logging.info("creating new package")
        if description is None:
            raise ValueError("'description' parameter must be set when creating a new package")

        if files is None:
            raise ValueError("'files' parameter must be set when creating a new package")

        pkg = self.new(
            name, description, files, version=version, labels=labels, tags=tags, repo=self._repo, config=config
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

        id = repo.build_id(name, version)

        verdir = cls._pkg_local_dir(id)
        os.makedirs(verdir)

        for fp in files:
            copy_any(fp, id.to_path())

        file_hashes = hash_files(files)

        info = PkgInfo(version, description, labels, tags, file_hashes)

        info.write(id)

        pkg = cls.from_id(id)
        return pkg

    @classmethod
    def from_id(cls, id: PkgID) -> Pkg:
        """Create a package from an ID

        Args:
            id (PkgID): ID to create package from

        Returns:
            Pkg: The package
        """
        pkg = object.__new__(cls)
        pkg._id = id
        out = id.to_path()
        pkg._root_dir = out
        pkg._version = id.version
        pkg._repo = pkgrepo_from_uri(id.repo_uri())

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
            name (str): Name of the pkg
            labels (Optional[Dict[str, str]], optional): Labels to add. Defaults to None.
            tags (Optional[str], optional): Tags to add. Defaults to None
            repo (Optional[Union[PkgRepo, str]], optional): Repo to use. Defaults to None.
            config (Optional[Config], optional): Config to use
        """
        repo = self._get_repo(repo, config)

        info = self.info()
        if not labels:
            labels = {}

        if not tags:
            tags = []

        labels["description"] = info.description
        labels["tags"] = json.dumps(tags)
        of.push(str(self._id), filepath=self._root_dir, labels=labels)
        logging.info(f"pushed {str(self._id)}")

        return None

    @classmethod
    def pull(
        cls: Type[Pkg],
        name: Optional[str] = None,
        version: Optional[str] = None,
        uri: Optional[str] = None,
        repo: Optional[Union[PkgRepo, str]] = None,
        config: Optional[Config] = None,
        force: bool = True,
    ) -> Pkg:
        """Pull a package

        Args:
            name (Optional[str], optional): Name of the pkg. Defaults to None.
            version (Optional[str], optional): Version of the pkg. If not provided will use latest stable.
            uri (Optional[str], optional): URI of the pkg. Defaults to None.
            repo (Optional[Union[PkgRepo, str]], optional): Repo of the package. Defaults to the local config option.
            config (Optional[Config], optional): Config to use
            force (bool, optional): Whether to force pull

        Returns:
            Pkg: A package
        """

        id: PkgID
        if uri is None:
            if name is None:
                raise ValueError("name must be provided if URI is None")
            repo = cls._get_repo(repo, config)
            if version is None:
                version = cls.latest_release(name, repo)
                if version is None:
                    raise ValueError(f"could not find version '{version}' for '{name}'")
                logging.info(f"using version: {version}")
            id = repo.build_id(name, version)
        else:
            id = PkgID.parse(uri)

        out = id.to_path()

        if os.path.exists(out):
            if force:
                shutil.rmtree(out)
            else:
                logging.info("pkg already exists locally")
                return cls.from_id(id)

        of.pull(uri, out)
        logging.info(f"pulled pkg '{uri}' to '{out}'")

        return cls.from_id(id)

    @classmethod
    def latest_release(
        cls, name: str, repo: Optional[Union[PkgRepo, str]] = None, config: Optional[Config] = None
    ) -> Optional[str]:
        """Latest release for the package

        Args:
            name (str): Name of the package
            repo (Optional[Union[PkgRepo, str]], optional): Repo to use. Defaults to None.
            config (Optional[Config], optional): Config to use. Defaults to None.

        Returns:
            Optional[str]: The latest semver release, or None if no version exists
        """
        repo = cls._get_repo(repo, config)
        tags = get_repo_tags(str(repo))

        latest_version: Optional[VersionInfo] = None
        for tag in tags:
            nm, ver = PkgID.parse_tag(tag)
            if nm != name:
                continue
            info = VersionInfo.parse(ver[1:])
            if latest_version is None:
                latest_version = info

            if info > latest_version:
                latest_version = info

        if latest_version is None:
            return None

        return f"v{str(latest_version)}"

    @classmethod
    def exists(cls, name: str, repo: Optional[Union[PkgRepo, str]] = None, config: Optional[Config] = None) -> bool:
        """Check if the package name exists

        Args:
            name (str): Name of the package
            repo (Optional[Union[PkgRepo, str]], optional): Repo to use. Defaults to None.
            config (Optional[Config], optional): Config to use. Defaults to None.

        Returns:
            bool: Whether the package name exists
        """
        repo = cls._get_repo(repo, config)
        tags = get_repo_tags(str(repo))

        for tag in tags:
            nm, _ = PkgID.parse_tag(tag)
            if nm == name:
                return True

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
        delete_repo_tag(
            self._id.repo_uri(),
            self._id.tag(),
        )
        logging.info(f"deleted '{str(self._id)}'")

    def open(self, filepath: str) -> TextIOWrapper:
        """Open a file in a package

        Args:
            filepath (str): The filepath to open

        Returns:
            TextIOWrapper: A TextIOWrapper
        """

        return open(Path(self._root_dir).joinpath(filepath))

    def all_files(self, relative: bool = True) -> List[str]:
        """All files in the package

        Args:
            relative (str): Whether to return relative paths

        Returns:
            List[str]: List of filepaths
        """
        file_set = set()

        for dir_, _, files in os.walk(self.root_dir()):
            for file_name in files:
                if relative:
                    dir_ = os.path.relpath(dir_, self.root_dir())
                rel_file = os.path.join(dir_, file_name)
                file_set.add(rel_file)

        return list(file_set)

    def hash(self) -> str:
        """Calculate the version hash based on the package contents

        Returns:
            str: A SHA256 version hash
        """
        return hash_all(self.all_files(relative=False))

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
        repo = self._get_repo(repo, config)

        current_info = self.info()
        if version is None:
            latest = self.latest_release(self._id.name)
            if not latest:
                latest = "v0.0.1"
            latest_pkg = self.pull(self._id.name, latest, force=True)
            current_hashes = hash_files(self.all_files(relative=False))
            latest_hashes = hash_files(latest_pkg.all_files(relative=True))
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

        old_path = self._id.to_path()
        self._id.version = version
        os.rename(old_path, self._id.to_path())

        current_info.write(self._id)

        logging.info(f"successfully released '{self._id.name}' at version '{version}'")

        return

    def info(self) -> PkgInfo:
        """Get current package info

        Returns:
            PkgInfo: Package info
        """
        meta_path = self._pkg_local_dir(self._id).joinpath("./info.yaml")
        with open(meta_path) as f:
            return yaml.load(f, Loader=yaml.FullLoader)

    @classmethod
    def describe(cls, uri: str) -> None:
        """Describe the URI

        Args:
            uri (str): URI to describe
        """
        id = PkgID.parse(uri)
        labels = get_repo_labels(uri)
        desc = labels.pop("description")
        dct = {"repo": f"{id.host}/{id.repo}", "name": id.name, "description": desc, "labels": labels}
        print(yaml.dump(dct))
        print("---")
        print(list_files(id.to_path()))

    @classmethod
    def _get_repo(cls, repo: Optional[Union[PkgRepo, str]] = None, config: Optional[Config] = None) -> PkgRepo:
        if repo is None:
            if hasattr(cls, "_repo"):
                return cls._repo
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
        pkg_path = id.to_path()
        verdir = Path(pkg_path).joinpath(".pkg")
        return verdir


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
    id = PkgID.parse(uri)
    pkg = Pkg(id.name, files, description, id.version, labels, tags, id.repo)
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


def open_pkg(uri: str, filepath: str) -> TextIOWrapper:
    """Open a filepath in a package URI

    Args:
        uri (str): URI to open file in
        filepath (str): Filepath in the package

    Returns:
        TextIOWrapper: A TextIOWrapper
    """
    pkg = Pkg.pull(uri)
    return pkg.open(filepath)


def describe(uri: str) -> None:
    """Describe the uri

    Args:
        uri (str): URI to describe
    """
    return Pkg.describe(uri)
