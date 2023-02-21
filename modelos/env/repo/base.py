from abc import ABC, abstractmethod
from typing import Optional, List

from modelos.env import EnvID, EnvInfo

"aunum/ml-project:env.obj.foo-classifier.v1"


class EnvRepo(ABC):
    """An Environment repo stores environments"""

    @abstractmethod
    def find(self, name: Optional[str], version: Optional[str], scheme: Optional[str]) -> List[EnvID]:
        """Find environments

        Args:
            name (Optional[str]): Name of the environment
            version (Optional[str]): Version of the environment
            scheme (Optional[str]): Scheme of the environment

        Returns:
            EnvID: ID of the environment
        """
        pass

    @abstractmethod
    def push(self, name: str, version: str, scheme: str) -> EnvID:
        """Push the env remote

        Args:
            name (str): Name of the env
            version (str): Version of the env
            scheme (str): Scheme of the env

        Returns:
            EnvID: Env ID
        """
        pass

    @abstractmethod
    def pull(self, name: str, version: str, scheme: str) -> EnvID:
        """Pull the env locally

        Args:
            name (str): Name of the env
            version (str): Version of the env
            scheme (str): Scheme of the env

        Returns:
            EnvID: Environment ID
        """
        pass

    @abstractmethod
    def exists(self, name: str, version: str, scheme: str) -> bool:
        """Check if the environment exists

        Args:
            name (str): Name of the env
            version (str): Version of the env
            scheme (str): Scheme of the env

        Returns:
            bool: Whether the env exists
        """
        pass

    @abstractmethod
    def describe(self, name: str, version: str, scheme: str) -> EnvInfo:
        """Describe the environment

        Args:
            name (str): Name of the env
            version (str): Version of the env
            scheme (str): Scheme of the env

        Returns:
            EnvInfo: Info for the environment
        """
        pass
