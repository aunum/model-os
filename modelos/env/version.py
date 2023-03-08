import hashlib

from modelos.project import Project

VERSION_SHA_LENGTH = 5


def env_hash() -> str:
    """Generate a hash for the environment

    Returns:
        str: A SHA256 hash
    """

    project = Project()
    env = project.env_code()

    h = hashlib.new("sha256")
    h.update(env.encode())

    return h.hexdigest()[:VERSION_SHA_LENGTH]
