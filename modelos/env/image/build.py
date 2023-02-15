from typing import Optional, Dict, Any, List
import os
import logging
import yaml
import sys
import subprocess
import hashlib

from docker import APIClient
from rich.progress import Progress, TaskID

from modelos.virtual.container.file import Dockerfile, write_dockerfile, MDL_DOCKERFILE_NAME
from modelos.virtual.container.id import ImageID
from modelos.config import Config, RemoteSyncStrategy
from modelos.virtual.container.client import default_socket
from modelos.scm import SCM
from modelos.util.rootpath import load_conda_yaml

TOMLDict = Dict[str, Any]

REPO_ROOT = "/app"

DEFAULT_PORT = 8000


def client_hash(client_filepath: str) -> str:
    with open(client_filepath, "rb") as f:
        cli_file = f.read()

        h = hashlib.new("sha256")
        if len(cli_file) == 0:
            raise ValueError("could not calculate hash of client file")

        h.update(cli_file)
        cli_hash = h.hexdigest()
        return cli_hash


def img_tag(
    strategy: RemoteSyncStrategy,
    scm: Optional[SCM] = None,
    tag_prefix: Optional[str] = None,
    client_filepath: Optional[str] = None,
) -> str:
    """Generate a repo hash by sync strategy

    Args:
        strategy (RemoteSyncStrategy): Strategy to use
        scm (SCM, optional): SCM to use. Defaults to None.
        tag_prefix (str, optional): Tag prefix to use. Defaults to None.
        client_filepath (str, optional): Client filepath to use for versioning. Defaults to None.

    Returns:
        str: a SHA256 hash
    """
    if scm is None:
        scm = SCM()

    hash = ""
    if strategy == RemoteSyncStrategy.IMAGE:
        hash = scm.sha()
    elif strategy == RemoteSyncStrategy.CONTAINER:
        hash = scm.base_sha()
    else:
        raise ValueError("uknown sync strategy")

    if client_filepath:
        # TODO: do proper client versioning

        cli_hash = client_hash(client_filepath)
        hash = hash + "-" + cli_hash

    if tag_prefix:
        return tag_prefix + hash

    return hash


def img_id(
    strategy: RemoteSyncStrategy,
    image_repo: Optional[str] = None,
    tag: Optional[str] = None,
    tag_prefix: Optional[str] = None,
    scm: Optional[SCM] = None,
    client_filepath: Optional[str] = None,
) -> ImageID:
    """Generate ID for an image based on the environment

    Args:
        strategy (RemoteSyncStrategy): Sync strategy to use
        image_repo (Optional[str], optional): Image repository to use. Defaults to None.
        tag (Optional[str], optional): Tag to use. Defaults to None.
        tag_prefix (Optional[str], optional): Tag prefix to use. Defaults to None.
        scm (Optional[SCM], optional): SCM to use. Defaults to None.
        client_filepath (Optional[str], optional): Client file to use for versioning. Defaults to None

    Returns:
        ImageID: An ImageID
    """
    if image_repo is None:
        cfg = Config()
        if cfg.image_repo is None:
            raise ValueError("must supply image repo")
        image_repo = cfg.image_repo

    if scm is None:
        scm = SCM()

    if tag is None:
        tag = img_tag(strategy, scm, tag_prefix=tag_prefix, client_filepath=client_filepath)

    id = ImageID.from_ref(image_repo)
    if id.tag is not None:
        raise ValueError("image repo should not have tag supplied")
    id.tag = tag
    return id


def build_dockerfile(
    base_image: Optional[str] = None,
    dev_dependencies: bool = False,
    scm: Optional[SCM] = None,
    cfg: Optional[Config] = None,
    command: Optional[List[str]] = None,
    sync_strategy: Optional[RemoteSyncStrategy] = None,
) -> Dockerfile:
    """Build a Containerfile for the repo

    Args:
        base_image (Optional[str], optional): base image to use. Defaults to None.
        dev_dependencies (bool, optional): install dev dependencies. Defaults to False.
        scm (SCM, optional): SCM to use. Defaults to None.
        cfg (Config, optional): Config to use. Defaults to None.
        command (List[str], optional): Optional command to add to the container

    Returns:
        Dockerfile: A Dockerffile
    """
    if scm is None:
        scm = SCM()

    if cfg is None:
        cfg = Config()

    if sync_strategy is None:
        sync_strategy = cfg.remote_sync_strategy

    rel_path = scm.rel_project_path()
    project_root = REPO_ROOT
    if rel_path != "./" and rel_path != ".":
        project_root = os.path.join(REPO_ROOT, rel_path)
    if project_root[-1] != "/":
        project_root = project_root + "/"

    logging.info(f"using project root: {project_root}")

    dockerfile: Optional[Dockerfile] = None
    if scm.is_poetry_project():
        logging.info("building image for poetry project")
        if sync_strategy == RemoteSyncStrategy.IMAGE:
            logging.info("building poetry dockerfile")
            dockerfile = build_poetry_dockerfile(scm.load_pyproject(), project_root, base_image, dev_dependencies)
        elif sync_strategy == RemoteSyncStrategy.CONTAINER:
            logging.info("building poetry env dockerfile")
            dockerfile = build_poetry_base_dockerfile(scm.load_pyproject(), project_root, base_image, dev_dependencies)
        else:
            raise SystemError("unknown sync strategy")

    elif scm.is_pip_project():
        logging.info("building image for pip project")
        if sync_strategy == RemoteSyncStrategy.IMAGE:
            dockerfile = build_pip_containerfile(project_root, base_image)
        elif sync_strategy == RemoteSyncStrategy.CONTAINER:
            dockerfile = build_pip_base_containerfile(project_root, base_image)
        else:
            raise SystemError("unknown sync strategy")

    elif scm.is_conda_project():
        logging.info("building image for conda project")
        if sync_strategy == RemoteSyncStrategy.IMAGE:
            dockerfile = build_conda_containerfile(project_root, base_image)
        elif sync_strategy == RemoteSyncStrategy.CONTAINER:
            dockerfile = build_conda_base_containerfile(project_root, base_image)
        else:
            raise SystemError("unknown sync strategy")

    if dockerfile is None:
        raise ValueError("Cannot build containterfile due to unknown project type")

    if command is not None:
        dockerfile.cmd(command)

    return dockerfile


def _add_repo_files(
    dockerfile: Dockerfile,
    scm: Optional[SCM] = None,
) -> Dockerfile:
    """Build a Dockerile for a Poetry project

    Args:
        dockerfile (Dockerfile): Dockerfile to add to
        scm (SCM, optional): SCM to use. Defaults to None.

    Returns:
        Dockerfile: A Dockerfile
    """
    if scm is None:
        scm = SCM()

    # Fun stuff here because we don't want to mess with .dockerignore, exclude patterns
    # will be added soon https://github.com/moby/moby/issues/15771
    pkgs: Dict[str, List[str]] = {}
    for fp in scm.all_files():
        dir = os.path.dirname(fp)
        if dir in pkgs:
            pkgs[dir].append(fp)
        else:
            pkgs[dir] = [fp]

    for pkg, files in pkgs.items():
        if pkg != "":
            dockerfile.copy(files, os.path.join(f"{REPO_ROOT}/", pkg + "/"))
        else:
            dockerfile.copy(files, os.path.join(f"{REPO_ROOT}/"))

    # NOTE: there is likely a better way of doing this; copying the .git directory
    # with the tar sync was causing errors, and it is needed for the algorithms to
    # work currently
    dockerfile.copy(".git", f"{REPO_ROOT}/.git/")

    return dockerfile


def build_poetry_base_dockerfile(
    pyproject_dict: Dict[str, Any],
    project_root: str,
    base_image: Optional[str] = None,
    dev_dependencies: bool = False,
    scm: Optional[SCM] = None,
) -> Dockerfile:
    """Build a Dockerfile for a Poetry project

    Args:
        pyproject_dict (Dict[str, Any]): a parsed pyproject file
        project_root (str): Root of the python project
        base_image (str, optional): base image to use. Defaults to None.
        dev_dependencies (bool, optional): whether to install dev dependencies. Defaults to False.
        scm (SCM, optional): SCM to use. Defaults to None.

    Returns:
        Dockerfile: A Dockerfile
    """
    if scm is None:
        scm = SCM()

    # check for poetry keys
    try:
        pyproject_dict["tool"]["poetry"]["dependencies"]
    except KeyError:
        raise ValueError("no poetry.tool.dependencies section found in pyproject.toml")

    dockerfile = Dockerfile()

    # find base image
    if base_image is None:
        try:
            info = sys.version_info
            dockerfile.from_(f"python:{info.major}.{info.minor}.{info.micro}-slim")
        except KeyError:
            raise ValueError("could not determine python version")
    else:
        dockerfile.from_(base_image)

    dockerfile.env("PYTHONUNBUFFERED", "1")
    dockerfile.env("PYTHONDONTWRITEBYTECODE", "1")
    dockerfile.env("PIP_NO_CACHE_DIR", "off")
    dockerfile.env("PIP_DISABLE_PIP_VERSION_CHECK", "on")
    dockerfile.env("POETRY_NO_INTERACTION", "1")
    # dockerfile.env("POETRY_VIRTUALENVS_CREATE", "false")

    dockerfile.env("PYTHONPATH", f"${{PYTHONPATH}}:{REPO_ROOT}:{project_root}")

    # apt install -y libffi-dev
    dockerfile.run("apt update && apt install -y watchdog git curl")
    dockerfile.run("pip install poetry==1.2.0 && poetry --version")
    # dockerfile.run("pip uninstall -y setuptools && pip install setuptools")

    dockerfile.workdir(project_root)
    rel_proj_root = scm.rel_project_path()

    dockerfile.copy(
        f"{os.path.join(rel_proj_root, 'poetry.lock')} {os.path.join(rel_proj_root, 'pyproject.toml')}",
        f"{project_root}",
    )
    # dockerfile.run("poetry run python -m pip install --upgrade setuptools")

    if dev_dependencies:
        dockerfile.run("poetry install --no-ansi --no-root")
    else:
        dockerfile.run("poetry install --no-ansi --no-root --only main")

    dockerfile.expose(DEFAULT_PORT)

    return dockerfile


def build_poetry_dockerfile(
    pyproject_dict: Dict[str, Any],
    project_root: str,
    base_image: Optional[str] = None,
    dev_dependencies: bool = False,
    scm: Optional[SCM] = None,
) -> Dockerfile:
    """Build a Containerfile for a Poetry project

    Args:
        pyproject_dict (Dict[str, Any]): a parsed pyproject file
        project_root (str): Root of the python project
        base_image (str, optional): base image to use. Defaults to None.
        dev_dependencies (bool, optional): whether to install dev dependencies. Defaults to False.
        scm (SCM, optional): SCM to use. Defaults to None.

    Returns:
        Dockerfile: A Containerfile
    """
    if scm is None:
        scm = SCM()

    dockerfile = build_poetry_base_dockerfile(pyproject_dict, project_root, base_image, dev_dependencies, scm)
    dockerfile = _add_repo_files(dockerfile, scm)

    return dockerfile


def build_conda_base_containerfile(
    project_root: str, base_image: Optional[str] = None, scm: Optional[SCM] = None
) -> Dockerfile:
    """Build a base Containerfile for a Conda project

    Args:
        project_root (str): Root of project
        base_image (Optional[str], optional): Base image to use. Defaults to None.
        scm (Optional[SCM], optional): SCM to use. Defaults to None.

    Returns:
        Dockerfile: A Containerfile
    """
    if scm is None:
        scm = SCM()

    dockerfile = Dockerfile()

    # find base image
    if base_image is None:
        try:
            out = subprocess.check_output(["conda", "--version"])
            conda_ver = str(out).split(" ")
            if len(conda_ver) != 2:
                raise ValueError(f"could not determine conda version from: {conda_ver}")
            img = f"continuumio/miniconda:{conda_ver[1]}"
            logging.info(f"using base image: {img}")
            dockerfile.from_(img)
        except KeyError:
            logging.warn("could not determine conda version, trying latest")
            dockerfile.from_("continuumio/miniconda:latest")
    else:
        dockerfile.from_(base_image)

    # this needs to be project_root
    dockerfile.env("PYTHONPATH", f"${{PYTHONPATH}}:{REPO_ROOT}:{project_root}")

    dockerfile.run("apt update && apt install -y watchdog git curl")

    dockerfile.workdir(project_root)
    rel_proj_root = scm.rel_project_path()
    dockerfile.copy(f"{os.path.join(rel_proj_root, 'environment.yml')}", f"{project_root}")

    conda_yaml = load_conda_yaml()
    if "name" not in conda_yaml:
        raise ValueError("cannot find 'name' in environment.yml")

    env_name = conda_yaml["name"]

    # https://stackoverflow.com/questions/55123637/activate-conda-environment-in-docker
    dockerfile.shell(["conda", "run", "--no-capture-output", "-n", env_name, "/bin/bash", "-c"])

    dockerfile.expose(DEFAULT_PORT)

    return dockerfile


def build_conda_containerfile(
    project_root: str, base_image: Optional[str] = None, scm: Optional[SCM] = None
) -> Dockerfile:
    """Build a Containerfile for a Conda project

    Args:
        project_root (str): Root of project
        base_image (Optional[str], optional): Base image to use. Defaults to None.
        scm (Optional[SCM], optional): SCM to use. Defaults to None.

    Returns:
        Dockerfile: A Containerfile
    """
    dockerfile = build_conda_base_containerfile(project_root, base_image, scm)
    dockerfile = _add_repo_files(dockerfile, scm)
    return dockerfile


def build_pip_base_containerfile(
    project_root: str, base_image: Optional[str] = None, scm: Optional[SCM] = None
) -> Dockerfile:
    """Build a base Containerfile for a Pip project

    Args:
        project_root (str): Root of project
        base_image (Optional[str], optional): Base image to use. Defaults to None.
        scm (Optional[SCM], optional): SCM to use. Defaults to None.

    Returns:
        Dockerfile: A Containerfile
    """
    if scm is None:
        scm = SCM()

    dockerfile = Dockerfile()

    # find base image
    if base_image is None:
        try:
            info = sys.version_info
            dockerfile.from_(f"python:{info.major}.{info.minor}.{info.micro}")
        except KeyError:
            raise ValueError("could not determine python version")
    else:
        dockerfile.from_(base_image)

    dockerfile.env("PYTHONUNBUFFERED", "1")
    dockerfile.env("PYTHONDONTWRITEBYTECODE", "1")
    dockerfile.env("PIP_NO_CACHE_DIR", "off")
    dockerfile.env("PIP_DISABLE_PIP_VERSION_CHECK", "on")

    dockerfile.env("PYTHONPATH", f"${{PYTHONPATH}}:{REPO_ROOT}:{project_root}")

    dockerfile.run("apt update && apt install -y watchdog git curl")

    dockerfile.workdir(project_root)
    rel_proj_root = scm.rel_project_path()
    dockerfile.copy(f"{os.path.join(rel_proj_root, 'requirements.txt')}", f"{project_root}")

    dockerfile.run("python -m pip install -r requirements.txt")

    dockerfile.expose(DEFAULT_PORT)

    return dockerfile


def build_pip_containerfile(
    project_root: str, base_image: Optional[str] = None, scm: Optional[SCM] = None
) -> Dockerfile:
    """Build a Containerfile for a Pip project

    Args:
        project_root (str): Root of project
        base_image (Optional[str], optional): Base image to use. Defaults to None.
        scm (Optional[SCM], optional): SCM to use. Defaults to None.

    Returns:
        Dockerfile: A Containerfile
    """
    dockerfile = build_pip_base_containerfile(project_root, base_image, scm)
    dockerfile = _add_repo_files(dockerfile, scm)
    return dockerfile


def build_img(
    c: Dockerfile,
    sync_strategy: RemoteSyncStrategy,
    image_repo: Optional[str] = None,
    tag: Optional[str] = None,
    docker_socket: Optional[str] = None,
    scm: Optional[SCM] = None,
    labels: Optional[Dict[str, str]] = None,
    tag_prefix: Optional[str] = None,
    clean: bool = True,
) -> ImageID:
    """Build image from Containerfile

    Args:
        c (Dockerfile): Dockerfile to use
        image_repo (str, optional): repository name. Defaults to None.
        tag (str, optional): tag for image. Defaults to None.
        docker_socket (str, optional): docker socket to use. Defaults to None.
        scm (SCM, optional): SCM to use. Defaults to None.
        labels (Dict[str, str], optional): Labels to add to the image. Defaults to None.
        tag_prefix (str, optional): Prefix for the image tag. Defaults to None.
        clean (bool, optional): Whether to clean the generated dockerfile. Defaults to True

    Returns:
        ImageID: An ImageID
    """

    containerfile_path = write_dockerfile(c)

    if docker_socket is None:
        docker_socket = default_socket()

    cli = APIClient(base_url=docker_socket)

    if scm is None:
        scm = SCM()

    image_id = img_id(sync_strategy, image_repo=image_repo, tag=tag, scm=scm, tag_prefix=tag_prefix)

    logging.info(f"building image using id '{image_id}'")

    dl_tasks: Dict[str, TaskID] = {}
    ext_tasks: Dict[str, TaskID] = {}
    progress: Optional[Progress] = Progress(transient=True)
    progress.start()  # type: ignore
    for line in cli.build(
        path=os.path.dirname(containerfile_path),
        rm=True,
        tag=image_id.ref(),
        dockerfile=MDL_DOCKERFILE_NAME,
        decode=True,
        labels=labels,
    ):
        if "stream" in line:
            if progress:
                if progress.live.is_started:
                    progress.stop()
            line = str(line["stream"])
            if line != "\n":
                print(line.strip("\n"))
        if "progressDetail" in line:
            if progress is None:
                progress = Progress(transient=True)
                progress.start()
            if not progress.live.is_started:
                progress.start()
            if "status" not in line:
                continue
            if line["status"] == "Extracting":
                push_id: str = line["id"]
                details = line["progressDetail"]
                if push_id not in ext_tasks:
                    if "total" not in details:
                        continue
                    task_id = progress.add_task(f"extracting layer {push_id}", total=details["total"])
                    ext_tasks[push_id] = task_id
                task = ext_tasks[push_id]
                progress.update(task, completed=details["current"])
            if line["status"] == "Downloading":
                push_id = line["id"]
                details = line["progressDetail"]
                if push_id not in dl_tasks:
                    if "total" not in details:
                        continue
                    task_id = progress.add_task(f"downloading layer {push_id}", total=details["total"])
                    dl_tasks[push_id] = task_id
                task = dl_tasks[push_id]
                progress.update(task, completed=details["current"])
            else:
                print(line)

    # if clean:
    # delete_containerfile()
    return image_id


def push_img(id: ImageID, docker_socket: Optional[str] = None) -> None:
    """Push image

    Args:
        id (ImageID): image ID to push
        docker_socket (str, optional): docker socket to use. Defaults to None.
    """

    if docker_socket is None:
        docker_socket = default_socket()

    client = APIClient(base_url=docker_socket)

    logging.info("pushing docker image")

    with Progress() as progress:
        tasks: Dict[str, TaskID] = {}
        for line in client.push(id.ref(), stream=True, decode=True):
            if "status" not in line:
                continue
            if line["status"] != "Pushing":
                continue
            push_id: str = line["id"]
            details = line["progressDetail"]
            if push_id not in tasks:
                if "total" not in details:
                    continue
                task_id = progress.add_task(f"pushing layer {push_id}", total=details["total"])
                tasks[push_id] = task_id
            task = tasks[push_id]
            progress.update(task, completed=details["current"])

    logging.info("done pushing image")
    return


def find_or_build_img(
    docker_socket: Optional[str] = None,
    scm: Optional[SCM] = None,
    cfg: Optional[Config] = None,
    sync_strategy: RemoteSyncStrategy = RemoteSyncStrategy.CONTAINER,
    dev_dependencies: bool = False,
    command: Optional[List[str]] = None,
    tag: Optional[str] = None,
    tag_prefix: Optional[str] = None,
    labels: Optional[Dict[str, str]] = None,
    clean: bool = True,
    client_filepath: Optional[str] = None,
) -> ImageID:
    """Find the current image or build and push it

    Args:
        docker_socket (str, optional): docker socket to use. Defaults to None.
        scm (SCM, optional): SCM to use
        cfg (Config, optional): Config to use
        sync_strategy (RemoteSyncStrategy, optional): How to sync data
        command (List[str], optional): Optional command to add to the container
        tag (List[str], optional): Optional tag of the image
        tag_prefix (List[str], optional): Optional prefix for the tag of the image
        labels (Dict[str, str], optional): Labels to add to the image. Defaults to None.
        clean (bool, optional): Whether to clean the generate files. Default to True
        client_filepath (str, optional): The client filepath, which can be used to version

    Returns:
        ImageID: An image ID
    """
    if docker_socket is None:
        docker_socket = default_socket()

    cli = APIClient(base_url=docker_socket)

    if scm is None:
        scm = SCM()

    if cfg is None:
        cfg = Config()

    desired_id = img_id(sync_strategy, scm=scm, tag=tag, tag_prefix=tag_prefix, client_filepath=client_filepath)

    # check if tag exists in current image cache
    for img in cli.images():
        ids = img["RepoTags"]
        if ids is None:
            logging.info("no image ids found")
            continue
        for id in ids:
            # print(f"checking id '{id}' against desired id '{desired_id}'")
            if str(id) == str(desired_id):
                logging.info("cached image found locally")
                return desired_id

    # if not then build
    logging.info("image not found locally... building")
    dockerfile = build_dockerfile(command=command, sync_strategy=sync_strategy, dev_dependencies=dev_dependencies)

    image_id = build_img(dockerfile, sync_strategy, tag=tag, clean=clean, labels=labels, tag_prefix=tag_prefix)
    push_img(image_id)

    return image_id


def img_command(container_path: str, scm: Optional[SCM] = None) -> List[str]:
    """Create the CMD for the image based on the project type

    Args:
        container_path (str): Path to the executable
        scm (Optional[SCM], optional): An optional SCM to pass. Defaults to None.

    Returns:
        List[str]: A CMD list
    """
    if scm is None:
        scm = SCM()

    command = ["python", container_path]
    if scm.is_poetry_project():
        command = ["poetry", "run", "python", str(container_path)]

    elif scm.is_pip_project():
        command = ["python", str(container_path)]

    elif scm.is_conda_project():
        conda_yaml = load_conda_yaml()
        if "name" not in conda_yaml:
            raise ValueError("cannot find 'name' in environment.yml")

        env_name = conda_yaml["name"]
        command = ["conda", "run", "--no-capture-output", "-n", env_name, "python", str(container_path)]

    else:
        raise ValueError("project type unknown")

    return command


def cache_img() -> None:
    # https://github.com/senthilrch/kube-fledged
    return
