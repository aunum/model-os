from __future__ import annotations
from abc import abstractmethod, ABC
from typing import List, Optional, Iterable, Dict, Any

from .id import ProcessID, RuntimeID
from modelos.env import Env


class Runtime(ABC):
    """A runtime for Python code"""

    @abstractmethod
    def run(self, env: Env, cmd: Optional[List[str]] = None) -> ProcessID:
        """Run the environment

        Args:
            env (Env): Environment to run
            cmd (Optional[List[str]], optional): Command to run in environment. Defaults to None.

        Returns:
            ProcessID: The process ID
        """
        pass

    @abstractmethod
    def sync(self, process: ProcessID) -> None:
        """Sync code to the process

        Args:
            process (ProcessID): Process to sync code to
        """
        pass

    @abstractmethod
    def logs(self, process: ProcessID) -> Iterable[str]:
        """Logs for the process

        Args:
            process (ProcessID): Process to get logs for

        Returns:
            Iterable[str]: A log stream
        """
        pass

    @abstractmethod
    def status(self, process: ProcessID) -> Dict[str, Any]:
        """Status of the process

        Args:
            process (ProcessID): The process to get a status for

        Returns:
            Dict[str, Any]: The status
        """
        pass

    @abstractmethod
    def kill(self, process: ProcessID) -> None:
        """Kill the process

        Args:
            process (ProcessID): Process ID to kill
        """
        pass

    @abstractmethod
    def id(self) -> RuntimeID:
        """ID for the runtime

        Returns:
            RuntimeID: A runtime ID
        """
        pass

    @abstractmethod
    def are_remote(self) -> bool:
        """Check if the current process is within the runtime

        Returns:
            bool: Whether the current process is in the runtime
        """
        pass

    @abstractmethod
    def connect(self) -> None:
        """Connect to the runtime if necessary"""
        pass


class Process(ABC):
    """A runtime process"""

    @abstractmethod
    @classmethod
    def from_id(cls, id: ProcessID) -> Process:
        """Create a process from the ID

        Args:
            id (ProcessID): ID to create process from

        Returns:
            Process: The process
        """
        pass

    @abstractmethod
    @classmethod
    def from_uri(cls, uri: str) -> Process:
        """Create a process from the URI

        Args:
            uri (str): URI to create process from

        Returns:
            Process: The process
        """
        pass

    @abstractmethod
    def sync(self) -> None:
        """Sync code to the process"""
        pass

    @abstractmethod
    def logs(self) -> Iterable[str]:
        """Logs for the process

        Returns:
            Iterable[str]: A log stream
        """
        pass

    @abstractmethod
    def status(self) -> Dict[str, Any]:
        """Status of the process

        Returns:
            Dict[str, Any]: The process status
        """
        pass

    @abstractmethod
    def store(self) -> str:
        """Store of the process

        Returns:
            str: URI of the stored artifact
        """
        pass

    @abstractmethod
    def id(self) -> ProcessID:
        """ID of the process

        Returns:
            ProcessID: The process ID
        """
        pass

    @abstractmethod
    def runtime(self) -> Runtime:
        """Runtime of the process

        Returns:
            Runtime: The runtime
        """
        pass

    @abstractmethod
    def kill(self) -> None:
        """Kill the process"""
        pass

    @abstractmethod
    def labels(self) -> Dict[str, str]:
        """Labels for the process"""
        pass

    @abstractmethod
    @classmethod
    def is_process(cls, uri: str) -> bool:
        """Check if the URI is a process

        Returns:
            bool: Whether its a process
        """
        pass
