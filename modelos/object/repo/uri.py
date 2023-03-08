from .base import ObjectRepo
from .oci import OCIObjectRepo


def remote_objrepo_from_uri(uri: str) -> ObjectRepo:
    """Get a remote object repo from a URI

    Args:
        uri (str): URI to get a repo for

    Returns:
        ObjectRepo: Object repo
    """

    if uri.startswith("oci://"):
        uri = uri.split(":")[0]
        return OCIObjectRepo(uri)

    else:
        uri = uri.split(":")[0]
        return OCIObjectRepo(uri)
