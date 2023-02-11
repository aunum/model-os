from .base import PkgRepo  # noqa
from .oci import OCIPkgRepo  # noqa


def pkgrepo_from_uri(uri: str) -> PkgRepo:
    if uri.startswith("s3://"):
        raise ValueError("s3 not yet supported")

    elif uri.startswith("gs://"):
        raise ValueError("gcs not yet supported")

    elif uri.startswith("oci://"):
        return OCIPkgRepo(uri)

    else:
        return OCIPkgRepo(uri)
