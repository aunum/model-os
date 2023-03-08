from enum import Enum

from semver import VersionInfo


class VersionBump(Enum):
    """The version bump needed"""

    NONE = 0
    PATCH = 1
    MINOR = 2
    MAJOR = 3


def merge_bump(old_bump: VersionBump, new_bump: VersionBump) -> VersionBump:
    if new_bump.value > old_bump.value:
        return new_bump
    return old_bump


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
        info = info.bump_minor()
    elif bump == VersionBump.MAJOR:
        info = info.bump_major()

    return f"v{str(info)}"
