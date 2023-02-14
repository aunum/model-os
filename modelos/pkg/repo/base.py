from typing import Optional

from .remote import RemotePkgRepo
from .local import LocalPkgRepo
from modelos.config import Config
from .util import remote_pkgrepo_from_uri


class PkgRepo:
    """A package repository"""

    local: LocalPkgRepo
    remote: RemotePkgRepo

    def __init__(
        self,
        remote: Optional[RemotePkgRepo] = None,
        local: Optional[LocalPkgRepo] = None,
        config: Optional[Config] = None,
    ) -> None:
        if remote is None:
            if config is None:
                config = Config()
            repo_uri = config.pkg_repo
            if repo_uri is None:
                raise ValueError(
                    "could not determine remote repo uri, please set"
                    + " the 'remote' parameter, or configure mdl.yaml, or pyproject.toml"
                )
            remote = remote_pkgrepo_from_uri(repo_uri)

        self.remote = remote

        if local is None:
            local = LocalPkgRepo(config=config)
        self.local = local
