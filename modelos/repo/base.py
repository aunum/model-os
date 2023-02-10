from typing import List

from docker_image import reference


class Repo:
    """A state repository"""

    host: str
    name: str
    uri: str

    def __init__(self, uri: str) -> None:
        host, name = reference.Reference.split_docker_domain(uri)
        self.host = host
        self.name = name
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


class PkgRepo:
    pass


class ImgRepo:
    pass
