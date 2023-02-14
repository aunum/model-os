import shutil
import os
import logging


def copy_any(src: str, dest: str) -> None:
    """Copy either a file or a directory

    Args:
        src (str): Source filepath
        dest (str): Dest filepath
    """
    if not os.path.exists(src):
        raise ValueError(f"src '{src}' does not exist")
    if os.path.isdir(src):
        shutil.copytree(src, dest, dirs_exist_ok=True)
    elif os.path.isfile(src):
        shutil.copy(src, dest)
    else:
        logging.warn(f"@ skipping path '{src}' as it is not a directory or file")

    return


def rm_any(filepath: str) -> None:
    """Remove either a filepath or a directory

    Args:
        filepath (str): The filepath to remove
    """
    if not os.path.exists(filepath):
        raise ValueError(f"filepath '{filepath}' does not exist")

    if os.path.isdir(filepath):
        shutil.rmtree(filepath)
    elif os.path.isfile(filepath):
        os.remove(filepath)
    else:
        logging.warn(f"skipping path '{filepath}' as it is not a directory or file")

    return


# def tags_to_str(tags: List[str]) -> str:
#     return ",".join(tags)


# def str_to_tags(tags: str) -> List[str]:
#     return tags.split(",")
