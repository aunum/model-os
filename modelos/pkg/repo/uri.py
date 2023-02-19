from .oci import OCIPkgRepo
from .remote import RemotePkgRepo


def remote_pkgrepo_from_uri(uri: str) -> RemotePkgRepo:
    """Get a remote pkg repo from a URI

    Args:
        uri (str): URI to get a repo for

    Returns:
        RemotePkgRepo: Remote repo
    """
    if uri.startswith("s3://"):
        raise ValueError("s3 not yet supported")

    elif uri.startswith("gs://"):
        raise ValueError("gs not yet supported")

    elif uri.startswith("oci://"):
        uri = uri.split(":")[0]
        return OCIPkgRepo(uri)

    else:
        uri = uri.split(":")[0]
        return OCIPkgRepo(uri)
