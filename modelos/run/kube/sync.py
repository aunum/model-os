from typing import Optional, List, Union
from tempfile import TemporaryFile
import tarfile
import logging
import os

from kubernetes.client import (
    CoreV1Api,
    V1Pod,
    V1PodSpec,
    V1Container,
    V1ObjectMeta,
)
from kubernetes.client.rest import ApiException
from kubernetes import config
from kubernetes.stream import stream

from modelos.config import RemoteSyncStrategy
from modelos.virtual.container.id import ImageID
from modelos.scm import SCM
from modelos.env.image.build import find_or_build_img, REPO_ROOT
from modelos.run.kube.pod_util import (
    REPO_SHA_LABEL,
    SYNC_SHA_LABEL,
    ENV_SHA_LABEL,
    wait_for_pod_running,
)


def copy_file_to_pod(
    src_path: Union[List[str], str],
    pod_name: str,
    namespace: str = "default",
    base_path: Optional[str] = None,
    restart: bool = True,
    label: bool = False,
    core_v1_api: Optional[CoreV1Api] = None,
    scm: Optional[SCM] = None,
):
    """Copy the given filepath into the pod

    Args:
        src_path (List[str], str): Local filepath(s) to copy
        pod_name (str): name of the pod
        namespace (str): namespace of the pod. Defaults to 'default'.
        base_path (Optional[str], optional): base path to prepend to the file(s)
        restart (bool, optional): Whether to restart the container after copying. Defaults to True.
        label (bool, optional): Whether the pod should be labeled with the updated sha
        core_v1_api (Optional[CoreV1Api], optional): client to use. Will create a default one if none provided
        scm (Optional[SCM], optional): scm to use. Will create a default on if none provided
    """

    # this uses https://github.com/kubernetes-client/python/blob/master/examples/pod_exec.py and
    # https://github.com/kubernetes-client/python/commit/5cb61bba23671704a8b7562a5b59c9f2eba1c30f
    # https://github.com/prafull01/Kubernetes-Utilities/blob/master/kubectl_cp_as_python_client.py
    if core_v1_api is None:
        config.load_kube_config()
        core_v1_api = CoreV1Api()

    if scm is None:
        scm = SCM()

    try:
        exec_command = ["tar", "xvf", "-", "-C", "/"]
        api_response = stream(
            core_v1_api.connect_get_namespaced_pod_exec,
            pod_name,
            namespace,
            command=exec_command,
            stderr=True,
            stdin=True,
            stdout=True,
            tty=False,
            _preload_content=False,
        )

        with TemporaryFile() as tar_buffer:
            with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
                if isinstance(src_path, List):
                    for item in src_path:
                        if base_path is None:
                            tar.add(item)
                        else:
                            tar.add(item, os.path.join(base_path, item))
                else:
                    if base_path is None:
                        tar.add(src_path)
                    else:
                        tar.add(src_path, os.path.join(base_path, src_path))

            tar_buffer.seek(0)
            commands = []
            commands.append(tar_buffer.read())

            while api_response.is_open():
                api_response.update(timeout=1)
                if api_response.peek_stdout():
                    print("STDOUT: %s" % api_response.read_stdout())
                if api_response.peek_stderr():
                    print("STDERR: %s" % api_response.read_stderr())
                if commands:
                    c = commands.pop(0)
                    try:
                        # do we need to decode?!
                        # api_response.write_stdin(c.decode())
                        api_response.write_stdin(c)
                    except Exception as e:
                        logging.error(f"unable to copy files to pod: {e}")
                        raise
                else:
                    break
            api_response.close()

    except ApiException as e:
        print("Exception when copying file to the pod%s \n" % e)

    if label:
        pod = V1Pod(metadata=V1ObjectMeta(labels={SYNC_SHA_LABEL: scm.sha()}))
        core_v1_api.patch_namespaced_pod(pod_name, namespace, pod)

    if restart:
        # restart the container
        # kubectl exec -it [POD_NAME] -c [CONTAINER_NAME] -- /bin/sh -c "kill 1"
        # TODO: add container name, but how?
        exec_command = [
            "/bin/sh",
            "-c",
            "kill 1",
        ]
        stream(
            core_v1_api.connect_get_namespaced_pod_exec,
            pod_name,
            namespace,
            command=exec_command,
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
        )

    return


def _update_pod_img(
    pod_name: str,
    namespace: str,
    sync_strategy: RemoteSyncStrategy,
    container_name: str,
    scm: Optional[SCM] = None,
    core_v1_api: Optional[CoreV1Api] = None,
) -> ImageID:
    """Update the pod image

    Args:
        pod_name (str): name of the pod
        namespace (str): namespace of the pod
        sync_strategy (RemoteSyncStrategy): strategy to sync by
        container_name (str): name of the container to sync to
        scm (Optional[SCM], optional): scm to use. Defaults to None.
        core_v1_api (Optional[CoreV1Api], optional): client to use. Defaults to None.

    Returns:
        ImageID: ID of the new image
    """
    if core_v1_api is None:
        config.load_kube_config()
        core_v1_api = CoreV1Api()

    if scm is None:
        scm = SCM()

    pod_patch = V1Pod()
    image_id = find_or_build_img(scm=scm, sync_strategy=sync_strategy)

    pod_spec = V1PodSpec(containers=[V1Container(name=container_name, image=str(image_id))])
    meta = V1ObjectMeta(labels={ENV_SHA_LABEL: scm.env_sha(), REPO_SHA_LABEL: scm.sha()})

    pod_patch.spec = pod_spec
    pod_patch.metadata = meta

    logging.info(f"patching pod {pod_name}")
    core_v1_api.patch_namespaced_pod(pod_name, namespace, pod_patch)
    return image_id


def sync_repo_to_pod(
    pod_name: str,
    namespace: str,
    sync_strategy: RemoteSyncStrategy,
    container_name: str,
    scm: Optional[SCM] = None,
    core_v1_api: Optional[CoreV1Api] = None,
) -> None:
    if core_v1_api is None:
        config.load_kube_config()
        core_v1_api = CoreV1Api()

    if scm is None:
        scm = SCM()

    logging.info("checking if pod is up to date")
    pod: V1Pod = core_v1_api.read_namespaced_pod(pod_name, namespace)
    meta: V1ObjectMeta = pod.metadata

    if sync_strategy == RemoteSyncStrategy.IMAGE:
        repo_sha = meta.labels[REPO_SHA_LABEL]
        if repo_sha != scm.sha():
            logging.info("updating image")
            _update_pod_img(pod_name, namespace, sync_strategy, container_name, scm=scm, core_v1_api=core_v1_api)
        else:
            logging.info("pod is up to date")
        return

    if ENV_SHA_LABEL in meta.labels:
        env_sha = meta.labels[ENV_SHA_LABEL]
        if env_sha != scm.env_sha():
            logging.info("rebuilding container because environment has changed")
            image_id = _update_pod_img(
                pod_name, namespace, sync_strategy, container_name, scm=scm, core_v1_api=core_v1_api
            )

            running = wait_for_pod_running(pod_name, namespace, core_v1_api=core_v1_api)
            if not running:
                raise SystemError(f"pod {pod_name} never started running")
            new_pod: V1Pod = core_v1_api.read_namespaced_pod(pod_name, namespace)

            container_found = False
            for container in new_pod.spec.containers:
                if container.name == container_name:
                    container_found = True
                    if container.image != str(image_id):
                        raise SystemError("image was not updated")
            if not container_found:
                raise SystemError("container was not found")

            logging.info(f"pod is running '{pod_name}'")
        else:
            logging.info("env sha is up to date")
    else:
        logging.warning("env sha not in labels")

    if SYNC_SHA_LABEL in meta.labels:
        sync_sha = meta.labels[SYNC_SHA_LABEL]
        if sync_sha != scm.sha():
            logging.info("syncing files to pod")
            copy_file_to_pod(
                scm.all_files(absolute_paths=True),
                pod_name,
                namespace=namespace,
                base_path=REPO_ROOT.lstrip("/"),
                label=True,
                core_v1_api=core_v1_api,
                scm=scm,
            )
            logging.info("files copied to pod")
        else:
            logging.info("sync sha is up to date")
    else:
        logging.info("syncing archive to pod for first time")
        logging.info("syncing files to pod")
        copy_file_to_pod(
            scm.all_files(absolute_paths=True),
            pod_name,
            namespace=namespace,
            base_path=REPO_ROOT.lstrip("/"),
            label=True,
            core_v1_api=core_v1_api,
            scm=scm,
        )
        logging.info("files copied to pod")
    return
