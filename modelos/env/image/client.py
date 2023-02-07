import os

from modelos.config import Config


# TODO: do this in the config as a default factory
def default_socket() -> str:
    docker_socket = Config().docker_socket
    if docker_socket is not None:
        return docker_socket

    if os.name == "nt":
        raise ValueError("windows not yet supported")

    return "unix://var/run/docker.sock"
