import logging
import time
import inspect
from typing import Callable, Optional

from kubernetes.client import (
    CoreV1Api,
    V1Pod,
)
from kubernetes.client.rest import ApiException
from kubernetes import config

from modelos.scm import SCM
from modelos.config import Config

TYPE_LABEL = "mdl/type"
FUNC_NAME_LABEL = "mdl/func"
SYNC_SHA_LABEL = "mdl/sync-sha"
REPO_SHA_LABEL = "mdl/repo-sha"
ENV_SHA_LABEL = "mdl/env-sha"
REPO_NAME_LABEL = "mdl/repo"
SYNC_STRATEGY_LABEL = "sync-strategy"


def pod_running(name: str, namespace: str, core_v1_api: Optional[CoreV1Api] = None) -> bool:
    """Check if a pod is running

    Args:
        name (str): name of the pod
        namespace (str): namespace of the pod
        core_v1_api (CoreV1Api, optional): client to use

    Returns:
        bool: whether the pod is running
    """
    if core_v1_api is None:
        config.load_kube_config()
        core_v1_api = CoreV1Api()

    try:
        pod: V1Pod = core_v1_api.read_namespaced_pod(name, namespace)
    except ApiException as e:
        logging.info(f"waiting for pod to be running {e}")
        return False
    else:
        if pod.status.phase == "Failed":
            raise SystemError("pod is failed, check logs")
        elif pod.status.phase != "Running":
            logging.info(f"waiting for pod to be running; current phase: {pod.status.phase}")
            return False
        else:
            return True


def wait_for_pod_running(
    name: str,
    namespace: str,
    core_v1_api: Optional[CoreV1Api] = None,
    wait_interval: int = 1,
    max_attempts: int = 1000,
) -> bool:
    """Wait for a pod to be running

    Args:
        name (str): name of the pod
        namespace (str): namespace of the pod
        core_v1_api (CoreV1Api, optional): client to use
        wait_interval (int): period in seconds to wait before retrying
        max_attempts (int): maximum number of intervals to retry for

    Returns:
        bool: whether the pod is running
    """
    if core_v1_api is None:
        config.load_kube_config()
        core_v1_api = CoreV1Api()
    ready = False
    for _ in range(max_attempts):
        ready = pod_running(name, namespace, core_v1_api)
        if not ready:
            logging.info(f"pod not running, retrying in {wait_interval} seconds")
            time.sleep(wait_interval)
            continue
        break
    return ready


def pod_ready(name: str, namespace: str, core_v1_api: Optional[CoreV1Api] = None) -> bool:
    """Check if a pod is ready and has passed it's health checks

    Args:
        name (str): name of the pod
        namespace (str): namespace of the pod
        core_v1_api (CoreV1Api, optional): client to use

    Returns:
        bool: whether the pod is ready
    """
    if core_v1_api is None:
        config.load_kube_config()
        core_v1_api = CoreV1Api()

    try:
        pod: V1Pod = core_v1_api.read_namespaced_pod(name, namespace)
    except ApiException as e:
        logging.info(f"waiting for pod to become ready {e}")
        return False
    else:
        if pod.status.phase == "Failed":
            raise SystemError("pod is failed, check logs")
        elif pod.status.phase != "Running":
            logging.info(f"waiting for pod to become ready; current phase: {pod.status.phase}")
            return False
        else:
            for status in pod.status.container_statuses:
                if not status.ready:
                    logging.info("pod running but not ready")
                    return False
            return True


def wait_for_pod_ready(
    name: str,
    namespace: str,
    core_v1_api: Optional[CoreV1Api] = None,
    wait_interval: int = 1,
    max_attempts: int = 1000,
) -> bool:
    """Wait for a pod to be ready and passing it's health checks

    Args:
        name (str): name of the pod
        namespace (str): namespace of the pod
        core_v1_api (CoreV1Api, optional): client to use
        wait_interval (int): period in seconds to wait before retrying
        max_attempts (int): maximum number of intervals to retry for

    Returns:
        bool: whether the pod is ready
    """
    if core_v1_api is None:
        config.load_kube_config()
        core_v1_api = CoreV1Api()
    ready = False
    for _ in range(max_attempts):
        ready = pod_ready(name, namespace, core_v1_api)
        if not ready:
            logging.info(f"pod not ready, retrying in {wait_interval} seconds")
            time.sleep(wait_interval)
            continue
        break
    return ready


def pod_exists(name: str, namespace: str, core_v1_api: Optional[CoreV1Api] = None) -> bool:
    """Checks if a pod exists

    Args:
        name (str): name of the pod
        namespace (str): namespace of the pod
        core_v1_api (CoreV1Api, optional): client to use

    Raises:
        e: An APIException if not a 404

    Returns:
        bool: whether the pod exists
    """
    if core_v1_api is None:
        config.load_kube_config()
        core_v1_api = CoreV1Api()

    found = True
    try:
        core_v1_api.read_namespaced_pod(name, namespace)
    except ApiException as e:
        if e.status == 404:
            found = False
        else:
            raise e
    return found


def get_pod_name_from_func(func: Callable, scm: Optional[SCM] = None, cfg: Optional[Config] = None) -> str:
    """Get the pod name based on the function

    Args:
        func (Callable): the function to use
        scm (SCM, optional): SCM to use. Defaults to SCM().

    Returns:
        str: the pod name
    """
    if scm is None:
        scm = SCM()

    if cfg is None:
        cfg = Config()

    func_module = inspect.getmodule(func)
    if func_module is None:
        raise SystemError(f"cannot find module for func {func.__name__}")

    mod_name = func_module.__name__
    if mod_name == "__main__":
        mod_name = "main"
    mod_clean = mod_name.replace(".", "-").replace("_", "-")
    name_clean = func.__name__.replace("_", "-")

    return f"fn-{mod_clean}-{name_clean}"


def apply_pod(name: str, namespace: str, pod: V1Pod, core_v1_api: Optional[CoreV1Api] = None) -> None:
    if core_v1_api is None:
        config.load_kube_config()
        core_v1_api = CoreV1Api()
    try:
        core_v1_api.read_namespaced_pod(name, namespace)
        exists = True
    except ApiException:
        exists = False

    if not exists:
        core_v1_api.create_namespaced_pod(namespace, pod)
        return

    core_v1_api.replace_namespaced_pod(name, namespace, pod)
    return
