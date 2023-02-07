from typing import Tuple, Any


def make_py_uri(obj: Any) -> str:
    """Make a python URI

    Args:
        obj (Any): Any object

    Returns:
        str: A python URI
    """
    return f"py://{obj.__module__}"


def make_k8s_uri(pod_name: str, namespace: str) -> str:
    """Make a K8s URI

    Args:
        pod_name (str): Pod name
        namespace (str): Pod namespace

    Returns:
        str: A k8s uri
    """
    return f"k8s://{namespace}.{pod_name}"


def parse_k8s_uri(uri: str) -> Tuple[str, str]:
    """Parse the K8s URI

    Args:
        uri (str): URI to parse

    Raises:
        ValueError: If not a valid K8s URI

    Returns:
        Tuple[str, str]: Pod namd and namespace
    """
    print("parsing uri: ", uri)
    if not uri.startswith("k8s://"):
        raise ValueError("can't parse a non-k8s uri")

    uri = uri.strip("k8s://")

    print("stripped uri: ", uri)
    namespace, pod_name = uri.split(".")

    print("pod name: ", pod_name)
    print("namespace: ", namespace)
    return namespace, pod_name
