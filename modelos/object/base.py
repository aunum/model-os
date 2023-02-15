from __future__ import annotations
from dataclasses import dataclass
import shutil
import copy
from types import NoneType
import types
import json
import socket
import sys
from typing import Dict, Iterable, List, Any, Optional, Type, TypeVar, Union, get_args, get_type_hints
import typing
import inspect
import time
import logging
from textwrap import indent
import os
from pathlib import Path
import uuid
from functools import wraps, partialmethod
from types import FunctionType
from inspect import Parameter, signature
import importlib
import importlib.util

from starlette.schemas import SchemaGenerator
import cloudpickle as pickle
from dataclasses_jsonschema import JsonSchemaMixin
from kubernetes import config
from kubernetes.stream import portforward
from kubernetes.client.models import (
    V1VolumeMount,
    V1Pod,
    V1PodSpec,
    V1PodList,
    V1Container,
    V1ContainerPort,
    V1ConfigMap,
    V1Volume,
    V1ConfigMapVolumeSource,
    V1Probe,
    V1ExecAction,
    V1EnvVar,
    V1EmptyDirVolumeSource,
    V1SecretVolumeSource,
    V1KeyToPath,
    V1PodStatus,
    V1ContainerStatus,
    V1ContainerState,
    V1ContainerStateRunning,
    V1ContainerStateTerminated,
    V1ContainerStateWaiting,
    V1EnvVarSource,
    V1ObjectFieldSelector,
)
from kubernetes.client import CoreV1Api, V1ObjectMeta, RbacAuthorizationV1Api
from docker.utils.utils import parse_repository_tag
from docker.auth import resolve_repository_name
from black import format_str, FileMode
from removestar import removestar
import isort
from unimport.main import Main as unimport_main

from modelos.run.kube.sync import copy_file_to_pod
from modelos.virtual.container.client import default_socket
from modelos.env.image.build import REPO_ROOT, find_or_build_img, img_command, build_dockerfile
from modelos.run.kube.pod_util import (
    REPO_SHA_LABEL,
    SYNC_SHA_LABEL,
    REPO_NAME_LABEL,
    ENV_SHA_LABEL,
    SYNC_STRATEGY_LABEL,
    wait_for_pod_ready,
)
from modelos.virtual.container.file import write_dockerfile
from modelos.config import Config, RemoteSyncStrategy
from modelos.scm import SCM
from modelos.virtual.container.registry import get_img_labels, get_repo_tags
from modelos.run.kube.env import is_k8s_proc
from modelos.run.kube.auth_util import ensure_cluster_auth_resources
from modelos.env.image.build import img_id, client_hash
from modelos.object.kind import ObjectInfo
from modelos.run.client import get_client_id
from modelos.run.kube.uri import make_py_uri, parse_k8s_uri, make_k8s_uri
from modelos.object.opts import OptsBuilder, Opts
from modelos.object.kind import Kind, ObjectLocator, OBJECT_URI_ENV
from modelos.object.encoding import (
    is_type,
    is_list,
    is_dict,
    is_tuple,
    is_enum,
    is_first_order,
    is_union,
    is_iterable_cls,
    is_optional,
    decode_any,
)


SERVER_PORT = "8080"
NAME_LABEL = "name"
VERSION_LABEL = "version"
BASES_LABEL = "bases"
PARAMS_SCHEMA_LABEL = "params-schema"
SERVER_PATH_LABEL = "server-path"
URI_LABEL = "uri"
OWNER_LABEL = "owner"
CONFIG_FILE_NAME = "config.json"
BUILD_MNT_DIR = "/mnt/build"
ARTIFACT_TYPE_LABEL = "artifact-type"
CONFIG_DIR = "/config"


K = TypeVar("K", bound="Kind")
C = TypeVar("C", bound="Client")


class Client(Kind):
    """A client for a server running remotely"""

    uri: str
    artifact_labels: Dict[str, Any]
    core_v1_api: CoreV1Api
    rbac_v1_api: RbacAuthorizationV1Api
    uid: uuid.UUID
    server_port: str
    server_addr: str
    pod_name: str
    pod_namespace: str
    scm: SCM
    cfg: Config
    docker_socket: str
    hot: bool

    def __init__(
        self,
        uri: Optional[str] = None,
        opts: Optional[Opts] = None,
        server: Optional[Union[Type[Object], Object]] = None,
        reuse: bool = False,
        hot: Optional[bool] = None,
        dev_dependencies: bool = False,
        clean: bool = True,
        core_v1_api: Optional[CoreV1Api] = None,
        rbac_v1_api: Optional[RbacAuthorizationV1Api] = None,
        docker_socket: Optional[str] = None,
        namespace: Optional[str] = None,
        cfg: Optional[Config] = None,
        scm: Optional[SCM] = None,
    ) -> None:
        if hot is None:
            if hasattr(self, "hot"):
                hot = self.hot
            else:
                hot = False

        sync_strategy = RemoteSyncStrategy.IMAGE
        if hot:
            sync_strategy = RemoteSyncStrategy.CONTAINER

        if is_k8s_proc():
            logging.info("running in kubernetes")

        else:
            logging.info("not running in kubernetes")

        if core_v1_api is None:
            if is_k8s_proc():
                config.load_incluster_config()
            else:
                config.load_kube_config()

            core_v1_api = CoreV1Api()
        self.core_v1_api = core_v1_api

        if rbac_v1_api is None:
            if is_k8s_proc():
                config.load_incluster_config()
            else:
                config.load_kube_config()
            rbac_v1_api = RbacAuthorizationV1Api()
        self.rbac_v1_api = rbac_v1_api

        # We need to get metadata on the server by looking at the registry and pulling metadata
        if docker_socket is None:
            docker_socket = default_socket()
        self.docker_socket = docker_socket

        if cfg is None:
            cfg = Config()
        self.cfg = cfg

        if scm is None:
            scm = SCM()
        self.scm = scm

        if namespace is None:
            namespace = cfg.kube_namespace

        self.uid = uuid.uuid4()

        self._patch_socket(core_v1_api)

        if uri is not None and uri.startswith("k8s://"):
            self.pod_namespace, self.pod_name = parse_k8s_uri(uri)
            self.server_addr = f"http://{self.pod_name}.pod.{self.pod_namespace}.kubernetes:{SERVER_PORT}"
            logging.info(f"connecting directly to pod {self.pod_name} in namespace {self.pod_namespace}")
            info = self.info()
            logging.info(f"server info: {info}")
            self.uri = info.uri
            self.artifact_labels = get_img_labels(self.uri)
            return

        if server is not None:
            logging.info("server provided, storing class")
            self.uri = server.store_cls(dev_dependencies=dev_dependencies, clean=clean, sync_strategy=sync_strategy)
            # if isinstance(server, Object):
            #     opts = server.opts()
        elif uri is not None:
            self.uri = uri
        elif hasattr(self, "uri"):
            pass
        else:
            raise ValueError("Client URI cannot be none. Either 'uri' or 'server' must be provided")

        # Check schema compatibility between client/server https://github.com/aunum/arc/issues/12
        self.artifact_labels = get_img_labels(self.uri)

        if self.artifact_labels is None:
            raise ValueError(
                f"image uri '{self.uri}' does not contain any labels, are you sure it was build by modelos?"
            )

        if reuse:
            # check if container exists
            logging.info("checking if server is already running in cluster")
            found_pod = self._find_reusable_pod(namespace)
            if found_pod is not None:
                logging.info("found reusable server running in cluster")
                pod_name = found_pod.metadata.name
                self.server_addr = f"http://{pod_name}.pod.{namespace}.kubernetes:{SERVER_PORT}"
                self.pod_name = pod_name
                self.pod_namespace = namespace
                annotations = found_pod.metadata.annotations

                is_working = True
                try:
                    info = self.info()
                    logging.info(f"server info: {info}")
                except:  # noqa
                    logging.info("found server not functioning")
                    is_working = False

                if sync_strategy == RemoteSyncStrategy.CONTAINER and is_working:
                    logging.info("sync strategy is container")
                    if SYNC_SHA_LABEL in annotations:
                        if annotations[SYNC_SHA_LABEL] == scm.sha():
                            logging.info("sync sha label up to date")
                            return

                    logging.info("sync sha doesn't match, syncing files")
                    self._sync_to_pod(server, found_pod, namespace=namespace)
                    return

            logging.info("server not found running, deploying now...")

        logging.info("creating server in cluster")
        pod = self._create_k8s_resources(
            sync_strategy=sync_strategy,
            opts=opts,
            namespace=namespace,
        )
        pod_name = pod.metadata.name

        # TODO: handle readiness https://github.com/aunum/arc/issues/11
        time.sleep(10)

        self.server_port = SERVER_PORT
        self.server_addr = f"http://{pod_name}.pod.{namespace}.kubernetes:{SERVER_PORT}"
        self.pod_name = pod_name
        self.pod_namespace = namespace

        logging.info(f"server info: {self.info()}")

        if sync_strategy == RemoteSyncStrategy.CONTAINER:
            logging.info("syncing files to server container")
            self._sync_to_pod(server, pod, namespace)
        return

    def _patch_socket(self, core_v1_api: CoreV1Api) -> None:
        """Patch the socket to port forward to k8s pods

        Args:
            core_v1_api (CoreV1Api): CoreV1API to use
        """
        socket_create_connection = socket.create_connection

        def kubernetes_create_connection(address, *args, **kwargs):
            dns_name = address[0]
            if isinstance(dns_name, bytes):
                dns_name = dns_name.decode()
            dns_name = dns_name.split(".")
            if dns_name[-1] != "kubernetes":
                return socket_create_connection(address, *args, **kwargs)
            if len(dns_name) not in (3, 4):
                raise RuntimeError("Unexpected kubernetes DNS name.")
            namespace = dns_name[-2]
            name = dns_name[0]
            port = address[1]

            if is_k8s_proc():
                pod_found = core_v1_api.read_namespaced_pod(name, namespace)
                ip = pod_found.status.pod_ip
                ipstr = ip.replace(".", "-")
                addr = f"{ipstr}.{namespace}.pod.cluster.local"
                return socket_create_connection((addr, port), *args, **kwargs)

            try:
                pf = portforward(
                    core_v1_api.connect_get_namespaced_pod_portforward, name, namespace, ports=str(SERVER_PORT)
                )
            except Exception as e:
                logging.error(
                    f"Trouble connecting to pod '{name}' in namespace '{namespace}';"
                    + f"check to see if pod is running. \n {e}"
                )  # noqa
                raise
            return pf.socket(int(port))

        socket.create_connection = kubernetes_create_connection

    def _find_reusable_pod(self, namespace: str) -> Optional[V1Pod]:
        """Find a reusable pod to sync code to

        Args:
            namespace (str): Namespace to look

        Returns:
            Optional[V1Pod]: A pod if found or None.
        """
        logging.info("checking if server is already running in cluster")
        pod_list: V1PodList = self.core_v1_api.list_namespaced_pod(namespace)
        found_pod: Optional[V1Pod] = None
        pod: V1Pod
        for pod in pod_list.items:
            annotations = pod.metadata.annotations
            if annotations is None:
                continue
            if URI_LABEL in annotations and OWNER_LABEL in annotations:
                server_uri = annotations[URI_LABEL]
                server_owner = annotations[OWNER_LABEL]
                if server_uri == self.uri:
                    if server_owner != get_client_id():
                        logging.warning("found server running in cluster but owner is not current user")
                    found_pod = pod
            # status: V1PodStatus = pod.status
            # TODO: better status
        return found_pod

    def _sync_to_pod(
        self,
        server: Optional[Union[Type[Object], Object]],
        pod: V1Pod,
        namespace: str,
    ) -> None:
        """Sync local code to pod

        Args:
            server (Optional[Type[Object]]): Object type to use
            pod (V1Pod): Pod to sync to
            namespace (str): Namespace to use
        """
        if server is None:
            raise ValueError("server cannot be None when doing a container sync")

        server_path = server._write_server_file()
        logging.info(f"wrote server to path: {server_path}")
        pod_name = pod.metadata.name
        copy_file_to_pod(
            self.scm.all_files(absolute_paths=True),
            pod_name,
            namespace=namespace,
            base_path=REPO_ROOT.lstrip("/"),
            label=True,
            core_v1_api=self.core_v1_api,
            scm=self.scm,
            restart=False,
        )
        # TODO: need to remove this sleep
        time.sleep(10)
        logging.info("files copied to pod, waiting for pod to become ready")
        # see if pod is ready
        ready = wait_for_pod_ready(pod_name, namespace, self.core_v1_api)
        if not ready:
            raise SystemError(f"pod {pod_name} never became ready")
        logging.info("pod is ready!")

        # should check if info returns the right version
        # it will just return the original verion, how do we sync the verion with
        # the files to tell if its running?
        # TODO! https://github.com/aunum/arc/issues/11
        logging.info(self.info())
        return

    def _create_k8s_resources(
        self,
        sync_strategy: RemoteSyncStrategy,
        labels: Optional[Dict[str, Any]] = None,
        opts: Optional[Opts] = None,
        namespace: Optional[str] = None,
    ) -> V1Pod:
        """Create the resources needed in Kubernetes

        Args:
            sync_strategy (RemoteSyncStrategy): Sync strategy to use
            labels (Optional[Dict[str, Any]], optional): Labels to add. Defaults to None.
            opts (Optional[Opts], optional): Params for the model to use. Defaults to None.
            namespace (Optional[str], optional): Namespace to use. Defaults to None.

        Returns:
            V1Pod: The created pod
        """

        repository, tag = parse_repository_tag(self.uri)
        registry, repo_name = resolve_repository_name(repository)
        project_name = repo_name.split("/")[1]

        if namespace is None:
            namespace = Config().kube_namespace

        pod_name = f"{str(project_name).replace('/', '-')}-{tag}"

        if len(pod_name) > 57:
            pod_name = pod_name[:56]

        uid = str(uuid.uuid4())
        pod_name = pod_name + "-" + uid[:5]

        logging.info("ensuring cluster auth resources...")
        auth_resources = ensure_cluster_auth_resources(
            self.core_v1_api, self.rbac_v1_api, self.docker_socket, namespace, self.cfg
        )

        if opts is not None:
            cfg = V1ConfigMap(
                metadata=V1ObjectMeta(name=pod_name, namespace=namespace), data={CONFIG_FILE_NAME: opts.to_json()}
            )
            self.core_v1_api.create_namespaced_config_map(namespace, cfg)

        server_path = self.artifact_labels[SERVER_PATH_LABEL]

        # if not deploy
        container = V1Container(
            name="server",
            command=img_command(server_path),
            image=self.uri,
            ports=[V1ContainerPort(container_port=int(SERVER_PORT))],
            startup_probe=V1Probe(
                success_threshold=1,
                _exec=V1ExecAction(
                    command=[
                        "curl",
                        f"http://localhost:{SERVER_PORT}/health",
                    ]
                ),
                period_seconds=1,
                failure_threshold=10000,
            ),
            env=[
                V1EnvVar(
                    name="POD_NAME",
                    value_from=V1EnvVarSource(field_ref=V1ObjectFieldSelector(field_path="metadata.name")),
                ),
                V1EnvVar(
                    name="POD_NAMESPACE",
                    value_from=V1EnvVarSource(field_ref=V1ObjectFieldSelector(field_path="metadata.namespace")),
                ),
                V1EnvVar(name=OBJECT_URI_ENV, value=self.uri),
            ],
        )
        container.volume_mounts = [
            V1VolumeMount(name="build", mount_path=BUILD_MNT_DIR),
            V1VolumeMount(name="dockercfg", mount_path="/root/.docker"),
        ]
        if opts is not None:
            container.volume_mounts.append(V1VolumeMount(name="config", mount_path=CONFIG_DIR))

        spec = V1PodSpec(
            containers=[container],
            service_account_name=auth_resources.service_account_name,
        )
        spec.volumes = [
            V1Volume(name="build", empty_dir=V1EmptyDirVolumeSource()),
            V1Volume(
                name="dockercfg",
                secret=V1SecretVolumeSource(
                    secret_name=auth_resources.secret_name,
                    items=[V1KeyToPath(key=".dockerconfigjson", path="config.json")],
                ),
            ),
        ]
        if opts is not None:
            spec.volumes.append(V1Volume(name="config", config_map=V1ConfigMapVolumeSource(name=pod_name)))

        annotations = {
            URI_LABEL: self.uri,
            OWNER_LABEL: get_client_id(),
        }
        annotations.update(self.artifact_labels)
        po = V1Pod(
            metadata=V1ObjectMeta(
                name=pod_name,
                namespace=namespace,
                labels={
                    REPO_SHA_LABEL: self.scm.sha(),
                    ENV_SHA_LABEL: self.scm.env_sha(),
                    REPO_NAME_LABEL: self.scm.name(),
                    SYNC_STRATEGY_LABEL: str(sync_strategy),
                },
                annotations=annotations,
            ),
            spec=spec,
        )
        self.core_v1_api.create_namespaced_pod(namespace, po)

        # see if pod is ready
        ready = wait_for_pod_ready(pod_name, namespace, self.core_v1_api)
        if not ready:
            raise SystemError(f"pod {pod_name} never became ready")

        logging.info(f"pod is ready'{pod_name}'")

        return po

    @classmethod
    def opts(cls) -> Optional[Type[Opts]]:
        """Options for the server

        Returns:
            Optional[Type[Serializable]]: Options for the server
        """
        return OptsBuilder[Opts].build(cls)

    @classmethod
    def find(cls, locator: ObjectLocator) -> List[str]:
        """Find objects

        Args:
            locator (ObjectLocator): A locator of objects

        Returns:
            List[str]: A list of object uris
        """
        raise NotImplementedError()

    @classmethod
    def versions(
        cls: Type[C], repositories: Optional[List[str]] = None, cfg: Optional[Config] = None, compatible: bool = True
    ) -> List[str]:
        """Find all versions of this type

        Args:
            repositories (List[str], optional): Extra repositories to check
            cfg (Config, optional): Config to use
            compatible (bool, optional): Return only compatible versions. Defaults to True

        Returns:
            List[str]: A list of versions
        """

        cli_hash = ""
        if compatible:
            # TODO
            pass

        if repositories is None:
            if cfg is None:
                cfg = Config()
            if cfg.image_repo is None:
                raise ValueError("Must supply an image repo")
            repositories = [cfg.image_repo]

        if repositories is None:
            # TODO: use current repository
            raise ValueError("must provide repositories to search")

        ret: List[str] = []
        for repo_uri in repositories:
            tags = get_repo_tags(repo_uri)

            for tag in tags:
                if f"{cls.__name__.lower().rstrip('client')}" in tag:
                    if compatible:
                        cli_hash_found = tag.split("-")[-1]
                        if cli_hash_found != cli_hash:
                            logging.info(f"bypassing {tag} as it is not compatible with client {cli_hash}")
                            continue

                    ret.append(f"{repo_uri}:{tag}")
        return ret

    @property
    def process_uri(self) -> str:
        """K8s URI for the server

        Returns:
            str: K8s URI for the server
        """
        if self.pod_name == "" or self.pod_namespace == "":
            raise ValueError("no pod name or namespace for client")

        return make_k8s_uri(self.pod_name, self.pod_namespace)

    @property
    def object_uri(self) -> str:
        """URI for the object

        Returns:
            str: A URI for the object
        """
        return self.uri

    def logs(self) -> Iterable[str]:
        """Logs for the process

        Returns:
            Iterable[str]: A stream of logs
        """
        raise NotImplementedError()

    def copy(self: C) -> C:
        """Copy the process

        Returns:
            Client: A client
        """
        # TODO: add a hot copy
        uri = self.store()
        return self.__class__.from_uri(uri=uri)

    def publish(self) -> str:
        """Publish the repo as an installable python package

        Returns:
            str: URI for the artifact
        """
        raise NotImplementedError()

    @classmethod
    def schema(cls) -> str:
        """Schema of the object

        Returns:
            str: Object schema
        """
        # needs to come from the image
        raise NotImplementedError()

    def notebook(self) -> None:
        """Launch a notebook for the object"""
        raise NotImplementedError()

    def sync(self) -> None:
        """Sync changes to a remote process"""
        raise NotImplementedError()

    def source(self) -> str:
        """Source code for the object"""
        raise NotImplementedError()

    def merge(self: C, uri: str) -> C:
        """Merge with the given resource

        Args:
            uri (str): Resource to merge with

        Returns:
            Resource: A Resource
        """
        raise NotImplementedError()

    def diff(self, uri: str) -> str:
        """Diff of the given object from the URI

        Args:
            uri (str): URI to diff

        Returns:
            str: A diff
        """
        raise NotImplementedError()

    @classmethod
    def base_names(cls) -> List[str]:
        """Bases for the resource

        Raises:
            SystemError: Server bases

        Returns:
            List[str]: Bases of the server
        """
        raise NotImplementedError()

    @classmethod
    def clean_artifacts(cls, dir: str = "./artifacts") -> None:
        """Clean any created artifacts

        Args:
            dir (str, optional): Directory where artifacts exist. Defaults to "./artifacts".
        """
        raise NotImplementedError()

    @classmethod
    def from_opts(cls: Type[C], opts: Type[Opts]) -> C:
        """Load server from Opts

        Args:
            opts (Opts): Opts to load from

        Returns:
            Object: An object
        """
        raise NotImplementedError()

    @classmethod
    def opts_schema(cls) -> Dict[str, Any]:
        """Schema for the server options

        Returns:
            Dict[str, Any]: JsonSchema for the server options
        """
        raise NotImplementedError()

    @classmethod
    def load(cls: Type[C], dir: str = "./artifacts") -> C:
        """Load the object

        Args:
            dir (str): Directory to the artifacts
        """
        raise NotImplementedError()

    @classmethod
    def store_cls(
        cls,
        clean: bool = True,
        dev_dependencies: bool = False,
        hot: bool = False,
    ) -> str:
        """Create an image from the server class that can be used to create servers from scratch

        Args:
            clean (bool, optional): Whether to clean generated files. Defaults to True.
            dev_dependencies (bool, optional): Whether to install dev dependencies. Defaults to False.
            hot (bool, optional): Whether to build an environment image

        Returns:
            str: URI for the image
        """

        raise NotImplementedError("Not yet implemented for clients")

    def delete(self) -> None:
        """Delete the resource"""
        if not hasattr(self, "core_v1_api") or (hasattr(self, "core_v1_api") and self.core_v1_api is None):
            if is_k8s_proc():
                config.load_incluster_config()
            else:
                config.load_kube_config()

            self.core_v1_api = CoreV1Api()

        # TODO: maybe it should delte itself https://stackoverflow.com/questions/293431/python-object-deleting-itself
        # or we could just add a 'deleted' attribute and alert if a method is called
        self.core_v1_api.delete_namespaced_pod(self.pod_name, self.pod_namespace)

    @classmethod
    def from_uri(cls: Type[C], uri: str) -> C:
        """Create an instance of the class from the uri

        Args:
            uri (str): URI of the object

        Returns:
            Client: A Client
        """
        return cls(uri=uri)

    @classmethod
    def client(
        cls: Type[C],
        clean: bool = True,
        dev_dependencies: bool = False,
        reuse: bool = True,
        hot: bool = False,
    ) -> Type[C]:
        """Create a client of the class, which will allow for the generation of instances remotely

        Args:
            clean (bool, optional): Whether to clean generated files. Defaults to True.
            dev_dependencies (bool, optional): Whether to install dev dependencies. Defaults to False.
            reuse (bool, optional): Whether to reuse existing processes. Defaults to True.
            hot (bool, optional): Hot reload code remotely

        Returns:
            Client: A client which can generate servers on object initialization
        """
        # TODO: this should roughly be a copy
        raise NotImplementedError("client already initialized")

    def store(self, dev_dependencies: bool = False, clean: bool = True) -> str:  # TODO: make this a generator
        """Store the resource

        Args:
            dev_dependencies (bool, optional): Whether to install dev dependencies. Defaults to False.
            clean (bool, optional): Whether to clean the generated files. Defaults to True.

        Returns:
            str: URI of the saved server
        """
        if not hasattr(self, "core_v1_api") or (hasattr(self, "core_v1_api") and self.core_v1_api is None):
            if is_k8s_proc():
                config.load_incluster_config()
            else:
                config.load_kube_config()

            self.core_v1_api = CoreV1Api()

        logging.info("saving server...")

        self.save()
        # req = request.Request(f"{self.server_addr}/save", method="POST")
        # resp = request.urlopen(req)
        # body = resp.read().decode("utf-8")

        _, tag = parse_repository_tag(self.uri)
        # registry, repo_name = resolve_repository_name(repository)
        # docker_secret = get_dockercfg_secret_name()

        cls_name = tag.split("-")[0]

        info = self.info()
        version = info.version
        uri = img_id(RemoteSyncStrategy.IMAGE, tag=f"{cls_name}-{version}")

        server_filepath = info.server_entrypoint

        labels = self.labels()
        labels[SERVER_PATH_LABEL] = server_filepath

        path_params = {"name": self.pod_name, "namespace": self.pod_namespace}

        query_params = []  # type: ignore
        header_params = {}

        form_params = []  # type: ignore
        local_var_files = {}  # type: ignore

        header_params["Accept"] = "application/json"
        header_params["Content-Type"] = "application/strategic-merge-patch+json"

        # Authentication setting
        auth_settings = ["BearerToken"]  # noqa: E501

        # _pod: V1Pod = core_v1_api.read_namespaced_pod(self.pod_name, self.pod_namespace)

        label_args: List[str] = []
        for k, v in labels.items():
            label_args.append(f"--label={k}={v}")

        args = [
            f"--context={BUILD_MNT_DIR}",
            f"--destination={uri}",
            "--dockerfile=Dockerfile.mdl",
            "--ignore-path=/product_uuid",  # https://github.com/GoogleContainerTools/kaniko/issues/2164
        ]
        args.extend(label_args)
        body = {
            "spec": {
                "ephemeralContainers": [
                    {
                        "name": f"snapshot-{int(time.time())}",
                        "args": args,
                        "image": "gcr.io/kaniko-project/executor:latest",
                        "volumeMounts": [
                            {"mountPath": "/kaniko/.docker/", "name": "dockercfg"},
                            {"mountPath": BUILD_MNT_DIR, "name": "build"},
                        ],
                    }
                ]
            }
        }

        self.core_v1_api.api_client.call_api(
            "/api/v1/namespaces/{namespace}/pods/{name}/ephemeralcontainers",
            "PATCH",
            path_params,
            query_params,
            header_params,
            body,
            post_params=form_params,
            files=local_var_files,
            response_type="V1Pod",  # noqa: E501
            auth_settings=auth_settings,
        )

        logging.info("snapshotting image...")

        done = False

        while not done:
            pod: V1Pod = self.core_v1_api.read_namespaced_pod(self.pod_name, self.pod_namespace)
            status: V1PodStatus = pod.status

            if status.ephemeral_container_statuses is None:
                time.sleep(1)
                logging.info("ephemeral container status is None")
                continue

            for container_status in status.ephemeral_container_statuses:
                st: V1ContainerStatus = container_status
                state: V1ContainerState = st.state

                if state.running is not None:
                    running: V1ContainerStateRunning = state.running
                    logging.info(f"snapshot is running: {running}")

                if state.terminated is not None:
                    terminated: V1ContainerStateTerminated = state.terminated
                    logging.info(f"snapshot is terminated: {terminated}")
                    if terminated.exit_code != 0:
                        raise SystemError(
                            f"unable to snapshot image - reason: {terminated.reason} message: {terminated.message}"
                        )
                    done = True

                if state.waiting is not None:
                    waiting: V1ContainerStateWaiting = state.waiting
                    logging.info(f"snapshot is waiting: {waiting}")

            time.sleep(1)

        logging.info(f"saved object as uri: {str(uri)}")
        return str(uri)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.delete()


def init_wrapper(method):
    """Init wrapper stores the args provided on object creation so that they
    may be used remotely"""

    @wraps(method)
    def wrapped(*args, **kwargs):
        self_var = args[0]
        _kwargs = kwargs.copy()
        names = method.__code__.co_varnames
        _kwargs.update(zip(names[1:], args[1:]))
        if "_kwargs" not in self_var.__dict__:
            self_var.__dict__["_kwargs"] = _kwargs
        return method(*args, **kwargs)

    return wrapped


def local(method):
    """Local wrapper prevents generating a server method"""
    method.local = True
    return method


def nolock(method):
    """Do not lock this method"""
    method.nolock = True
    return method


def methods(methods: List[str]):
    """Wrapper to specify HTTP action to use"""

    def wrapper(method):
        method.methods = methods
        return method

    return wrapper


def partialcls(cls, *args, **kwds):
    """Just like functools.partial but for classes"""

    class NewCls(cls):
        __init__ = partialmethod(cls.__init__, *args, **kwds)

    return NewCls


def convert_hot_to_strategy(hot: bool) -> RemoteSyncStrategy:
    if hot:
        return RemoteSyncStrategy.CONTAINER
    return RemoteSyncStrategy.IMAGE


def convert_strategy_to_hot(strategy: RemoteSyncStrategy) -> bool:
    if strategy == RemoteSyncStrategy.IMAGE:
        return False
    elif strategy == RemoteSyncStrategy.CONTAINER:
        return True

    else:
        raise ValueError("unknown sync strategy: ", strategy)


class ResourceMetaClass(type):
    """Resource metaclass is the metaclass for the Resource type"""

    def __new__(meta, classname, bases, classDict):
        newClassDict = {}

        for attributeName, attribute in classDict.items():
            if isinstance(attribute, FunctionType):
                if hasattr(attribute, "local"):
                    continue

                if attributeName.startswith("__"):
                    continue

                if attributeName == "__init__":
                    attribute = init_wrapper(attribute)

            newClassDict[attributeName] = attribute

        return type.__new__(meta, classname, bases, newClassDict)


class TypeNotSupportedError(Exception):
    pass


@dataclass
class Lock:
    created: float
    """Time the lock was created"""

    key: Optional[str] = None
    """Key associated with the lock"""

    timeout: Optional[int] = None
    """Timout when the lock will expire"""

    def is_expired(self) -> bool:
        """Check whether the lock has expired

        Returns:
            bool: Whether the lock has expired
        """
        if self.timeout is None:
            return False

        if (time.time() - self.created) > self.timeout:
            return True
        return False

    def try_unlock(self, key: str) -> None:
        """Try to unlock the lock with a key

        Raises:
            SystemError: If it can't be unlocked
        """

        if self.key is None:
            return None

        if self.is_expired():
            return None

        if self.key == key:
            return None

        raise SystemError("Object is locked and key provided is denied")


O = TypeVar("O", bound="Object")


class Object(Kind):
    """A resource that can be built and ran remotely over HTTP"""

    last_used_ts: float
    schemas: SchemaGenerator

    scm: SCM = SCM()
    _lock: Optional[Lock] = None

    @classmethod
    @local
    def from_env(cls: Type[O]) -> O:
        """Create the server from the environment, it will look for a saved artifact,
        a config.json, or command line arguments

        Returns:
            Server: A server
        """
        log_level = os.getenv("LOG_LEVEL")
        if log_level is None:
            logging.basicConfig(level=logging.INFO)
        else:
            logging.basicConfig(level=log_level)

        logging.info("logging test0")

        artifact_file = Path(f"./artifacts/{cls.short_name()}.pkl")
        cfg_file = Path(CONFIG_DIR, CONFIG_FILE_NAME)

        if artifact_file.is_file():
            logging.info("loading srv artifact found locally")
            srv = cls.load()
        elif cfg_file.is_file():
            logging.info("loading srv from config file")
            with open(cfg_file) as f:
                jdict = json.load(f)

            opts = decode_any(jdict, cls.opts())
            srv = cls.from_opts(opts)  # type: ignore
        else:
            logging.info("no config file found, attempting to create class without params")
            srv = cls()

        uri = os.getenv(OBJECT_URI_ENV)
        if uri is None:
            logging.warning(f"${OBJECT_URI_ENV} var not found, defaulting to class uri")
        else:
            srv.uri = uri

        srv.last_used_ts = time.time()
        srv.scm = SCM()

        return srv

    @nolock
    @classmethod
    def name(cls) -> str:
        """Name of the resource

        Returns:
            str: Name of the server
        """
        if cls.__name__.endswith("Server"):
            return cls.__name__.removesuffix("Server")
        return cls.__name__

    @nolock
    @classmethod
    def short_name(cls) -> str:
        """Short name for the resource

        Returns:
            str: A short name
        """
        if cls.__name__.endswith("Server"):
            return cls.__name__.removesuffix("Server").lower()
        return cls.__name__.lower()

    @nolock
    @classmethod
    @local
    def base_names(cls) -> List[str]:
        """Bases for the resource

        Raises:
            SystemError: Server bases

        Returns:
            List[str]: Bases of the server
        """
        bases = inspect.getmro(cls)
        base_names: List[str] = []
        for base in bases:
            if isinstance(base, Object):
                base_names.append(base.__name__)
        return base_names

    @nolock
    def info(self) -> ObjectInfo:
        """Info about the resource

        Returns:
            Dict[str, Any]: Resource info
        """
        # TODO: create info object
        server_filepath = self._server_filepath()
        if is_k8s_proc():
            server_filepath = self._container_server_path(server_filepath)

        return ObjectInfo(
            name=self.name(),
            version=self.scm.sha(),
            env_sha=self.scm.env_sha(),
            uri=self.uri,
            server_entrypoint=server_filepath,
            locked=self._is_locked(),
        )

    @methods(["GET", "POST"])
    @nolock
    def health(self) -> Dict[str, str]:
        """Health of the resource

        Returns:
            Dict[str, Any]: Resource health
        """
        return {"health": "ok"}

    @local
    def delete(self) -> None:
        """Delete the resource"""
        raise NotImplementedError()

    @classmethod
    @local
    def find(cls, locator: ObjectLocator) -> List[str]:
        """Find objects

        Args:
            locator (ObjectLocator): A locator of objects

        Returns:
            List[str]: A list of object uris
        """
        raise NotImplementedError()

    @nolock
    @classmethod
    def labels(cls) -> Dict[str, str]:
        """Labels for the resource

        Args:
            scm (Optional[SCM], optional): SCM to use. Defaults to None.

        Returns:
            Dict[str, Any]: Labels for the server
        """
        base_names = cls.base_names()

        base_labels = {
            BASES_LABEL: json.dumps(base_names),
            NAME_LABEL: cls.name(),
            VERSION_LABEL: cls.scm.sha(),
            PARAMS_SCHEMA_LABEL: json.dumps(cls.opts_schema()),
            ENV_SHA_LABEL: cls.scm.env_sha(),
            REPO_NAME_LABEL: cls.scm.name(),
            REPO_SHA_LABEL: cls.scm.sha(),
        }
        return base_labels

    @property
    def process_uri(self) -> str:
        """K8s URI for the process

        Returns:
            str: K8s URI for the server
        """
        name = os.getenv("POD_NAME")
        namespace = os.getenv("POD_NAMESPACE")
        if name is None or namespace is None:
            return f"local://{os.getpid()}"
        return make_k8s_uri(name, namespace)

    @property
    def object_uri(self) -> str:
        """URI for the object

        Returns:
            str: A URI for the object
        """
        uri = os.getenv(OBJECT_URI_ENV)
        if uri is None:
            return make_py_uri(self)
        return uri

    @nolock
    def lock(self, key: Optional[str] = None, timeout: Optional[int] = None) -> None:
        """Lock the process to only operate with the caller

        Args:
            key (Optional[str], optional): An optional key to secure the lock
            timeout (Optional[int], optional): Whether to unlock after a set amount of time. Defaults to None.
        """
        if self._lock is not None and not self._lock.is_expired():
            raise SystemError(f"lock already exists: {self._lock}")
        self._lock = Lock(
            time.time(),
            key,
            timeout,
        )
        return

    @nolock
    def unlock(self, key: Optional[str] = None, force: bool = False) -> None:
        """Unlock the kind

        Args:
            key (Optional[str], optional): Key to unlock, if needed. Defaults to None.
            force (bool, optional): Force unlock without a key. Defaults to False.
        """
        if self._lock is None:
            return
        elif self._lock.is_expired():
            self._lock = None
        elif self._lock.key is None:
            self._lock = None
        else:
            if self._lock.key == key:
                self._lock = None
            elif force is True:
                self._lock = None
            else:
                raise ValueError("lock requires a key to unlock, or force")
        return

    @local
    def logs(self) -> Iterable[str]:
        """Logs for the resource

        Returns:
            Iterable[str]: A stream of logs
        """
        raise NotImplementedError()

    @local
    def diff(self, uri: str) -> str:
        """Diff of the given object from the URI

        Args:
            uri (str): URI to diff

        Returns:
            str: A diff
        """
        raise NotImplementedError()

    @local
    def merge(self: O, uri: str) -> O:
        """Merge with the given resource

        Args:
            uri (str): Resource to merge with

        Returns:
            Resource: A Resource
        """
        raise NotImplementedError()

    @local
    def publish(self) -> str:
        """Publish the repo as an installable package

        Returns:
            str: URI for the artifact
        """
        raise NotImplementedError("Not yet implemented")

    @local
    def sync(self) -> None:
        """Sync changes to a remote process"""
        # TODO: does this make sense?
        raise NotImplementedError("this method only works on client objects")

    @local
    def copy(self: O) -> O:
        """Copy the process

        Returns:
            Resource: A resource
        """
        # TODO: add remote copy
        return copy.deepcopy(self)

    @local
    def source(self) -> str:
        """Source code for the object

        Returns:
            str: Source for the object
        """
        raise NotImplementedError()

    @classmethod
    @local
    def schema(cls) -> str:
        """Schema of the object

        Returns:
            str: Object schema
        """
        raise NotImplementedError()

    @classmethod
    def _cls_package(cls) -> str:
        """Get package of the current class

        Returns:
            str: the package
        """
        raise NotImplementedError()

    @classmethod
    def _client_cls(cls) -> Type[Client]:
        """Class of the client for the resource

        Returns:
            Type[Client]: A client class for the server
        """
        # TODO: need to generate this
        cls._write_client_file()

        cls._write_server_file()

        modl = cls.__module__
        msplit = modl.split(".")
        if len(msplit) > 1:
            msplit = msplit[:-1]
        cls_package = ".".join(msplit)

        if cls_package == "__main__":
            spec = importlib.util.spec_from_file_location("module.name", cls._client_filepath())
            if spec is None:
                raise ValueError(
                    "Trouble loading client class, if you hit this please open an issue", cls._client_filepath()
                )
            mod = importlib.util.module_from_spec(spec)
            sys.modules["module.name"] = mod
            if spec.loader is None:
                raise ValueError(
                    "Trouble loading client class, loader is None, if you hit this please open an issue",
                    cls._client_filepath(),  # noqa
                )
            spec.loader.exec_module(mod)

        else:
            mod = importlib.import_module(f".{cls._client_file_name()}", package=cls_package)  # noqa: F841

        # exec(f"from .{cls._client_file_name()} import {cls.__name__}Client")
        loc_copy = locals().copy()
        client_cls: Type[Client] = eval(f"mod.{cls.__name__}Client", loc_copy)
        return client_cls

    def save(self, out_dir: str = "./artifacts") -> None:
        """Save the object

        Args:
            out_dir (str, optional): Directory to output the artiacts. Defaults to "./artifacts".
        """
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"{self.short_name()}.pkl")
        with open(out_path, "wb") as f:
            pickle.dump(self, f)

        if is_k8s_proc():
            logging.info("building containerfile")
            c = build_dockerfile(sync_strategy=RemoteSyncStrategy.IMAGE)
            logging.info("writing containerfile")
            write_dockerfile(c)
            logging.info("copying directory to build dir...")
            shutil.copytree(REPO_ROOT, BUILD_MNT_DIR, dirs_exist_ok=True)
        return

    @classmethod
    @local
    def load(cls: Type[O], dir: str = "./artifacts") -> O:
        """Load the object

        Args:
            dir (str): Directory to the artifacts
        """
        path = os.path.join(dir, f"{cls.short_name()}.pkl")
        with open(path, "rb") as f:
            return pickle.load(f)

    @classmethod
    @local
    def clean_artifacts(cls, dir: str = "./artifacts") -> None:
        """Clean any created artifacts

        Args:
            dir (str, optional): Directory where artifacts exist. Defaults to "./artifacts".
        """
        shutil.rmtree(dir)

    @classmethod
    @local
    def opts_schema(cls) -> Dict[str, Any]:
        """Schema for the server options

        Returns:
            Dict[str, Any]: JsonSchema for the server options
        """
        opts = OptsBuilder[JsonSchemaMixin].build(cls)
        if opts is None:
            return {}
        return opts.json_schema()

    @classmethod
    @local
    def opts(cls) -> Type[Opts]:
        """Options for the server

        Returns:
            Type[Opts]: Options for the server
        """
        opts = OptsBuilder[Opts].build(cls)
        if opts is None:
            raise ValueError("Can't build opts from this object")
        return opts

    @property
    def uri(self) -> str:
        """URI for the resource

        Returns:
            str: A URI for the resource
        """

        if hasattr(self, "_uri"):
            return self._uri

        return f"{self.__module__}.{self.__class__.__name__}"

    @uri.setter
    def uri(self, val: str):
        self._uri = val

    def _update_ts(self):
        self.last_used_ts = time.time()

    @local
    def notebook(self) -> None:
        """Launch a notebook for the object"""
        raise NotImplementedError()

    @classmethod
    @local
    def from_uri(cls: Type[O], uri: str) -> O:
        """Create an instance of the class from the uri

        Args:
            uri (str): URI of the object

        Returns:
            R: A Resource
        """
        return cls._client_cls().from_uri(uri)  # type: ignore

    @classmethod
    @local
    def client(
        cls: Type[O],
        clean: bool = True,
        dev_dependencies: bool = False,
        reuse: bool = True,
        hot: bool = False,
        uri: Optional[str] = None,
    ) -> Type[O]:
        """Create a client of the class, which will allow for the generation of instances remotely

        Args:
            clean (bool, optional): Whether to clean generated files. Defaults to True.
            dev_dependencies (bool, optional): Whether to install dev dependencies. Defaults to False.
            reuse (bool, optional): Whether to reuse existing processes. Defaults to True.
            hot (bool, optional): Hot reload code remotely
            uri (bool, optional): URI of resource to use. If None will use the current class

        Returns:
            Client: A client which can generate servers on object initialization
        """

        if uri is None:
            client_cls = partialcls(
                cls._client_cls(),
                server=cls,
                reuse=reuse,
                clean=clean,
                dev_dependencies=dev_dependencies,
                hot=hot,
                scm=cls.scm,
            )
        else:
            client_cls = partialcls(
                cls._client_cls(),
                uri=uri,
                reuse=reuse,
                clean=clean,
                dev_dependencies=dev_dependencies,
                hot=hot,
                scm=cls.scm,
            )
        return client_cls

    @classmethod
    @local
    def store_cls(
        cls,
        clean: bool = True,
        dev_dependencies: bool = False,
        sync_strategy: RemoteSyncStrategy = RemoteSyncStrategy.IMAGE,
    ) -> str:
        """Create an image from the server class that can be used to create servers from scratch

        Args:
            clean (bool, optional): Whether to clean generated files. Defaults to True.
            dev_dependencies (bool, optional): Whether to install dev dependencies. Defaults to False.
            sync_strategy (RemoteSyncStrategy, optional): Sync strategy to use. Defaults to RemoteSyncStrategy.IMAGE.

        Returns:
            str: URI for the image
        """

        return cls._build_image(clean=clean, dev_dependencies=dev_dependencies, sync_strategy=sync_strategy)

    @local
    def store(self, dev_dependencies: bool = False, clean: bool = True) -> str:
        """Create a server image with the saved artifact

        Args:
            dev_dependencies (bool, optional): Whether to install dev dependencies. Defaults to False.
            clean (bool, optional): Whether to clean the generated files. Defaults to True.

        Returns:
            str: URI for the image
        """

        self.save()

        uri = self._build_image(
            clean=clean,
            dev_dependencies=dev_dependencies,
            sync_strategy=RemoteSyncStrategy.IMAGE,
        )
        if clean:
            self.clean_artifacts()

        return uri

    @classmethod
    def _container_server_path(cls, local_path: str) -> str:
        server_filepath = Path(local_path)
        repo_root = Path(str(cls.scm.git_repo.working_dir))
        root_relative = server_filepath.relative_to(repo_root)
        container_path = Path(REPO_ROOT).joinpath(root_relative)
        return str(container_path)

    @classmethod
    def _build_image(
        cls,
        labels: Optional[Dict[str, str]] = None,
        clean: bool = True,
        dev_dependencies: bool = False,
        sync_strategy: RemoteSyncStrategy = RemoteSyncStrategy.IMAGE,
    ) -> str:
        """Build a generic image for a server

        Args:
            labels (Optional[Dict[str, str]], optional): Labels to add. Defaults to None.
            clean (bool, optional): Whether to clean generated files. Defaults to True.
            dev_dependencies (bool, optional): Whether to install dev dependencies. Defaults to False.
            sync_strategy (RemoteSyncStrategy, optional): Sync strategy to use. Defaults to RemoteSyncStrategy.IMAGE.

        Returns:
            str: URI of the image
        """

        # write the server file somewhere we can find it
        server_filepath = cls._write_server_file()
        client_filepath = cls._write_client_file()
        container_path = cls._container_server_path(server_filepath)

        base_labels = cls.labels()
        if labels is not None:
            base_labels.update(labels)

        base_labels[SERVER_PATH_LABEL] = str(container_path)

        if sync_strategy == RemoteSyncStrategy.IMAGE:
            imgid = find_or_build_img(
                sync_strategy=RemoteSyncStrategy.IMAGE,
                command=img_command(str(container_path)),
                tag_prefix=f"{cls.short_name().lower()}-",
                labels=base_labels,
                dev_dependencies=dev_dependencies,
                clean=clean,
                client_filepath=client_filepath,
            )
        elif sync_strategy == RemoteSyncStrategy.CONTAINER:
            imgid = find_or_build_img(
                sync_strategy=RemoteSyncStrategy.IMAGE,  # TODO: fix this at the source, we want to copy all files now
                command=img_command(str(container_path)),
                tag=f"{cls.short_name().lower()}-env-{cls.scm.env_sha()}",
                labels=base_labels,
                dev_dependencies=dev_dependencies,
                clean=clean,
            )
        else:
            raise ValueError("unkown sync strategy: ", sync_strategy)

        if clean:
            os.remove(server_filepath)

        return str(imgid)

    @classmethod
    @local
    def from_opts(cls: Type[O], opts: Type[Opts]) -> O:
        """Load server from Opts

        Args:
            opts (Opts): Opts to load from

        Returns:
            Object: An object
        """
        return cls(**opts.__dict__)

    def _reload_dirs(self) -> Dict[str, str]:
        pkgs: Dict[str, str] = {}
        for fp in self.scm.all_files():
            dir = os.path.dirname(fp)
            pkgs[dir] = ""

        return pkgs

    def _is_locked(self) -> bool:
        if self._lock is None:
            return False

        if self._lock.is_expired():
            return False

        return True

    def _check_lock(self, headers: Dict[str, Any]) -> str:
        """Check if the servers locked

        Args:
            headers (Dict[str, Any]): Headers in the request

        Raises:
            ValueError: if locked

        Returns:
            str: The client UUID
        """
        if "client-uuid" not in headers:
            raise ValueError("'client-uuid' must be present in headers")
        client_uuid = headers["client-uuid"]
        if self._lock is None:
            return client_uuid

        self._lock.try_unlock(client_uuid)
        return client_uuid

    def _schema_req(self, request):
        return self.schemas.OpenAPIResponse(request=request)

    @classmethod
    @local
    def versions(
        cls: Type[O], repositories: Optional[List[str]] = None, cfg: Optional[Config] = None, compatible: bool = True
    ) -> List[str]:
        """Find all versions of this type

        Args:
            repositories (List[str], optional): extra repositories to check. Defaults to None
            cfg (Config, optional): Config to use. Defaults to None
            compatible (bool, optional): Whether to only return compatible resources. Defaults to True

        Returns:
            List[str]: A list of versions
        """

        cli_hash = ""
        if compatible:
            client_filepath = cls._write_client_file()
            cli_hash = client_hash(client_filepath)

        if repositories is None:
            if cfg is None:
                cfg = Config()
            if cfg.image_repo is None:
                raise ValueError("must supply an image repo")
            repositories = [cfg.image_repo]

        if repositories is None:
            # TODO: use current repository
            raise ValueError("must provide repositories to search")

        ret: List[str] = []
        for repo_uri in repositories:
            tags = get_repo_tags(repo_uri)

            for tag in tags:
                if f"{cls.__name__.lower()}" in tag:
                    if compatible:
                        cli_hash_found = tag.split("-")[-1]
                        if cli_hash_found != cli_hash:
                            logging.info(f"bypassing {tag} as it is not compatible with client {cli_hash}")
                            continue
                    ret.append(f"{repo_uri}:{tag}")
        return ret

    def _get_class_that_defined_method(fn):
        if inspect.ismethod(fn):
            for cls in inspect.getmro(fn.__self__.__class__):
                if fn.__name__ in cls.__dict__:
                    return cls
            fn = fn.__func__  # fallback to __qualname__ parsing
        if inspect.isfunction(fn):
            cls = getattr(inspect.getmodule(fn), fn.__qualname__.split(".<locals>", 1)[0].rsplit(".", 1)[0], None)
            if isinstance(cls, type):
                return cls
        return None

    @classmethod
    def _gen_server(cls) -> str:
        routes: List[str] = []
        server_fns: List[str] = []
        import_statements: Dict[str, Any] = {}

        fns = inspect.getmembers(cls, predicate=inspect.isfunction)
        methods = inspect.getmembers(cls, predicate=inspect.ismethod)

        fns.extend(methods)

        used_vars: Dict[str, Any] = {}
        possible_vars: str = "abcdefghijklmnopqrstuvwxyz"
        var_iter: int = 0

        def get_var() -> str:
            nonlocal possible_vars, used_vars, var_iter
            if len(used_vars) >= len(possible_vars):
                possible_vars = possible_vars + possible_vars
                var_iter += 1
            ret = possible_vars[len(used_vars)]
            if var_iter > 0:
                ret = f"{ret}_{var_iter}"
            used_vars[ret] = ""
            return ret

        def proc_load(
            t: Type,
            key: str,
            load_lines: List[str],
            idt: str = "",
            jdict_name: str = "jdict",
            is_nested: Optional[bool] = False,
        ) -> None:
            """Generate the code to deserialize the parameters

            Args:
                t (Type): Type to process
                key (str): Key of the type
                load_lines (List[str]): Load lines to append to
                idt (str, optional): Indent for code. Defaults to "".
                default (Optional[Any], optional): is this needed?. Defaults to None.
                optional_dict (Optional[Dict[str, Any]], optional): Helps track if this is an optional param.
                    Defaults to None.
            """
            # if optional_dict is None:
            #     optional_dict = {}

            if is_type(t):
                logging.warning("types not yet supported as parameters")
                raise TypeNotSupportedError()

            if t == inspect._empty:
                raise ValueError(f"field '{key}' must by typed")

            if is_first_order(t):
                return

            if is_optional(t):
                load_lines.append(indent(f"if '{key}' in _{jdict_name}:", idt))
                idt += "    "

            # if default != inspect._empty and key not in optional_dict:
            #     load_lines.append(indent(f"if '{key}' in _jdict:", idt))
            #     idt += "    "
            #     optional_dict[key] = None

            if not is_nested:
                load_lines.append(indent(f"_{key} = _{jdict_name}['{key}']", idt))

            t_hint = cls._proc_arg(t, import_statements, "")

            # load_lines.append(indent(f"_{key}: {t_hint}", idt))

            # start type checks
            _op = getattr(t, "from_dict", None)
            if callable(_op):
                load_lines.append(indent(f"_{key} = {t.__name__}.from_dict(_{jdict_name}['{k}'])", idt))

            elif is_dict(t):
                args = get_args(t)
                if len(args) != 2:
                    raise ValueError(f"Dicts must be typed - {key}: {t}")

                load_lines.append(indent(f"# code for dict: {t_hint}", idt))
                t_hint = cls._proc_arg(t, import_statements, "")
                if is_first_order(args[1]):
                    return

                import_statements["from modelos.object.encoding import json_is_type_match"] = None
                load_lines.append(indent(f"if not json_is_type_match({t_hint}, _{key}):", idt))
                load_lines.append(
                    indent(f"    raise ValueError(\"JSON from '{key}' returned does not match type: {t}\")", idt)
                )
                load_lines.append("")
                key_var = get_var() + "_key"
                val_var = get_var() + "_val"
                load_lines.append(indent(f"_{key}_dict: {t_hint} = {{}}", idt))
                load_lines.append(indent(f"for _{key_var}, _{val_var} in _{key}.items():", idt))
                proc_load(args[1], val_var, load_lines, idt + "    ", is_nested=True)
                load_lines.append(indent(f"    _{key}_dict[_{key_var}] = _{val_var}  # type: ignore", idt))
                load_lines.append(indent(f"_{key} = _{key}_dict", idt))
                load_lines.append(indent(f"# end dict: {t_hint}", idt))
                load_lines.append("")

            elif is_list(t):
                args = get_args(t)
                if len(args) != 1:
                    raise ValueError(f"Lists must be typed - {key}: {t}")

                load_lines.append(indent(f"# code for list: {t_hint}", idt))
                t_hint = cls._proc_arg(t, import_statements, "")
                if is_first_order(args[0]):
                    return

                import_statements["from modelos.object.encoding import json_is_type_match"] = None
                load_lines.append(indent(f"if not json_is_type_match({t_hint}, _{key}):", idt))
                load_lines.append(
                    indent(f"    raise ValueError(\"JSON from '{key}' returned does not match type: {t}\")", idt)
                )
                load_lines.append("")
                val_var = get_var() + "_val"
                load_lines.append(indent(f"_{key}_list: {t_hint} = []", idt))
                load_lines.append(indent(f"for _{val_var} in _{key}:", idt))
                proc_load(args[0], val_var, load_lines, idt + "    ", is_nested=True)
                load_lines.append(indent(f"    _{key}_list.append(_{val_var})  # type: ignore", idt))
                load_lines.append(indent(f"_{key} = _{key}_list", idt))
                load_lines.append(indent(f"# end list: {t_hint}", idt))
                load_lines.append("")

            elif is_tuple(t):
                args = get_args(t)
                load_lines.append(indent(f"# code for tuple: {t_hint}", idt))
                load_lines.append(indent(f"_{key}_tuple: {t_hint} = ()  # type: ignore", idt))
                load_lines.append("")
                for i, arg in enumerate(args):
                    load_lines.append(indent(f"# code for tuple arg: {arg}", idt))
                    load_lines.append(indent(f"_{key}_{i} = _{key}[{i}]", idt))
                    proc_load(arg, f"{key}_{i}", load_lines, idt, is_nested=True)
                    load_lines.append(indent(f"_{key}_tuple = _{key}_tuple + (_{key}_{i},)  # type: ignore", idt))
                    load_lines.append(indent(f"# end tuple arg: {arg}", idt))
                    load_lines.append("")
                load_lines.append(indent(f"_{key} = _{key}_tuple  # type: ignore", idt))
                load_lines.append(indent(f"# end tuple: {t_hint}", idt))
                load_lines.append("")

            elif is_union(t):
                args = typing.get_args(t)

                if len(args) == 0:
                    logging.warning("found union with no args")

                load_lines.append(indent(f"# code for union: {t_hint}", idt))
                if len(args) == 2 and args[1] == NoneType:
                    # Handle optionals
                    args = (args[1], args[0])

                for i, arg in enumerate(args):
                    if_line = "if"
                    if i > 0:
                        if_line = "elif"

                    arg_hint = cls._proc_arg(arg, import_statements, "")
                    h = cls._build_hint(arg, import_statements)

                    if is_first_order(arg):
                        load_lines.append(indent(f"{if_line} type(_{key}) == {h}:", idt))
                        load_lines.append(indent("    pass", idt))
                        continue

                    elif arg == NoneType:
                        load_lines.append(indent(f"{if_line} _{key} is {h}:", idt))
                        load_lines.append(indent("    pass", idt))
                        continue

                    else:
                        import_statements["from modelos.object.encoding import json_is_type_match"] = None
                        load_lines.append(indent(f"{if_line} json_is_type_match({arg_hint}, _{key}):", idt))
                        load_lines.append(indent(f"    print('checking type match match for {h}')", idt))
                        proc_load(arg, key, load_lines, idt + "    ")

                load_lines.append(indent("else:", idt))
                load_lines.append(
                    indent(
                        f'    raise ValueError(f"Argument could not be deserialized: {key} - type: {{type(_{key})}}")',
                        idt,
                    )
                )
                load_lines.append(indent(f"# end union: {t_hint}", idt))
                load_lines.append("")

            elif t == typing.Any:
                # TODO: handle any types, may need some basic checks similar to Union
                pass

            elif is_enum(t):
                h = cls._build_hint(t, import_statements)
                load_lines.append(indent(f"_{key} = {h}(_{key})", idt))

            elif hasattr(t, "__dict__"):
                load_lines.append("")
                load_lines.append(indent(f"# code for obj: {t_hint}", idt))
                # load_lines.append(indent(f"_{key} = _{key}.__dict__  # type: ignore", idt))
                if hasattr(t, "__annotations__"):
                    annots = get_type_hints(t)
                    h = cls._build_hint(t, import_statements)

                    load_lines.append(indent(f"_{key}_obj = object.__new__({h})", idt))

                    for nm, typ in annots.items():
                        nm_var = f"{nm}_attr"
                        load_lines.append(indent(f"_{nm_var} = _{key}['{nm}']", idt))
                        proc_load(typ, nm_var, load_lines, idt, is_nested=True, jdict_name=key)
                        load_lines.append(indent(f"setattr(_{key}_obj, '{nm}', _{nm_var})", idt))
                        load_lines.append("")

                    load_lines.append(indent(f"_{key} = _{key}_obj  # type: ignore", idt))
                    load_lines.append(indent(f"# end obj: {t_hint}", idt))
                    load_lines.append("")

            else:
                raise ValueError(f"Do not know how to load param '{key}' of type: {t}")

            if not is_nested:
                load_lines.append(indent(f"_{jdict_name}['{key}'] = _{key}", idt))

        def proc_return(ret: Type, ret_lines: List[str], idt: str = "", ret_name: str = "ret") -> None:
            if is_type(ret):
                logging.warning("types not yet supported as parameters")
                raise TypeNotSupportedError()

            elif ret == NoneType:
                # ret_lines.append(indent(f"_{ret_name} = {{'value': None}}", idt))
                return

            elif is_first_order(ret):
                # ret_lines.append(indent(f"_{ret_name} = {{'value': _ret}}", idt))
                return

            elif is_dict(ret):
                args = get_args(ret)
                if len(args) != 2:
                    raise ValueError(f"Dictionary must by typed: {name}")

                if is_first_order(args[1]):
                    return

                else:
                    ret_lines.append(indent(f"# code for dict arg: {ret}", idt))
                    ret_lines.append(indent(f"_{ret_name}_dict = {{}}", idt))
                    key_var = get_var() + "_key"
                    val_var = get_var() + "_val"
                    ret_lines.append(indent(f"for _{key_var}, _{val_var} in _{ret_name}.items():  # type: ignore", idt))
                    proc_return(args[1], ret_lines, idt + "    ", val_var)
                    ret_lines.append(indent(f"    _{ret_name}_dict[_{key_var}] = _{val_var}  # type: ignore", idt))
                    ret_lines.append(indent(f"_{ret_name} = _{ret_name}_dict", idt))
                    ret_lines.append(indent(f"# end dict: {ret}", idt))
                    ret_lines.append("")

            elif is_list(ret):
                args = get_args(ret)
                if len(args) != 1:
                    raise SystemError(f"List must be typed: {ret}")

                if is_first_order(args[0]):
                    return

                else:
                    ret_lines.append(indent(f"# code for list: {ret}", idt))
                    ret_lines.append(indent(f"_{ret_name}_list = []", idt))
                    val_var = get_var() + "_val"
                    ret_lines.append(indent(f"for _{val_var} in _{ret_name}:  # type: ignore", idt))
                    proc_return(args[0], ret_lines, idt + "    ", val_var)
                    ret_lines.append(indent(f"    _{ret_name}_list.append(_{val_var})", idt))
                    ret_lines.append(indent(f"_{ret_name} = _{ret_name}_list", idt))
                    ret_lines.append(indent(f"# end list: {ret}", idt))
                    ret_lines.append("")

            elif is_tuple(ret):
                ret_lines.append(indent(f"# code for tuple: {ret}", idt))
                args = get_args(ret)
                ret_lines.append(indent(f"_{ret_name}_list = []", idt))
                for i, arg in enumerate(args):
                    ret_lines.append(indent(f"# code for tuple arg: {arg}", idt))
                    arg_name = f"{ret_name}_{i}"
                    ret_lines.append(indent(f"_{arg_name} = _{ret_name}[{i}]", idt))
                    proc_return(arg, ret_lines, idt, arg_name)
                    ret_lines.append(indent(f"_{ret_name}_list.append(_{arg_name})  # type: ignore", idt))
                    ret_lines.append(indent(f"# end tuple arg: {arg}", idt))
                    ret_lines.append("")
                ret_lines.append(indent(f"_{ret_name} = _{ret_name}_list  # type: ignore", idt))
                ret_lines.append(indent(f"# end tuple: {ret}", idt))
                ret_lines.append("")

            elif is_union(ret):
                # TODO: make this fully recursive
                ret_lines.append(indent(f"# code for union: {ret}", idt))
                args = typing.get_args(ret)
                if len(args) == 2 and args[1] == NoneType:
                    # Handle optionals
                    args = (args[1], args[0])

                import_statements["from modelos.object.encoding import deep_isinstance"] = None
                for i, arg in enumerate(args):
                    if_line = "if"
                    if i > 0:
                        if_line = "elif"
                    arg_hint = cls._proc_arg(arg, import_statements, "")
                    ret_lines.append(indent(f"{if_line} deep_isinstance(_{ret_name}, {arg_hint}):", idt))

                    len_ret = len(ret_lines)
                    proc_return(arg, ret_lines, idt + "    ")  # We may need to return the arg name here
                    len_ret_post = len(ret_lines)
                    if len_ret == len_ret_post:
                        ret_lines.append(indent("    pass", idt))
                ret_lines.append(indent("else:", idt))
                ret_lines.append(
                    indent(
                        '    raise ValueError("Do not know how to serialize" + '
                        + f"\"parameter '{ret}' \" + f\"of type '{{type(_{ret_name})}}'\")",
                        idt,
                    )
                )
                ret_lines.append(indent(f"# end union: {ret}", idt))
                ret_lines.append("")

            elif is_enum(ret):
                ret_lines.append(indent(f"# code for enum: {ret}", idt))
                ret_lines.append(indent(f"_{ret_name} = _{ret_name}.value  # type: ignore", idt))
                ret_lines.append(indent(f"# end enum: {ret}", idt))
                ret_lines.append("")

            elif ret == typing.Any:
                # TODO: we should have a way of trying to serialize at runtime
                logging.warning(
                    "Use of Any type may result in serialization failures; object supplied to Any "
                    + "must be json serializable"
                )

            # TODO: need to handle the given dict types
            elif hasattr(ret, "__dict__"):
                ret_lines.append(indent(f"# code for object: {ret}", idt))
                ret_lines.append(indent(f"_{ret_name} = _{ret_name}.__dict__  # type: ignore", idt))
                if hasattr(ret, "__annotations__"):
                    annotations = get_type_hints(ret)
                    for nm, typ in annotations.items():
                        typ_hint = cls._proc_arg(typ, import_statements, "")

                        if is_first_order(typ):
                            continue
                        ret_lines.append(indent(f"_{nm}: {typ_hint} = _{ret_name}['{nm}']", idt))
                        proc_return(typ, ser_lines, idt, nm)
                        ret_lines.append(indent(f"_{ret_name}['{nm}'] = _{nm}", idt))

                ret_lines.append(indent(f"# end object: {ret}", idt))
                ret_lines.append("")

            else:
                raise ValueError(f"Do not know how to serialize param '{name}' of type: {t}")

            # Need to handle things like mixins --> look at json schema mixin

        for name, fn in fns:
            # print("\n====\n server fn: ", name)
            used_vars = {}
            root_cls = cls._get_class_that_defined_method(fn)
            if not issubclass(root_cls, Object):
                # logging.info(f"skipping fn '{name}' as it is not of subclass resource")
                continue

            sig = signature(fn, eval_str=True, follow_wrapped=True)

            if hasattr(fn, "local"):
                continue

            if name.startswith("__"):
                continue

            if name.startswith("_"):
                continue

            load_lines: List[str] = []
            not_supported: bool = False
            for k in sig.parameters:
                param = sig.parameters[k]
                if k == "self" or k == "cls" or k == "args" or k == "kwargs" or str(param).startswith("*"):
                    continue

                t = param.annotation

                try:
                    proc_load(t, k, load_lines)
                except TypeNotSupportedError:
                    not_supported = True
                    break

            if not_supported:
                logging.warning(f"function '{name}' will be bypassed as it contains unsupported types")
                continue

            hints = get_type_hints(fn)

            if "return" not in hints:
                logging.warning(f"no return method specified for function '{name}' skipping generation")
                continue

            ret = hints["return"]

            is_iterable = is_iterable_cls(ret)
            if is_iterable:
                args = get_args(ret)
                if len(args) == 0:
                    raise SystemError("args for iterable are None")
                if len(args) > 1:
                    raise ValueError("Iterable with args greater than one not currently supported")

                ret = args[0]

            ser_lines: List[str] = []

            try:
                proc_return(ret, ser_lines)
                if is_first_order(ret) or is_enum(ret) or is_list(ret) or is_tuple(ret):
                    ser_lines.append("_ret = {'value': _ret}")
                if ret == NoneType:
                    ser_lines.append("_ret = {'value': None}")
                if is_union(ret):
                    import_statements["from modelos.object.encoding import is_first_order"] = None
                    ser_lines.append("if is_first_order(type(_ret)) or _ret is None:")
                    ser_lines.append("    _ret = {'value': _ret}")
            except TypeNotSupportedError:
                logging.warning(f"function '{name}' will be bypassed as it contains unsupported types")
                continue

            check_lock_line = ""
            if not hasattr(fn, "nolock"):
                check_lock_line = "self._check_lock(headers)"

            sig_doc_qa = ""
            if len(name + str(sig)) > 70:
                sig_doc_qa = "  # noqa"

            if is_iterable:
                fin_ser_lines = ""
                for line in ser_lines:
                    line += "\n"
                    fin_ser_lines += indent(line, "            ")

                joined_load_lines = ""
                for line in load_lines:
                    line += "\n"
                    joined_load_lines += indent(line, "        ")
                req_code = f"""
    async def _{name}_req(self, websocket):
        \"""Request for function:
        {name}{sig}{sig_doc_qa}
        \"""

        await websocket.accept()
        headers = websocket.headers
        logging.debug(f"headers: {{headers}}")
        {check_lock_line}

        # Process incoming messages
        qs = parse.parse_qs(str(websocket.query_params))

        _jdict = {{}}
        if "data" in qs and len(qs["data"]) > 0:
            _jdict = json.loads(qs["data"][0])
{joined_load_lines}

        print("jdict: ", _jdict)
        for _ret in self.{name}(**_jdict):
{fin_ser_lines}

            print("sending json")
            await websocket.send_json(_ret)
            print("sent")

        print("all done sending data, closing socket")
        await websocket.close()
                """
                server_fns.append(req_code)
                routes.append(f"WebSocketRoute('/{name}', endpoint=self._{name}_req)")

            else:
                fin_ser_lines = ""
                for line in ser_lines:
                    line += "\n"
                    fin_ser_lines += indent(line, "        ")

                joined_load_lines = ""
                for line in load_lines:
                    line += "\n"
                    joined_load_lines += indent(line, "        ")

                req_code = f"""
    async def _{name}_req(self, request):
        \"""Request for function:
        {name}{sig}{sig_doc_qa}
        \"""

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {{}}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {{headers}}")
        {check_lock_line}

{joined_load_lines}
        print("calling function: ", _jdict)
        _ret = self.{name}(**_jdict)
        print("called function: ", _ret)
{fin_ser_lines}

        print("returning: ", _ret)
        return JSONResponse(_ret)
"""
                server_fns.append(req_code)

                if hasattr(fn, "methods"):
                    liststr = "["
                    for i, method in enumerate(fn.methods):
                        liststr += f"'{method}'"
                        if (i + 1) == len(fn.methods):
                            continue
                        liststr += ","
                    liststr += "]"
                    routes.append(f"Route('/{name}', endpoint=self._{name}_req, methods={liststr})")
                else:
                    routes.append(f"Route('/{name}', endpoint=self._{name}_req, methods=['POST'])")

        routes_joined = ", ".join(routes)
        route_code = f"""
    def _routes(self) -> List[BaseRoute]:
        return [{routes_joined}]
"""
        server_fns.append(route_code)

        # cls_file_path = Path(inspect.getfile(cls))
        # cls_file = cls_file_path.stem

        cls_arg = cls._proc_arg(cls, import_statements, "")

        imports_joined = "\n".join(import_statements.keys())
        server_fns_joined = "".join(server_fns)
        server_file = f"""
# This file was generated by ModelOS
from typing import List
import logging
import os
import json
from urllib import parse

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route, WebSocketRoute, BaseRoute
import uvicorn

{imports_joined}

log_level = os.getenv("LOG_LEVEL")
if log_level is None:
    logging.basicConfig(level=logging.INFO)
else:
    logging.basicConfig(level=log_level)


class {cls.__name__}Server({cls_arg}):
    \"""A resource server for {cls.__name__}\"""
{server_fns_joined}

o = {cls.__name__}Server.from_env()
pkgs = o._reload_dirs()

app = Starlette(routes=o._routes())

if __name__ == "__main__":
    logging.info(f"starting server version '{{o.scm.sha()}}' on port: {SERVER_PORT}")
    uvicorn.run(
        "__main__:app",
        host="0.0.0.0",
        port={SERVER_PORT},
        log_level="info",
        workers=1,
        reload=True,
        reload_dirs=pkgs.keys(),
    )
        """
        return server_file

    @classmethod
    def _server_file_name(cls) -> str:
        return f"{cls.short_name()}_server"

    @classmethod
    def _server_filepath(cls) -> str:
        filename = f"{cls._server_file_name()}.py"
        dir = os.path.dirname(os.path.abspath(inspect.getfile(cls)))
        filepath = os.path.join(dir, filename)
        return filepath

    @classmethod
    def _write_server_file(cls) -> str:
        """Generate and write the server file next to the current one

        Returns:
            str: The server filepath
        """
        filepath = cls._server_filepath()
        logging.info(f"writing server file to {filepath}")
        with open(filepath, "w", encoding="utf-8") as f:
            server_code = cls._gen_server()
            server_code = removestar.fix_code(server_code, file=filepath)
            server_code = isort.code(server_code)
            server_code = format_str(server_code, mode=FileMode())
            f.write(server_code)
            unimport_main.run(["-r", filepath])
        return filepath

    @classmethod
    def _build_hint(cls, h: Type, imports: Dict[str, Any], module: Optional[str] = None) -> str:
        if hasattr(h, "__forward_arg__"):
            if module == "__main__":
                return h.__forward_arg__
            fq = f"{module}.{h.__forward_arg__}"
            imports[f"import {module}"] = None
            return fq

        if h == Ellipsis:
            return "..."

        if hasattr(h, "__name__"):
            if h.__name__ == "NoneType":
                return "None"
            if h.__name__ == "_empty":
                return ""
            if h.__module__ == "builtins":
                return f"{h.__name__}"
            else:
                if h.__module__ == "__main__":
                    p = inspect.getfile(cls)
                    filename = os.path.basename(p)

                    mod_name = filename.split(".")[0]
                    # we always assume that if the __module__ is main the resource is in
                    # the same module as the object, and if it weren't it would be a circular import
                    imports[f"import {mod_name}"] = None
                    return f"{mod_name}.{h.__name__}"

                imports[f"import {h.__module__}"] = None

                return f"{h.__module__}.{h.__name__}"
        else:
            if hasattr(h, "__module__"):
                mod = h.__module__
            else:
                if module is None:
                    raise ValueError("mod is None!")
                mod = module

            if mod == "__main__":
                p = inspect.getfile(cls)
                if hasattr(cls, "__file__"):
                    pass
                filename = os.path.basename(p)

                mod_name = filename.split(".")[0]
                # we always assume that if the __module__ is main the resource is in
                # the same module as the object, and if it weren't it would be a circular import
                imports[f"import {mod_name}"] = None
                return f"{mod_name}.{str(h)}"
                # f = inspect.getfile(h)
                # client_path = cls._client_filepath()
                # imports[f"import {cls.__module__}"] = None
                # return f"{cls.__module__}.{str(h)}"

            imports[f"import {mod}"] = None
            return f"{mod}.{str(h)}"

    @classmethod
    def _proc_arg(cls, t: Type, imports: Dict[str, Any], fin_param: str, module: Optional[str] = None) -> str:
        ret_param = cls._build_hint(t, imports, module)
        args = typing.get_args(t)
        if is_optional(t):
            args = args[:-1]

        ret_params: List[str] = []
        for arg in args:
            ret_params.append(cls._proc_arg(arg, imports, fin_param, module))

        if len(ret_params) > 0:
            ret_param = f"{ret_param}[{', '.join(ret_params)}]"

        ret_param = fin_param + ret_param
        return ret_param

    @classmethod
    def _gen_client(cls) -> str:
        """Generate a client for the server

        Returns:
            str: The client Python code
        """

        fns = inspect.getmembers(cls, predicate=inspect.isfunction)
        methods = inspect.getmembers(cls, predicate=inspect.ismethod)
        fns.extend(methods)

        client_fns: List[str] = []
        import_statements: Dict[str, Any] = {}
        used_vars: Dict[str, Any] = {}
        possible_vars = "abcdefghijklmnopqrstuvwxyz"

        def build_default(o: Any, imports: Dict[str, Any]) -> str:
            if isinstance(o, str):
                return f"'{o}'"
            if type(o).__module__ == "builtins":
                return f"{o}"
            else:
                imports[f"import {o.__module__}"] = None
                return f"{type(o).__module__}.{o}"

        def build_param(name: str, _type: str) -> str:
            if _type != "":
                return f"{name}: {_type}"
            return f"{name}"

        def get_var() -> str:
            ret = possible_vars[len(used_vars)]
            used_vars[ret] = ""
            return ret

        def prep_serialize(
            param_name: str,
            t: Type,
            ser_lines: List[str],
            idt: str = "",
            is_args: bool = False,
            var_prefix: str = "_",
            union_call: bool = False,
        ) -> None:
            """Prep the objects to be serialized

            Args:
                param_name (str): Name of the parametr
                t (Type): Type of the parameter
                ser_lines (List[str]): Serialization lines
                idt (str, optional): Indentation. Defaults to "".
                is_args (bool, optional): Whether this is *args or **kwargs. Defaults to False.
            """

            _op = getattr(t, "to_dict", None)
            name = param_name

            ignore_line = ""
            if union_call:
                ignore_line = "# type: ignore"

            if is_type(t):
                logging.warning("types not yet supported as parameters")
                raise TypeNotSupportedError()

            if t == inspect._empty:
                raise ValueError(f"field '{param_name}' must by typed")

            elif callable(_op):
                ser_lines.append(indent(f"{name} = {name}.to_dict()  # type: ignore", idt))

            elif is_args:
                pass

            elif is_first_order(t):
                pass

            elif is_dict(t):
                args = get_args(t)
                if len(args) != 2:
                    raise ValueError(f"Dictionary must by typed: {name}")

                if is_first_order(args[1]):
                    return

                else:
                    ser_lines.append(indent(f"# code for dict arg: {t}", idt))
                    ser_lines.append(indent(f"_{name}_dict = {{}}", idt))
                    key = get_var() + "_key"
                    val = get_var() + "_val"
                    ser_lines.append(indent(f"for _{key}, _{val} in {name}.items():  {ignore_line}", idt))
                    prep_serialize(f"_{val}", args[1], ser_lines, idt + "    ")
                    ser_lines.append(indent(f"    _{name}_dict[_{key}] = _{val}  {ignore_line}", idt))
                    ser_lines.append(indent(f"{name} = _{name}_dict  # type: ignore", idt))
                    ser_lines.append(indent(f"# end dict: {t}", idt))
                    ser_lines.append("")

            elif is_list(t):
                args = get_args(t)
                if len(args) != 1:
                    raise SystemError(f"List must be typed: {ret}")

                if is_first_order(args[0]):
                    return

                else:
                    ser_lines.append(indent(f"# code for list arg: {t}", idt))
                    ser_lines.append(indent(f"_{name}_list = []", idt))
                    val = get_var() + "_val"
                    ser_lines.append(indent(f"for _{val} in {name}:  {ignore_line}", idt))
                    prep_serialize(f"_{val}", args[0], ser_lines, idt + "    ")
                    ser_lines.append(indent(f"    _{name}_list.append(_{val})", idt))
                    ser_lines.append(indent(f"{name} = _{name}_list  {ignore_line}", idt))
                    ser_lines.append(indent(f"# end list: {t}", idt))
                    ser_lines.append("")

            elif is_tuple(t):
                ser_lines.append(indent(f"# code for tuple: {t}", idt))
                args = get_args(t)
                ser_lines.append(indent(f"{name}_list: typing.List[typing.Any] = []", idt))
                for i, arg in enumerate(args):
                    ser_lines.append(indent(f"# code for tuple arg: {arg}", idt))
                    arg_name = name + f"_{i}"
                    ser_lines.append(indent(f"{arg_name} = {name}[{i}]  {ignore_line}", idt))
                    prep_serialize(arg_name, arg, ser_lines, idt)
                    ser_lines.append(indent(f"{name}_list.append({arg_name})", idt))
                    ser_lines.append(indent(f"# end tuple arg: {arg}", idt))
                    ser_lines.append("")
                ser_lines.append(indent(f"{name} = {name}_list  # type: ignore", idt))
                ser_lines.append(indent(f"# end tuple: {t}", idt))
                ser_lines.append("")

            elif t == NoneType:
                pass

            elif is_union(t):
                # TODO: make this fully recursive
                ser_lines.append(indent(f"# code for union: {t}", idt))
                args = typing.get_args(t)
                if len(args) == 2 and args[1] == NoneType:
                    # Handle optionals
                    args = (args[1], args[0])

                import_statements["from modelos.object.encoding import deep_isinstance"] = None
                for i, arg in enumerate(args):
                    if_line = "if"
                    if i > 0:
                        if_line = "elif"
                    arg_hint = cls._proc_arg(arg, import_statements, "")
                    ser_lines.append(indent(f"{if_line} deep_isinstance({name}, {arg_hint}):", idt))

                    len_ser = len(ser_lines)
                    prep_serialize(param_name, arg, ser_lines, idt + "    ", union_call=True)
                    len_ser_post = len(ser_lines)
                    if len_ser == len_ser_post:
                        ser_lines.append(indent("    pass", idt))
                ser_lines.append(indent("else:", idt))
                ser_lines.append(
                    indent(
                        '    raise ValueError("Do not know how to serialize " + '
                        + f"\"parameter '{name}' \" + f\"of type '{{type({name})}}'\")",
                        idt,
                    )
                )
                ser_lines.append(indent(f"# end union: {t}", idt))
                ser_lines.append("")

            elif is_enum(t):
                ser_lines.append(indent(f"# code for enum: {t}", idt))
                ser_lines.append(indent(f"{name} = {name}.value  # type: ignore", idt))
                ser_lines.append(indent(f"# end enum: {t}", idt))
                ser_lines.append("")

            elif t == typing.Any:
                # TODO: we should have a way of trying to serialize at runtime
                logging.warning(
                    "Use of Any type may result in serialization failures; object supplied to Any "
                    + "must be json serializable"
                )

            # TODO: need to handle the given dict types
            elif hasattr(t, "__dict__"):
                ser_lines.append(indent(f"# code for object: {t}", idt))
                ser_lines.append(indent(f"{name} = {name}.__dict__  # type: ignore", idt))
                if hasattr(t, "__annotations__"):
                    annotations = get_type_hints(t)
                    for nm, typ in annotations.items():
                        typ_hint = cls._proc_arg(typ, import_statements, "")

                        if is_first_order(typ):
                            continue
                        ser_lines.append(indent(f"{nm}: {typ_hint} = {name}['{nm}']  # type: ignore", idt))
                        prep_serialize(nm, typ, ser_lines, idt)
                        ser_lines.append(indent(f"{name}['{nm}'] = {nm}  # type: ignore", idt))

                ser_lines.append(indent(f"# end object: {t}", idt))
                ser_lines.append("")

            else:
                raise ValueError(f"Do not know how to serialize param '{name}' of type: {t}")

        def proc_return(
            ret: Type,
            ser_lines: List[str],
            working_module: str,
            idt: str = "",
            jdict_name: str = "_jdict",
            ret_name: str = "_ret",
            ret_union: bool = False,
        ) -> None:
            """Process the return serialization

            Args:
                ret (Type): The return type
                ser_lines (List[str]): The lines of code to use for serialization
                working_module (str): The working module
                idt (str, optional): Indent to use. Defaults to ""
                jdict_name (str, optional): Name of the proverbial '_jdict' param, this may change when
                    recursing. Defaults to "_jdict".
                ret_name (str, optional): Name of the _ret param, this may change when recursing. Defaults to "_ret"
                ret_union (bool, optional): Whether this is a recursive pass in a nested Union_. Defaults to False.
            """

            ret_op = getattr(ret, "from_dict", None)
            ret_type = cls._build_hint(ret, import_statements, working_module)
            ret_hint = cls._proc_arg(ret, import_statements, "", working_module)

            if is_type(ret):
                logging.warning("types not yet supported as parameters")
                raise TypeNotSupportedError()

            if ret == NoneType:
                ser_lines.append(indent(f"{ret_name} = {jdict_name}", idt))
            elif callable(ret_op):
                ser_lines.append(indent(f"{ret_name} = {ret_type}.from_dict({jdict_name})", idt))
            elif is_first_order(ret):
                ser_lines.append(indent(f"{ret_name} = {jdict_name}", idt))
            elif is_list(ret):
                args = get_args(ret)
                if len(args) == 0:
                    raise SystemError(f"List must be typed: {ret}")
                ser_lines.append(indent(f"# code for arg: {ret}", idt))
                if is_first_order(args[0]):
                    ser_lines.append(indent(f"{ret_name} = {jdict_name}", idt))
                else:
                    val = get_var() + "_val"
                    ret_var = "_" + get_var()
                    ser_lines.append(indent(f"{ret_var}_list: {ret_type} = []", idt))
                    ser_lines.append(indent(f"for _{val} in {jdict_name}:", idt))
                    proc_return(args[0], ser_lines, working_module, idt + "    ", f"_{val}", ret_var)
                    ser_lines.append(indent(f"    {ret_var}_list.append({ret_var})", idt))
                    ser_lines.append(indent(f"{ret_name} = {ret_var}_list", idt))

                ser_lines.append(indent(f"# end list: {ret}", idt))
                ser_lines.append("")
            elif is_dict(ret):
                args = get_args(ret)
                if len(args) != 2:
                    raise SystemError(f"Dict must be typed: {ret}")

                ser_lines.append(indent(f"# code for arg: {ret}", idt))
                if not ret_union:
                    import_statements["from modelos.object.encoding import json_is_type_match"] = None
                    ser_lines.append(indent(f"if not json_is_type_match({ret_hint}, {jdict_name}):", idt))
                    ser_lines.append(
                        indent(f"    raise ValueError('JSON returned does not match type: {ret_hint}')", idt)
                    )

                if is_first_order(args[1]):
                    ser_lines.append(indent(f"{ret_name} = {jdict_name}", idt))

                else:
                    ret_var = "_" + get_var()
                    ser_lines.append(indent(f"{ret_var}_dict: {ret_hint} = {{}}", idt))
                    key = get_var() + "_key"
                    val = get_var() + "_val"
                    ser_lines.append(indent(f"for _{key}, _{val} in {jdict_name}.items():", idt))
                    proc_return(args[1], ser_lines, working_module, idt + "    ", f"_{val}", ret_var)
                    ser_lines.append(indent(f"    {ret_var}_dict[_{key}] = {ret_var}  # type: ignore", idt))
                    ser_lines.append(indent(f"{ret_name} = {ret_var}_dict", idt))

                ser_lines.append(indent(f"# end dict: {ret}", idt))
                ser_lines.append("")

            elif is_tuple(ret):
                args = get_args(ret)

                ser_lines.append(indent(f"# code for tuple: {ret}", idt))
                ser_lines.append(indent(f"{ret_name}_tuple: {ret_hint} = ()  # type: ignore", idt))
                ser_lines.append("")
                for i, arg in enumerate(args):
                    ser_lines.append(indent(f"# code for tuple arg: {arg}", idt))
                    ret_var = "_" + get_var()
                    ser_lines.append(indent(f"_v_{i} = {jdict_name}[{i}]", idt))
                    proc_return(arg, ser_lines, working_module, idt, f"_v_{i}", ret_var)
                    ser_lines.append(indent(f"{ret_name}_tuple = {ret_name}_tuple + ({ret_var},)  # type: ignore", idt))
                    ser_lines.append(indent(f"# end tuple arg: {arg}", idt))
                    ser_lines.append("")
                ser_lines.append(indent(f"{ret_name} = {ret_name}_tuple  # type: ignore", idt))
                ser_lines.append(indent(f"# end tuple: {ret}", idt))
                ser_lines.append("")

            elif ret == typing.Any:
                logging.warning(
                    "Use of Any type may yield unexpected results, "
                    + "whatever object is sent to Any it must be json serializable"
                )
                ser_lines.append(indent(f"{ret_name} = {jdict_name}", idt))

            elif is_union(ret):
                args = get_args(ret)
                if len(args) == 0:
                    raise SystemError("args for iterable are None")
                ser_lines.append(indent(f"# code for union: {ret}", idt))
                import_statements["from modelos.object.encoding import json_is_type_match"] = None
                for i, arg in enumerate(args):
                    if_line = "if"
                    if i > 0:
                        if_line = "elif"

                    arg_hint = cls._proc_arg(arg, import_statements, "", working_module)
                    ser_lines.append(indent(f"{if_line} json_is_type_match({arg_hint}, {jdict_name}):", idt))
                    proc_return(arg, ser_lines, working_module, "    ", jdict_name=jdict_name, ret_union=True)

                ser_lines.append(indent("else:", idt))
                ser_lines.append(
                    indent(f"    raise ValueError(f'Unable to deserialize return value: {{type({jdict_name})}}')", idt)
                )
                ser_lines.append(indent(f"# end union: {ret}", idt))
                ser_lines.append("")

            elif is_enum(ret):
                ser_lines.append(indent(f"# code for enum: {ret}", idt))
                ser_lines.append(indent(f"{ret_name} = {ret_type}({jdict_name})", idt))
                ser_lines.append(indent(f"# end enum: {ret}", idt))
                ser_lines.append("")

            elif hasattr(ret, "__annotations__"):
                annots = get_type_hints(ret)
                ser_lines.append(indent(f"# code for object: {ret}", idt))
                import_statements["from modelos.object.encoding import json_is_type_match"] = None
                ser_lines.append(indent(f"if not json_is_type_match({ret_type}, {jdict_name}):", idt))
                ser_lines.append(indent(f"    raise ValueError('JSON returned does not match type: {ret_hint}')", idt))
                ser_lines.append(indent(f"{ret_name}_obj = object.__new__({ret_type})  # type: ignore", idt))
                for nm, typ in annots.items():
                    nm_var = f"_{nm}"
                    ser_lines.append(indent(f"{nm_var} = {jdict_name}['{nm}']", idt))
                    if not is_first_order(typ):
                        proc_return(typ, ser_lines, working_module, idt, jdict_name=nm_var, ret_name=f"_{nm}")

                    ser_lines.append(indent(f"setattr({ret_name}_obj, '{nm}', _{nm})", idt))
                    ser_lines.append("")

                ser_lines.append(indent(f"{ret_name} = {ret_name}_obj", idt))
                ser_lines.append(indent(f"# end object: {ret}", idt))
                ser_lines.append("")

            else:
                raise ValueError(f"Do no know how to deserialize return param {ret_hint}")

            return

        for name, fn in fns:
            # print("\n=====\nclient fn name: ", name)
            params: List[str] = []
            used_vars = {}

            root_cls = cls._get_class_that_defined_method(fn)
            if not issubclass(root_cls, Object):
                continue

            if hasattr(fn, "local"):
                continue

            if name.startswith("_") and name != "__init__":
                continue

            sig = signature(fn, eval_str=True, follow_wrapped=True)

            fin_sig = f"def {name}("
            fin_params: List[str] = []

            if isinstance(fn, types.MethodType):
                fin_params.append("self")

            def proc_parameter(param: Parameter, imports: Dict[str, Any], module: Optional[str] = None):
                nonlocal fin_params

                name = param.name
                if str(param).startswith("*"):
                    name = f"*{param.name}"
                if str(param).startswith("**"):
                    name = f"**{param.name}"

                fin_param = build_param(name, cls._proc_arg(param.annotation, imports, "", module))

                # TODO: handle Union
                if param.default is not param.empty:
                    if isinstance(param.default, str):
                        fin_param += f" = '{param.default}'"
                    else:
                        fin_param += f" = {build_default(param.default, imports)}"

                fin_params.append(fin_param)

            super_params: List[str] = []

            def proc_init(param: Parameter):
                name = param.name
                if name == "self":
                    return
                super_params.append(f"{name}={name}")

            for param in sig.parameters:
                try:
                    proc_parameter(sig.parameters[param], import_statements, fn.__module__)
                except TypeNotSupportedError:
                    logging.warning(f"function '{name}' will be bypassed as it contains unsupported types")
                    continue
                if name == "__init__":
                    proc_init(sig.parameters[param])

            if name == "__init__":
                fin_params.append("**kwargs")

            params_joined = ", ".join(fin_params)
            fin_sig += params_joined
            fin_sig += ")"

            super_joined = ", ".join(super_params)

            param_ser_lines: List[str] = []

            for k in sig.parameters:
                if k == "self":
                    continue

                parameter = sig.parameters[k]
                try:
                    prep_serialize(k, parameter.annotation, param_ser_lines, "", str(parameter).startswith("*"))
                except TypeNotSupportedError:
                    logging.warning(f"function '{name}' will be bypassed as it contains unsupported types")
                    continue
                params.append(f"'{k}': {k}")
            hints = get_type_hints(fn)

            if "return" not in hints:
                logging.warning(f"function '{name}' has no return parameter, skipping generation")
                continue

            ret = hints["return"]
            orig_ret = ret

            if ret == typing.Type or (hasattr(ret, "__origin__") and ret.__origin__ == type):
                logging.warning("types not yet supported as parameters")
                continue

            # ser_line = "if hasattr(ret, '__dict__'): ret = ret.__dict__"
            is_iterable = is_iterable_cls(ret)
            if is_iterable:
                args = get_args(ret)
                if len(args) == 0:
                    raise SystemError("args for iterable are None")
                if len(args) > 1:
                    raise ValueError("Iterable with args greater than one not currently supported")

                ret = args[0]

            # handle type vars
            if hasattr(ret, "__bound__"):
                ret = eval(ret.__bound__.__forward_arg__)
                orig_ret = ret

            # we need to handle generic types here
            fin_param = cls._proc_arg(orig_ret, import_statements, "", fn.__module__)
            fin_sig += f" -> {fin_param}:"
            if inspect.ismethod(fn):
                fin_sig += " # type: ignore"

            ret_ser_lines: List[str] = []

            try:
                proc_return(ret, ret_ser_lines, fn.__module__)
            except TypeNotSupportedError:
                logging.warning(f"function '{name}' will be bypassed as it contains unsupported types")
                continue

            ret_arg_hint = cls._proc_arg(ret, import_statements, "", fn.__module__)

            params_joined = ", ".join(params)

            param_ser_lines_joined = ""
            for line in param_ser_lines:
                line += "\n"
                param_ser_lines_joined += indent(line, "        ")

            doc = ""
            if hasattr(fn, "__doc__") and fn.__doc__ is not None:
                doc = f'"""{fn.__doc__}"""'

            if name == "__init__":
                client_fn = f"""
    {fin_sig}
        {doc}
        ClientOpts = OptsBuilder[Opts].build(self.__class__)
        opts = ClientOpts({super_joined})
        super().__init__(opts=opts, **kwargs)
                """

            elif is_iterable:
                import_statements["import socket"] = None
                import_statements["from websocket import create_connection"] = None

                ret_ser_lines_joined = ""
                for line in ret_ser_lines:
                    line += "\n"
                    ret_ser_lines_joined += indent(line, "                ")

                client_fn = f"""
    {fin_sig}
        {doc}
        _server_addr = f"{{self.pod_name}}.pod.{{self.pod_namespace}}.kubernetes:{{self.server_port}}"

        _sock = socket.create_connection((f"{{self.pod_name}}.pod.{{self.pod_namespace}}.kubernetes", self.server_port))
{param_ser_lines_joined}

        _encoded = parse.urlencode({{"data": json.dumps({{{params_joined}}})}})
        _ws = create_connection(
            f"ws://{{_server_addr}}/{name}?{{_encoded}}",
            header=[f"client-uuid: {{str(self.uid)}}"],
            socket=_sock,
        )
        try:
            while True:
                code, _data = _ws.recv_data()
                if code == 8:
                    break
                _jdict = json.loads(_data)
                if 'value' in _jdict:
                    _jdict = _jdict['value']
                _ret: {ret_arg_hint}
{ret_ser_lines_joined}
                yield _ret

        except Exception as e:
            print("stream exception: ", e)
            raise e
"""
            else:
                ret_ser_lines_joined = ""
                for line in ret_ser_lines:
                    line += "\n"
                    ret_ser_lines_joined += indent(line, "        ")

                client_fn = f"""
    {fin_sig}
        {doc}
{param_ser_lines_joined}
        _params = json.dumps({{{params_joined}}}).encode("utf8")
        _headers = {{"content-type": "application/json", "client-uuid": str(self.uid)}}
        _req = request.Request(
            f"{{self.server_addr}}/{name}",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)

        if _jdict is None:
            raise ValueError('recieved invalid response from server, check server logs')

        if 'value' in _jdict:
            _jdict = _jdict['value']

        _ret: {fin_param}
{ret_ser_lines_joined}
        return _ret
            """
            client_fns.append(client_fn)

        # you are here
        # We need to do a conditional import of __main__ based on whether the resource file is __main__
        imports_joined = "\n".join(import_statements.keys())
        client_fns_joined = "".join(client_fns)

        server_uri = img_id(strategy=RemoteSyncStrategy.IMAGE, tag_prefix=f"{cls.short_name().lower()}-")

        m = importlib.import_module(cls.__module__)
        if m.__file__ is None:
            raise ValueError("could not find the path of the executing script, if you hit this please create an issue")
        filename = os.path.basename(m.__file__)
        mod_name = filename.split(".")[0]
        client_file = f"""
# This file was generated by ModelOS
from urllib import request, parse
import json
import os
from typing import Type
from pathlib import Path

from lib_programname import get_path_executed_script

from modelos import Client
from modelos.object.opts import OptsBuilder, Opts
{imports_joined}

if get_path_executed_script() == Path(os.path.dirname(__file__)).joinpath(Path('{filename}')):
    import __main__ as {mod_name}  # type: ignore # noqa

class {cls.__name__}Client(Client):
    \"""A resource client for {cls.__name__}\"""

    uri: str = "{server_uri}"

{client_fns_joined}

    def _super_init(self, uri: str) -> None:
        super().__init__(uri)

    @classmethod
    def from_uri(cls: Type["{cls.__name__}Client"], uri: str) -> "{cls.__name__}Client":
        c = cls.__new__(cls)
        c._super_init(uri)
        return c
        """

        return client_file

    @classmethod
    def _client_file_name(cls) -> str:
        return f"{cls.__name__.lower()}_client"

    @classmethod
    def _client_filepath(cls) -> str:
        filename = f"{cls._client_file_name()}.py"
        dir = os.path.dirname(os.path.abspath(inspect.getfile(cls)))
        filepath = os.path.join(dir, filename)
        return filepath

    @classmethod
    def _write_client_file(cls) -> str:
        """Generate and write the client file next to the current one

        Returns:
            str: The filepath
        """
        filepath = cls._client_filepath()
        logging.info(f"writing client file to {filepath}")
        with open(filepath, "w", encoding="utf-8") as f:
            client_code = cls._gen_client()
            client_code = removestar.fix_code(client_code, file=filepath)
            client_code = isort.code(client_code)
            client_code = format_str(client_code, mode=FileMode())
            f.write(client_code)
            unimport_main.run(["-r", filepath])
        return filepath

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return
