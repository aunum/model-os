from typing import List

from docker_image import reference


class Repo:
    """An OCI repository"""

    host: str
    repo: str
    uri: str

    def __init__(self, uri: str) -> None:
        host, repo = reference.Reference.split_docker_domain(uri)
        self.host = host
        self.repo = repo
        self.uri = uri

    def __str__(self):
        return self.uri

    def add(self) -> None:
        raise NotImplementedError()

    def add_global(self) -> None:
        raise NotImplementedError()

    @classmethod
    def list(cls) -> List[str]:
        raise NotImplementedError()
