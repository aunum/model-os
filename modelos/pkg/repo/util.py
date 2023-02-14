from typing import Tuple

from docker_image import reference

from .oci import OCIPkgRepo
from .base import RemotePkgRepo


def remote_pkgrepo_from_uri(uri: str) -> RemotePkgRepo:
    if uri.startswith("s3://"):
        raise ValueError("s3 not yet supported")

    elif uri.startswith("gs://"):
        raise ValueError("gs not yet supported")

    elif uri.startswith("oci://"):
        return OCIPkgRepo(uri)

    else:
        return OCIPkgRepo(uri)


def split_uri(uri: str) -> Tuple[str, str]:
    if uri.startswith("s3://"):
        raise ValueError("s3 not yet supported")

    elif uri.startswith("gs://"):
        raise ValueError("gs not yet supported")

    elif uri.startswith("oci://"):
        return reference.Reference.split_docker_domain(uri)

    else:
        return reference.Reference.split_docker_domain(uri)
