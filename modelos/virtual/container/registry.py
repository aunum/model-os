from typing import Any, Dict, List, Optional

from docker.utils.utils import parse_repository_tag
from docker.utils.config import load_general_config
from docker.auth import resolve_repository_name, load_config
from opencontainers.distribution.reggie import (
    NewClient,
    WithUsernamePassword,
    WithDebug,
    WithName,
    WithReference,
    WithDigest,
)


def clean_repo_name(name: str) -> str:
    """Clean the repo name

    Args:
        name (str): Name of the repo

    Returns:
        str: Repo name
    """
    if len(name.split("/")) == 1:
        name = f"library/{name}"
    return name


def get_oci_client(uri: str) -> NewClient:
    """Get OCI client for a URI

    Args:
        uri (str): URI to find client for

    Returns:
        NewClient: an OCI client
    """

    repository, _ = parse_repository_tag(uri)
    registry, _ = resolve_repository_name(repository)

    general_configs = load_general_config()

    auth_configs = load_config(
        config_dict=general_configs,
        credstore_env=None,
    )
    auth_cfg = auth_configs.resolve_authconfig(registry)

    if "ServerAddress" in auth_cfg:
        server_addr = auth_cfg["ServerAddress"]
    elif "serveraddress" in auth_cfg:
        server_addr = auth_cfg["serveraddress"]
    else:
        raise ValueError("server address not found in auth config")

    if "Username" in auth_cfg:
        username = auth_cfg["Username"]
    elif "username" in auth_cfg:
        username = auth_cfg["username"]
    else:
        raise ValueError("username not found in auth config")

    if "Password" in auth_cfg:
        password = auth_cfg["Password"]
    elif "password" in auth_cfg:
        password = auth_cfg["password"]
    else:
        raise ValueError("password not found in auth config")

    client = NewClient(
        server_addr,
        WithUsernamePassword(username, password),
        WithDebug(True),
    )
    return client


def get_repo_tags(repo: str, client: Optional[NewClient] = None) -> List[str]:
    """Get image tags

    Args:
        repo (str): Repo URI e.g. aunum/ml-project
        cli (docker.APIClient, optional): Docker client. Defaults to None.

    Returns:
        List[str]: A list of tags
    """

    repository, _ = parse_repository_tag(repo)
    _, repo_name = resolve_repository_name(repository)

    repo_name = clean_repo_name(repo_name)

    if client is None:
        client = get_oci_client(repo)

    req = client.NewRequest("GET", "/v2/<name>/tags/list", WithName(repo_name))
    response = client.Do(req)
    if response.status_code == 404:
        return []
    if response.status_code != 200:
        raise SystemError(f"unable to get repo tags: {response}")
    jdict = response.json()
    return jdict["tags"]


def delete_repo_tag(repo: str, tag: str, client: Optional[NewClient] = None) -> None:
    """Delete repo tag

    Args:
        repo (str): Repo URI e.g. aunum/ml-project
        tag (str): Tag to delete
        cli (docker.APIClient, optional): Docker client. Defaults to None.
    """
    if tag is None:
        raise ValueError("tag cannot be None")

    repository, _ = parse_repository_tag(repo)
    _, repo_name = resolve_repository_name(repository)

    repo_name = clean_repo_name(repo_name)

    if client is None:
        client = get_oci_client(repo)

    req = client.NewRequest("DELETE", "/v2/<name>/manifests/<reference>", WithName(repo_name), WithReference(tag))
    response = client.Do(req)
    if response.status_code != 200 and response.status_code != 202:
        raise ValueError(f"trouble executing request: {response}")


def get_img_labels(uri: str) -> Dict[str, Any]:
    """Get any labels for an image

    Args:
        uri (str): Image URI to get labels for e.g. aunum/ml-project:v1.0

    Returns:
        Dict[str, Any]: Dictionary of labels
    """
    repository, tag = parse_repository_tag(uri)
    _, repo_name = resolve_repository_name(repository)

    client = get_oci_client(uri)

    repo_name = clean_repo_name(repo_name)

    req = client.NewRequest(
        "GET", "/v2/<name>/manifests/<reference>", WithName(repo_name), WithReference(tag)
    ).SetHeader("Accept", "application/vnd.docker.distribution.manifest.v2+json")
    response = client.Do(req)

    jdict1 = response.json()
    if "config" not in jdict1:
        raise ValueError(f"'config' not found in response from registry: {jdict1}")

    config = jdict1["config"]
    if "digest" not in config:
        raise ValueError(f"'digest' not found in response from registry: {jdict1}")

    digest = config["digest"]
    req = client.NewRequest("GET", "/v2/<name>/blobs/<digest>", WithName(repo_name), WithDigest(digest)).SetHeader(
        "Accept", "application/vnd.docker.distribution.manifest.v2+json"
    )
    response = client.Do(req)
    jdict2 = response.json()

    if "Labels" not in jdict2["config"]:
        raise ValueError(f"'Labels' not found in response from registry: {jdict2}")

    labels = jdict2["config"]["Labels"]

    return labels
