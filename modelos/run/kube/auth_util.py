from dataclasses import dataclass
from typing import Optional
import logging
import json
import getpass
import hashlib
import base64

from kubernetes.client import (
    CoreV1Api,
    V1ObjectMeta,
    V1ServiceAccount,
    V1RoleBinding,
    RbacAuthorizationV1Api,
    V1Secret,
    V1Role,
    V1PolicyRule,
    V1LocalObjectReference,
    V1RoleRef,
    V1Subject,
    V1Namespace,
)
from kubernetes.client.rest import ApiException
from kubernetes import config
from docker.utils.config import load_general_config
from docker.auth import load_config

from modelos.config import Config
from modelos.run.kube.env import is_k8s_proc
from modelos.virtual.container.client import default_socket

AUTH_HASH_LABEL = "auth-hash"


def ensure_namespace(name: str, core_v1_api: Optional[CoreV1Api] = None) -> None:
    """Create namespace if it doesn't exist

    Args:
        name (str): Name of the namespace
        core_v1_api (Optional[CoreV1Api], optional): Core API to use. Defaults to None.
    """
    if core_v1_api is None:
        config.load_kube_config()
        core_v1_api = CoreV1Api()
    try:
        core_v1_api.read_namespace(name)
        exists = True
    except ApiException:
        exists = False

    if not exists:
        logging.info(f"creating namespace '{name}'")
        ns = V1Namespace(metadata=V1ObjectMeta(name=name))
        core_v1_api.create_namespace(ns)

    return


def service_account_exists(name: str, namespace: str, core_v1_api: Optional[CoreV1Api] = None) -> bool:
    """Checks if a service account exists

    Args:
        name (str): name of the service account
        namespace (str): namespace of the service account
        core_v1_api (CoreV1Api, optional): client to use

    Raises:
        e: An APIException if not a 404

    Returns:
        bool: whether the service account exists
    """
    if core_v1_api is None:
        config.load_kube_config()
        core_v1_api = CoreV1Api()

    found = True
    try:
        core_v1_api.read_namespaced_service_account(name, namespace)
    except ApiException as e:
        if e.status == 404:
            found = False
        else:
            raise e
    return found


def apply_service_account(
    name: str, namespace: str, sa: V1ServiceAccount, core_v1_api: Optional[CoreV1Api] = None
) -> None:
    """Create Service Account if it doesn't exist

    Args:
        name (str): Name of the Service Account
        namespace (str): Namespace of the Service Account
        sa (V1ServiceAccount): Service Account
        core_v1_api (Optional[CoreV1Api], optional): Core API to use. Defaults to None.
    """
    if core_v1_api is None:
        config.load_kube_config()
        core_v1_api = CoreV1Api()
    try:
        core_v1_api.read_namespaced_service_account(name, namespace)
        exists = True
    except ApiException:
        exists = False

    if not exists:
        core_v1_api.create_namespaced_service_account(namespace, sa)
        return

    core_v1_api.replace_namespaced_service_account(name, namespace, sa)
    return


def role_exists(name: str, namespace: str, rbac_v1_api: Optional[RbacAuthorizationV1Api] = None) -> bool:
    """Checks if a role exists

    Args:
        name (str): name of the role
        namespace (str): namespace of the role
        rbac_v1_api (CoreV1Api, optional): client to use

    Raises:
        e: An APIException if not a 404

    Returns:
        bool: whether the role exists
    """
    if rbac_v1_api is None:
        config.load_kube_config()
        rbac_v1_api = RbacAuthorizationV1Api()

    found = True
    try:
        rbac_v1_api.read_namespaced_role(name, namespace)
    except ApiException as e:
        if e.status == 404:
            found = False
        else:
            raise e
    return found


def apply_role(name: str, namespace: str, role: V1Role, rbac_v1_api: Optional[RbacAuthorizationV1Api] = None) -> None:
    """Create Role if it doesn't exist

    Args:
        name (str): Name of the Role
        namespace (str): Namespace of the Role
        role (V1Role): Role
        rbac_v1_api (Optional[CoreV1Api], optional): Core API to use. Defaults to None.
    """
    if rbac_v1_api is None:
        config.load_kube_config()
        rbac_v1_api = RbacAuthorizationV1Api()
    try:
        rbac_v1_api.read_namespaced_role(name, namespace)
        exists = True
    except ApiException:
        exists = False

    if not exists:
        rbac_v1_api.create_namespaced_role(namespace, role)
        return

    rbac_v1_api.replace_namespaced_role(name, namespace, role)
    return


def role_binding_exists(name: str, namespace: str, rbac_v1_api: Optional[RbacAuthorizationV1Api] = None) -> bool:
    """Checks if a Role Binding exists

    Args:
        name (str): name of the role binding
        namespace (str): namespace of the role binding
        rbac_v1_api (CoreV1Api, optional): client to use

    Raises:
        e: An APIException if not a 404

    Returns:
        bool: whether the Role Binding exists
    """
    if rbac_v1_api is None:
        config.load_kube_config()
        rbac_v1_api = RbacAuthorizationV1Api()

    found = True
    try:
        rbac_v1_api.read_namespaced_role_binding(name, namespace)
    except ApiException as e:
        if e.status == 404:
            found = False
        else:
            raise e
    return found


def apply_role_binding(
    name: str, namespace: str, role_binding: V1RoleBinding, rbac_v1_api: Optional[RbacAuthorizationV1Api] = None
) -> None:
    """Create Role Binding if it doesn't exist

    Args:
        name (str): Name of the Role Binding
        namespace (str): Namespace of the Role Binding
        role_binding (V1RoleBinding): Role Binding
        rbac_v1_api (Optional[CoreV1Api], optional): Core API to use. Defaults to None.
    """
    if rbac_v1_api is None:
        config.load_kube_config()
        rbac_v1_api = RbacAuthorizationV1Api()
    try:
        rbac_v1_api.read_namespaced_role_binding(name, namespace)
        exists = True
    except ApiException:
        exists = False

    if not exists:
        rbac_v1_api.create_namespaced_role_binding(namespace, role_binding)
        return

    rbac_v1_api.replace_namespaced_role_binding(name, namespace, role_binding)
    return


def build_dockercfg_json(docker_socket: Optional[str] = None) -> str:
    if docker_socket is None:
        docker_socket = default_socket()

    general_configs = load_general_config()

    auth_configs = load_config(
        config_dict=general_configs,
        credstore_env=None,
    )

    auths = {}
    for registry, auth_cfg in auth_configs.get_all_credentials().items():
        if "ServerAddress" in auth_cfg:
            server_addr = auth_cfg["ServerAddress"]
        elif "serveraddress" in auth_cfg:
            server_addr = auth_cfg["serveraddress"]
        else:
            raise ValueError("server adress is not found in docker auth config")

        if "Username" in auth_cfg:
            username = auth_cfg["Username"]
        elif "username" in auth_cfg:
            username = auth_cfg["username"]
        else:
            raise ValueError("username is not found in docker auth config")

        if "Password" in auth_cfg:
            password = auth_cfg["Password"]
        elif "password" in auth_cfg:
            password = auth_cfg["password"]
        else:
            raise ValueError("password is not found in docker auth config")

        auth_bytes = f"{username}:{password}".encode("utf-8")
        auth64_bytes = base64.b64encode(auth_bytes)

        # Need to monkeypatch the auth being stored in the keychain
        auths[server_addr] = {
            "username": username,
            "password": password,
            "auth": auth64_bytes.decode("utf-8"),
        }

    dockercfg_remote = {"auths": auths}
    auth_cfg_json = json.dumps(dockercfg_remote)

    return auth_cfg_json


def get_dockercfg_secret_name() -> str:
    return "mdl-dockercfg"


@dataclass
class AuthResources:
    secret_name: str
    service_account_name: str


def ensure_cluster_auth_resources(
    core_v1_api: Optional[CoreV1Api] = None,
    rbac_v1_api: Optional[RbacAuthorizationV1Api] = None,
    docker_socket: Optional[str] = None,
    namespace: Optional[str] = None,
    cfg: Optional[Config] = None,
) -> AuthResources:
    secret_name = get_dockercfg_secret_name()
    sa_name = "mdl"

    if is_k8s_proc():
        logging.info("in kubernetes process; won't create auth resources")
        return AuthResources(secret_name, sa_name)

    if core_v1_api is None:
        if is_k8s_proc():
            print("running in kubernetes")
            config.load_incluster_config()

        else:
            print("not running in kubernetes")
            config.load_kube_config()
        core_v1_api = CoreV1Api()

    if rbac_v1_api is None:
        if is_k8s_proc():
            print("running in kubernetes")
            config.load_incluster_config()

        else:
            print("not running in kubernetes")
            config.load_kube_config()
        rbac_v1_api = RbacAuthorizationV1Api()

    # We need to get metadata on the model by looking at the registry and pulling metadata
    if docker_socket is None:
        docker_socket = default_socket()

    if cfg is None:
        cfg = Config()

    if namespace is None:
        namespace = cfg.kube_namespace

    ensure_namespace(namespace)

    auth_cfg_json = build_dockercfg_json(docker_socket)

    h = hashlib.new("sha256")
    h.update(auth_cfg_json.encode("utf-8"))
    digest = h.hexdigest()

    try:
        secret_found = core_v1_api.read_namespaced_secret(secret_name, namespace)
        hash_found = secret_found.metadata.annotations[AUTH_HASH_LABEL]
        if hash_found == digest:
            secret_exists = True
        else:
            logging.info("secret exists but hash doesn't match, recreating...")
            core_v1_api.delete_namespaced_secret(secret_name, namespace)
            secret_exists = False
    except ApiException:
        secret_exists = False

    if not secret_exists:
        logging.info("no dockercfg secret found, creating...")
        # check if secret exists and include a hash check
        dockercfg_secret = V1Secret(
            metadata=V1ObjectMeta(
                name=secret_name,
                namespace=namespace,
                labels={"user": getpass.getuser()},
                annotations={
                    AUTH_HASH_LABEL: digest,
                },
            ),
            string_data={".dockerconfigjson": auth_cfg_json},
            type="kubernetes.io/dockerconfigjson",
        )
        core_v1_api.create_namespaced_secret(namespace, dockercfg_secret)

    # check if service account exists
    sa = V1ServiceAccount(
        metadata=V1ObjectMeta(
            name=sa_name,
            namespace=namespace,
        ),
        image_pull_secrets=[V1LocalObjectReference(name=secret_name)],
    )
    apply_service_account(sa_name, namespace, sa, core_v1_api=core_v1_api)

    role_name = "mdl"
    rl = V1Role(
        metadata=V1ObjectMeta(
            name=role_name,
            namespace=namespace,
        ),
        rules=[
            V1PolicyRule(
                api_groups=[""],
                resources=["pods", "pods/log", "pods/ephemeralcontainers", "pods/exec"],
                verbs=["*"],
            ),
            V1PolicyRule(
                api_groups=[""],
                resources=["services"],
                verbs=["*"],
            ),
        ],
    )
    apply_role(role_name, namespace, rl, rbac_v1_api)

    role_binding_name = "mdl"
    rb = V1RoleBinding(
        metadata=V1ObjectMeta(
            name=role_binding_name,
            namespace=namespace,
        ),
        role_ref=V1RoleRef(
            api_group="rbac.authorization.k8s.io",
            kind="Role",
            name=role_name,
        ),
        subjects=[V1Subject(kind="ServiceAccount", name=role_name, namespace=namespace)],
    )
    apply_role_binding(role_binding_name, namespace, rb, rbac_v1_api)

    return AuthResources(secret_name, sa_name)
