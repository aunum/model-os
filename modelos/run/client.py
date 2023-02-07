from getpass import getuser
import socket
import os

from modelos.run.kube.env import is_k8s_proc


def get_client_id() -> str:
    """Get the client id of the user and host

    Returns:
        str: A ID for this user and host
    """
    if is_k8s_proc():
        # need to set the env vars on the downward api
        pod_name = os.getenv("POD_NAME")
        if pod_name is None:
            raise SystemError("$POD_NAME is none but we are running in k8s, can't create client id")
        return pod_name

    return f"{getuser()}@{socket.gethostname()}"
