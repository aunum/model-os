from modelos.util.rootpath import patch_mdl_file
from .base import ObjectRepo  # noqa
from .oci import OCIObjectRepo  # noqa


def set_repo(uri: str) -> None:
    """Set the repo to use for the object

    Args:
        uri (str): URI of the repo
    """
    patch_mdl_file({"image_repo": uri})
