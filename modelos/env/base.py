from __future__ import annotations
from abc import abstractmethod, ABC
from typing import Optional, List

from .id import EnvID


class Env(ABC):
    """A Python environment"""

    @abstractmethod
    @classmethod
    def from_project(cls, include_repo: bool = True) -> Env:
        """Build an env from the current py project

        Args:
            include_repo (bool, optional): Whether to include the repo. Defaults to True

        Returns:
            Env: An env
        """
        pass

    @abstractmethod
    @classmethod
    def build(cls) -> Env:
        """Build an env

        Returns:
            Env: An env
        """
        pass

    @abstractmethod
    @classmethod
    def find_or_build(cls) -> Env:
        """Find or build an env

        Returns:
            Env: An env
        """
        pass

    @abstractmethod
    @classmethod
    def from_id(cls, id: EnvID) -> Env:
        """Create an env from an id

        Args:
            id (EnvID): EnvID

        Returns:
            Env: An env
        """
        pass

    @abstractmethod
    def build_uri(self, name: str, version: str, scheme: Optional[str] = "py") -> str:
        """Build a URI for an env

        Args:
            name (str): Name of the env
            version (str): Version of the env
            scheme (Optional[str], optional): Scheme of the env. Defaults to 'py'

        Returns:
            str: An env URI
        """
        pass

    @abstractmethod
    def build_id(self, name: str, version: str, scheme: Optional[str] = "py") -> EnvID:
        """Build an ID for an env

        Args:
            name (str): Name of the env
            version (str): Version of the env
            scheme (Optional[str], optional): Scheme of the env. Defaults to 'py'

        Returns:
            str: An EnvID
        """
        pass

    @abstractmethod
    def store(self) -> EnvID:
        """Store the environment

        Returns:
            EnvID: Environment ID
        """
        pass

    @abstractmethod
    def run(self, cmd: List[str], follow: bool = True) -> None:
        """Run a command in the environment"

        Args:
            cmd (List[str]): Command to run
            follow (bool, optional): Whether to follow the execution
        """
        pass

    @abstractmethod
    def sync(self) -> None:
        """Sync code to the environment"""
        pass

    @abstractmethod
    def id(self) -> EnvID:
        """ID for the env

        Returns:
            EnvID: Env ID
        """
        pass

    @abstractmethod
    def root_path(self) -> str:
        """Root path of the env

        Returns:
            str: Root path
        """
        pass

    @abstractmethod
    def delete(self) -> None:
        """Delete the env"""
        pass

    @abstractmethod
    def find(
        self, name: Optional[str] = None, version: Optional[str] = None, scheme: Optional[str] = None
    ) -> List[EnvID]:
        """Find ends

        Args:
            name (Optional[str], optional): Name of the env. Defaults to None.
            version (Optional[str], optional): Version of the env. Defaults to None.
            scheme (Optional[str], optional): Scheme of the env. Defaults to None.

        Returns:
            List[EnvID]: List of envs
        """
        pass
