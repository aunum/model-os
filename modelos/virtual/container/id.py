from dataclasses import dataclass
from typing import TypeVar, Type  # , Optional
from urllib.parse import urljoin

from docker_image import reference


ID = TypeVar("ID", bound="ImageID")


@dataclass
class ImageID:
    host: str
    repository: str
    tag: str

    @classmethod
    def from_ref(cls: Type[ID], image_ref: str) -> ID:
        host, repo = reference.Reference.split_docker_domain(image_ref)
        ref = reference.Reference.parse(repo)

        return cls(host=host, repository=ref["name"], tag=ref["tag"])

    def ref(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return f"{urljoin(self.host, self.repository)}:{self.tag}"
