from os import environ


def is_k8s_proc() -> bool:
    """Check if the current process is running inside Kubernetes

    Returns:
        bool: Whether the current process is running inside k8s
    """
    if environ.get("KUBERNETES_SERVICE_HOST") is not None:
        return True
    return False
