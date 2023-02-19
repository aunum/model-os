import shutil
import os
import logging
from typing import List, Dict


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


def list_to_str(lis: List[str]) -> str:
    return ",".join(lis)


def str_to_list(s: str) -> List[str]:
    lis = s.split(",")
    if len(lis) == 1 and lis[0] == "":
        return []
    return lis


def dict_to_str(d: Dict[str, str]) -> str:
    ret_lis = []
    for k, v in d.items():
        ret_lis.append(f"{k}:{v}")

    return " | ".join(ret_lis)


def str_to_dict(s: str) -> Dict[str, str]:
    kvs = s.split(" | ")

    ret: Dict[str, str] = {}
    for kv in kvs:
        kv_parts = kv.split(":")
        if len(kv_parts) != 2:
            continue
        ret[kv_parts[0]] = kv_parts[1]
    return ret
