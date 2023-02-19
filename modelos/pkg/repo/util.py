from typing import Tuple

from docker_image import reference


def split_uri(uri: str) -> Tuple[str, str]:
    """Split the given URI into host / repo

    Args:
        uri (str): URI to split

    Returns:
        Tuple[str, str]: Host and repo
    """
    if uri.startswith("s3://"):
        raise ValueError("s3 not yet supported")

    elif uri.startswith("gs://"):
        raise ValueError("gs not yet supported")

    elif uri.startswith("oci://"):
        uri = uri.split(":")[0]
        return reference.Reference.split_docker_domain(uri)

    else:
        uri = uri.split(":")[0]
        return reference.Reference.split_docker_domain(uri)
