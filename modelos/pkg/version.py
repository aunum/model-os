import os
from typing import List, Dict
import hashlib
import logging
from enum import Enum

from semver import VersionInfo

VERSION_HASH_LENGTH = 7


class VersionBump(Enum):
    """The version bump needed"""

    NONE = 0
    PATCH = 1
    MINOR = 2
    MAJOR = 3


def compare_file_hashes(current: Dict[str, str], new: Dict[str, str]) -> VersionBump:
    """Compare file hashes

    Args:
        current (Dict[str, str]): Current file hashes
        new (Dict[str, str]): New file hashes

    Returns:
        VersionBump: Whether to version bump
    """
    bump = VersionBump.NONE
    for fp, hash in current.items():
        if fp not in new:
            if bump.value > VersionBump.MINOR.value:
                bump = VersionBump.MINOR
        else:
            new_hash = new[fp]
            if hash != new_hash:
                bump = VersionBump.MAJOR
    return bump


def hash_file(fp: str) -> str:
    """Geet a hash for a file

    Args:
        fp (str): Filepath to hash

    Returns:
        str: A SHA256 hash
    """
    hash = hashlib.new("sha256")
    with open(fp, "r") as f:
        hash.update(f.read().encode())
    return hash.hexdigest()[:VERSION_HASH_LENGTH]


def hash_files(files: List[str]) -> Dict[str, str]:
    """Hash all the given files

    Args:
        files (List[str]): Files to hash

    Returns:
        Dict[str, str]: A map of filepath to hash
    """
    file_hash = {}
    for fp in files:
        if not os.path.exists(fp):
            raise ValueError(f"file '{fp}' does not exist")
        if os.path.isdir(fp):
            file_set = set()

            for dir_, _, files in os.walk(fp):
                if os.path.basename(os.path.normpath(dir_)) == ".mdl":
                    continue
                for file_name in files:
                    rel_dir = os.path.relpath(dir_, fp)
                    rel_file = os.path.join(rel_dir, file_name)
                    file_set.add(rel_file)

                    pth = os.path.join(dir_, file_name)
                    hash = hash_file(pth)
                    file_hash[rel_file] = hash

        elif os.path.isfile(fp):
            hash = hash_file(fp)
            name = os.path.basename(fp)
            file_hash[name] = hash

        else:
            logging.warn(f"& skipping path '{fp}' as it is not a directory or file")
    return file_hash


def hash_all(files: List[str]) -> str:
    """Hash all the given files together

    Args:
        files (List[str]): Files to hash

    Returns:
        str: A SHA256 hash
    """
    hash = hashlib.new("sha256")
    norm_files = []
    for fp in files:
        fp = os.path.normpath(fp)
        norm_files.append(fp)

    norm_files.sort()
    for fp in norm_files:
        if not os.path.exists(fp):
            raise ValueError(f"file '{fp}' does not exist")
        if os.path.isdir(fp):
            for dir_, _, files in os.walk(fp):
                if os.path.basename(os.path.normpath(dir_)) == ".mdl":
                    continue
                for file_name in files:
                    ff = os.path.join(dir_, file_name)
                    with open(ff, "r") as f:
                        b = f.read().encode()
                        hash.update(b)

        elif os.path.isfile(fp):
            with open(fp, "r") as f:
                hash.update(f.read().encode())

        else:
            logging.warn(f"# skipping path '{fp}' as it is not a directory or file")

    version = hash.hexdigest()[:VERSION_HASH_LENGTH]
    return version


def bump_version(version: str, bump: VersionBump) -> str:
    """Bump a version to the given bump

    Args:
        version (str): Version to bump
        bump (VersionBump): Amount to bump

    Returns:
        str: A new version
    """
    if version.startswith("v"):
        version = version[1:]

    info = VersionInfo.parse(version)
    if bump == VersionBump.NONE:
        return version
    elif bump == VersionBump.PATCH:
        info = info.bump_patch()
    elif bump == VersionBump.MINOR:
        info = info.bump_patch()
    elif bump == VersionBump.MAJOR:
        info = info.bump_major

    return f"v{str(info)}"
