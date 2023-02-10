from __future__ import annotations
from typing import List, Type, Dict, Optional, Union
import os
from pathlib import Path
import logging
import hashlib
import shutil
import yaml
from io import TextIOWrapper

from semver import VersionInfo
import ocifacts as of

from modelos.pkg.repo import PkgRepo
from modelos.pkg.info import PkgInfo
from modelos.env.image.registry import get_img_labels, get_repo_tags
from modelos.pkg.id import PkgID
from modelos.config import Config
from modelos.util.path import list_files


class Pkg:
    """A package is an versioned filesystem"""

    _root_dir: str
    _id: PkgID

    def __init__(
        self,
        name: str,
        files: Optional[List[str]] = None,
        description: Optional[str] = None,
        version: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None,
        repo: Optional[Union[PkgRepo, str]] = None,
        config: Optional[Config] = None,
    ) -> None:
        """A versioned filesystem"""

        repo = self._get_repo(repo, config)

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

        pkg = self.new(name, description, files, version=version, labels=labels, repo=repo, config=config)
        self._id = pkg._id
        self._root_dir = pkg._root_dir

    @classmethod
    def new(
        cls,
        name,
        description: str,
        files: List[str],
        version: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None,
        tags: Optional[List[str]] = None,
        repo: Optional[Union[PkgRepo, str]] = None,
        config: Optional[Config] = None,
    ) -> Pkg:
        if labels is None:
            labels = {}

        if tags is None:
            tags = []

        repo = cls._get_repo(repo, config)

        if version is None:
            hash_full = hashlib.new("sha256")
            for fp in files:
                with open(fp) as f:
                    hash_full.update(f.read().encode())

            version = hash_full.hexdigest()

        id = PkgID(name, version, repo.host, repo.name)

        verdir = cls._pkg_local_dir(id)
        os.makedirs(verdir)

        file_hash = {}

        def hash_file(fp: str) -> str:
            hash = hashlib.new("sha256")
            with open(fp) as f:
                hash.update(f.read().encode())
            return hash.hexdigest()

        for fp in files:
            if os.path.isdir(fp):
                file_set = set()

                for dir_, _, files in os.walk(fp):
                    for file_name in files:
                        rel_dir = os.path.relpath(dir_, fp)
                        rel_file = os.path.join(rel_dir, file_name)
                        file_set.add(rel_file)
                        hash = hash_file(fp)
                        file_hash[rel_file] = hash
                shutil.copytree(fp, id.to_path())

            elif os.path.isfile(fp):
                hash = hash_file(fp)
                name = os.path.basename(fp)
                file_hash[name] = hash

            else:
                logging.warn(f"skipping path '{fp}' as it is not a directory or file")

        info = PkgInfo(version, description, labels, tags, file_hash)
        cls._write_info(id, info)

        return cls.from_id(id)

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

        return pkg

    @classmethod
    def push(
        cls: Type[Pkg],
        filepath: str,
        name: str,
        description: str,
        version: str,
        labels: Optional[Dict[str, str]] = None,
        repo: Optional[Union[PkgRepo, str]] = None,
        config: Optional[Config] = None,
    ) -> Pkg:
        """Push a package

        Args:
            cls (Type[Pkg]): _description_
            filepath (str): Filepath to push
            name (str): Name of the pkg
            description (str): Description of the pkg
            version (str): Version of the pkg.
            labels (Optional[Dict[str, str]], optional): Labels to add. Defaults to None.
            repo (Optional[Union[PkgRepo, str]], optional): Repo to use. Defaults to None.
            config (Optional[Config], optional): Config to use

        Returns:
            Pkg: A package
        """
        repo = cls._get_repo(repo, config)

        id = PkgID(name, version, repo.host, repo.name)
        uri = id.to_uri()
        pkg_path = id.to_path()

        if not labels:
            labels = {}

        labels["description"] = description

        shutil.copytree(filepath, pkg_path)
        of.push(uri, filepath=pkg_path, labels=labels)
        logging.info(f"pushed '{filepath}' to '{uri}'")

        return cls.from_id(id)

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

            id = PkgID(name, version, repo.host, repo.name)
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
        pass

    def cp(self, src: str, dest: str) -> None:
        """Copy the src to the dest, to reference the package use pkg://mydir/file.txt

        Args:
            src (str): Copy from
            dest (str): Copy to
        """
        pass

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

    @classmethod
    def describe(cls, uri: str) -> None:
        """Describe the URI

        Args:
            uri (str): URI to describe
        """
        id = PkgID.parse(uri)
        labels = get_img_labels(uri)
        desc = labels.pop("description")
        dct = {"repo": f"{id.host}/{id.repo}", "name": id.name, "description": desc, "labels": labels}
        print(yaml.dump(dct))
        print("---")
        print(list_files(id.to_path()))

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

        return PkgRepo(repo)

    @classmethod
    def _pkg_local_dir(cls, id: PkgID) -> Path:
        pkg_path = id.to_path()
        verdir = Path(pkg_path).joinpath(".pkg")
        return verdir

    def _read_info(self) -> PkgInfo:
        meta_path = self._pkg_local_dir(self._id).joinpath("./info.yaml")
        with open(meta_path) as f:
            return yaml.load(f, Loader=yaml.FullLoader)

    @classmethod
    def _write_info(cls, id: PkgID, info: PkgInfo) -> None:
        meta_path = cls._pkg_local_dir(id).joinpath("./info.yaml")
        with open(meta_path) as f:
            yam_map = yaml.dump(info)
            f.write(yam_map)


def push(filepath: str, uri: str, description: str, labels: Optional[Dict[str, str]] = None) -> Pkg:
    """Push a package

    Args:
        filepath (str): Local filepath to push
        uri (str): URI to push to
        description (str): Description of the package
        labels(Dict[str, str], optional): Labels for the package

    Returns:
        Pkg: A package
    """
    return Pkg.push(filepath, uri, description, labels)


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


class Stage:
    """A stage is an mutable filesystem used to make new packages"""

    _from_pkg: Pkg
    _stage_pkg: Pkg

    def __init__(self, pkg: Pkg, new_version: str) -> None:
        """Create a mutable filesystem from a stage

        Args:
            pkg (Pkg): Package to create the stage from
            new_version (str): New version of the changes
        """
        self._from_pkg = pkg
        shutil.copytree(
            pkg.root_dir(),
        )

    def open(self, filepath: str) -> TextIOWrapper:
        """Open a file in a package

        Args:
            filepath (str): The filepath to open

        Returns:
            TextIOWrapper: A TextIOWrapper
        """

        return open(Path(self._stage_pkg.root_dir()).joinpath(filepath))

    def release(self, remote: bool = True) -> Pkg:
        """Release the stage as a package

        Args:
            remote (bool, optional): Whether to push remote as well. Defaults to True.

        Returns:
            Pkg: The new package
        """
        pass

    def delete(self) -> None:
        """Delete the stage"""
        shutil.rmtree(self._stage_pkg.root_dir())

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.delete()
