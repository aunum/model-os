"""Config for ModelOS"""

from typing import Optional, Any
import os
from enum import Enum
from typing import Dict, Protocol

from modelos.util.rootpath import is_pyproject, has_mdl_repo, load_mdl_repo, load_pyproject


class Opts(Protocol):
    # as already noted in comments, checking for this attribute is currently
    # the most reliable way to ascertain that something is a dataclass
    __dataclass_fields__: Dict


class RemoteSyncStrategy(str, Enum):
    """Strategy by which code source is synced remotely"""

    IMAGE = "image"
    """Create a new image to copy file changes"""

    CONTAINER = "container"
    """Copy the file changes directly into a running container"""


class Config:
    """General configuration for ModelOS"""

    image_repo: Optional[str]
    pkg_repo: Optional[str]
    docker_socket: str
    kube_namespace: str
    remote_sync_strategy: RemoteSyncStrategy

    _pyproject_dict: Optional[Dict[str, Any]] = None
    _mdl_repo: Optional[Dict[str, Any]] = None

    def __init__(
        self,
        image_repo: Optional[str] = None,
        pkg_repo: Optional[str] = None,
        docker_socket: Optional[str] = None,
        kube_namespace: Optional[str] = None,
        remote_sync_strategy: Optional[RemoteSyncStrategy] = None,
    ):
        if is_pyproject():
            self._pyproject_dict = load_pyproject()

        if has_mdl_repo():
            self._mdl_repo = load_mdl_repo()

        if image_repo is None:
            self.image_repo = self.get_image_repo()
        else:
            self.image_repo = image_repo
        if self.image_repo is None or self.image_repo == "":
            raise ValueError(
                "could not find a configured registry url, please set either $MDL_IMAGE_REPO,"
                + " add `tool.modelos.image_repo` to pyproject.toml, or add `image_repo` to mdl.yaml"
            )

        if pkg_repo is None:
            self.pkg_repo = self.get_pkg_repo()
        else:
            self.pkg_repo = pkg_repo
        if self.pkg_repo is None or self.pkg_repo == "":
            self.pkg_repo = self.image_repo

        if docker_socket is None:
            self.docker_socket = self.get_docker_socket()
        else:
            self.docker_socket = docker_socket
        if self.docker_socket == "":
            if os.name == "nt":
                raise ValueError("problem loading docker socket: windows not yet supported")

            self.docker_socket = "unix://var/run/docker.sock"

        if kube_namespace is None:
            self.kube_namespace = self.get_kube_namespace()
        else:
            self.kube_namespace = kube_namespace
        if self.kube_namespace == "":
            self.kube_namespace = "mdl"

        if remote_sync_strategy is None:
            self.remote_sync_strategy = self.get_remote_sync_strategy()
        else:
            self.remote_sync_strategy = remote_sync_strategy

    def get_image_repo(self) -> Optional[str]:
        env = os.getenv("MDL_IMAGE_REPO")
        if env is not None:
            return env

        if self._pyproject_dict is not None:
            try:
                return self._pyproject_dict["tool"]["modelos"]["image_repo"]
            except KeyError:
                pass

        if self._mdl_repo is not None:
            if "image_repo" in self._mdl_repo:
                return self._mdl_repo["image_repo"]

        return None

    def get_pkg_repo(self) -> Optional[str]:
        env = os.getenv("MDL_PKG_REPO")
        if env is not None:
            return env

        if self._pyproject_dict is not None:
            try:
                return self._pyproject_dict["tool"]["modelos"]["pkg_repo"]
            except KeyError:
                pass

        if self._mdl_repo is not None:
            if "pkg_repo" in self._mdl_repo:
                return self._mdl_repo["pkg_repo"]

        return None

    def get_docker_socket(self) -> str:
        env = os.getenv("MDL_DOCKER_SOCKET")
        if env is not None:
            return env

        if self._pyproject_dict is not None:
            try:
                return self._pyproject_dict["tool"]["modelos"]["docker_socket"]
            except KeyError:
                pass

        if self._mdl_repo is not None:
            if "docker_socket" in self._mdl_repo:
                return self._mdl_repo["docker_socket"]

        return ""

    def get_kube_namespace(self) -> str:
        env = os.getenv("MDL_KUBE_NAMESPACE")
        if env is not None:
            return env

        if self._pyproject_dict is not None:
            try:
                return self._pyproject_dict["tool"]["modelos"]["kube_namespace"]
            except KeyError:
                pass

        if self._mdl_repo is not None:
            if "kube_namespace" in self._mdl_repo:
                return self._mdl_repo["kube_naemspace"]

        return ""

    def get_remote_sync_strategy(self) -> RemoteSyncStrategy:
        env = os.getenv("MDL_REMOTE_SYNC_STRATEGY")
        if env is not None:
            return RemoteSyncStrategy(env)

        if self._pyproject_dict is not None:
            try:
                sync = self._pyproject_dict["tool"]["modelos"]["remote_sync_strategy"]
                return RemoteSyncStrategy(sync)
            except KeyError:
                pass

        if self._mdl_repo is not None:
            if "remote_sync_strategy" in self._mdl_repo:
                return RemoteSyncStrategy(self._mdl_repo["remote_sync_strategy"])

        return RemoteSyncStrategy.CONTAINER
