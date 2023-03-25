from typing import List, Optional, Dict
import logging

from docker.auth import resolve_repository_name
from docker import APIClient
from opencontainers.distribution.reggie import NewClient
from semver import VersionInfo
import yaml

from .base import ObjectRepo
from modelos.virtual.container.client import default_socket
from modelos.env.image.build import build_dockerfile, RemoteSyncStrategy, build_img, push_img
from modelos.virtual.container.id import ImageID
from modelos.object.id import ObjectID, NV, Version
from modelos.object.info import ObjectArtifactInfo
from modelos.virtual.container.registry import get_oci_client, get_repo_tags, delete_repo_tag, get_img_labels
from modelos.project import Project

PROTOCOL = "oci"


class OCIObjectRepo(ObjectRepo):
    """An OCI object repository"""

    _uri: str
    _docker_cli: APIClient
    _oci_client: NewClient
    _registry: str
    _name: str

    def __init__(self, uri: str, docker_socket: Optional[str] = None) -> None:
        """Connect to an OCI based pkg repo

        Args:
            uri (str): OCI registry URI to connect to e.g. aunum/ml-project or docker.io/aunum/ml-project
            docker_socket (Optional[str], optional): Docker socket to use. Defaults to None.
        """
        self._uri = uri

        self._registry, self._name = resolve_repository_name(uri)

        if docker_socket is None:
            docker_socket = default_socket()

        self._docker_cli = APIClient(base_url=docker_socket)
        self._oci_client = get_oci_client(uri)

    @classmethod
    def parse(cls, uri: str) -> ObjectID:
        """Parse a URI into a object ID

        Args:
            uri (str): URI of the object

        Returns:
            ObjectID: An object ID
        """
        id = ImageID.from_ref(uri)
        nv = NV.parse(id.tag)
        return ObjectID(nv.name, nv.version, id.host, id.repository, PROTOCOL)

    def build_id(self, name: str, version: str) -> ObjectID:
        """Build ID for the object

        Args:
            name (str): Name of the object
            version (str): Version of the object

        Returns:
            ObjectID: The object ID
        """
        return ObjectID(name, version, self._registry, self._name, PROTOCOL)

    @classmethod
    def build_uri(cls, id: ObjectID) -> str:
        """Generate a URI for the object id

        Args:
            id (ObjectID): ID to generate URI for

        Returns:
            str: A URI
        """
        uri = f"{id.repo}:obj.{id.name}.{id.version}"
        if id.host != "docker.io":
            uri = f"{id.host}/{uri}"
        return uri

    def host(self) -> str:
        """Host of the repo

        Returns:
            str: Host name
        """
        return self._registry

    def name(self) -> str:
        """Name of the repo

        Returns:
            str: Repo name
        """
        return self._name

    def protocol(self) -> str:
        """Protocol of the repo

        Returns:
            str: Protocol
        """
        return "oci"

    def find(self, name: str, version: Optional[str]) -> List[ObjectID]:
        """Find the object

        Args:
            name (str): Name of the object
            version (Optional[str], optional): Version of the object

        Returns:
            List[ObjectID]: A list of objects
        """

        ret: List[ObjectID] = []
        for img in self._docker_cli.images():
            ids = img["RepoTags"]
            if ids is None:
                logging.info("no image ids found")
                continue
            for id in ids:
                # print(f"checking id '{id}' against desired id '{desired_id}'")
                try:
                    obj_id = self.parse(id)
                except Exception:
                    continue

                if name != obj_id.name:
                    continue

                if version and version != obj_id.version:
                    continue

                ret.append(obj_id)

        return ret

    def build(
        self,
        name: str,
        version: str,
        command: List[str],
        clean: bool = True,
        labels: Optional[Dict[str, str]] = None,
        project: Optional[Project] = None,
    ) -> ObjectID:
        """Build the object artifact

        Args:
            name (str): Name of the object
            version (str): Version of the object
            command (List[str]): Command to launch object.
            clean (bool, optional): Whether to clean generated files. Defaults to True.
            labels (Dict[str, str], optional): Labels to add to the image. Defaults to None.
            project (Project, optional): Project to use. Defaults to None.

        Returns:
            ObjectID: The object ID
        """

        if project is None:
            project = Project()

        id = self.build_id(name, version)

        dockerfile = build_dockerfile(
            project=project,
            command=command,
            sync_strategy=RemoteSyncStrategy.IMAGE,
        )

        image_id = build_img(
            dockerfile,
            RemoteSyncStrategy.IMAGE,
            project=project,
            tag=str(id.nv()),
            img_repo=self._uri,
            clean=clean,
            labels=labels,
        )
        logging.info(f"successfully built img with {image_id}")

        return id

    def find_or_build(
        self,
        name: str,
        version: str,
        command: List[str],
        clean: bool = True,
        labels: Optional[Dict[str, str]] = None,
        project: Optional[Project] = None,
    ) -> ObjectID:
        """Find or build the object artifact

        Args:
            name (str): Name of the object
            version (str): Version of the object
            command (List[str]): Command to launch object.
            clean (bool, optional): Whether to clean generated files. Defaults to True.
            labels (Dict[str, str], optional). Labels to add to the image. Defaults to None.
            project (Project, optional): Project to use. Defaults to None.

        Returns:
            ObjectID: The object ID
        """
        print("generating id: ", name, version)
        id = self.build_id(name, version)
        print("id: ", id)

        found_ids = self.find(name, version)
        print("found ids: ", found_ids)
        if len(found_ids) == 1:
            return found_ids[0]

        if len(found_ids) > 1:
            raise SystemError("found multiple matching images")

        logging.info("image not found locally... building")
        self.build(name, version, command, clean, labels, project=project)

        self.push(name, version)

        return id

    def push(self, name: str, version: str) -> ObjectID:
        """Push the object to the remote

        Args:
            name (str): Name of the object
            version (str): Version of the object

        Returns:
            ObjectID: The object ID
        """
        id = self.build_id(name, version)
        imgid = ImageID(id.host, id.repo, str(id.nv()))
        push_img(imgid, api_client=self._docker_cli)

        return id

    def pull(self, name: str, version: str) -> ObjectID:
        """Pull the object from remote

        Args:
            name (str): Name of the object
            version (str): Version of the object

        Returns:
            ObjectID: The object ID
        """
        id = self.build_id(name, version)

        repo = f"{id.host}/{id.repo}"

        logging.info(f"pulling image '{str(id)}'")
        self._docker_cli.pull(repo, tag=str(id.nv()))

        logging.info(f"successfully pulled img with '{str(id)}'")

        return id

    def info(self, name: str, version: str) -> ObjectArtifactInfo:
        """Info for the object artifact

        Args:
            name (str): Name of the object
            version (str): Version of the object

        Returns:
            ObjectArtifactInfo: Object info
        """
        id = self.build_id(name, version)
        uri = self.build_uri(id)
        labels = get_img_labels(uri)
        return ObjectArtifactInfo.from_flat(labels)

    def show(self, id: ObjectID) -> None:
        """Show the object

        Args:
            id (ObjectID): ID of the object
        """
        print("---")
        out = self.info(id.name, id.version).__dict__

        fin = {}
        for k, v in out.items():
            if v:
                fin[k] = v

        print(yaml.dump(fin))
        print("")

    def names(self) -> List[str]:
        """Names of the objects in the repo

        Returns:
            List[str]: Names of objects
        """
        names = set()
        for tag in get_repo_tags(self._uri, self._oci_client):
            try:
                nv = ObjectID.parse_nv(tag)
                names.add(nv.name)
            except Exception:
                continue

        return list(names)

    def versions(self, name: str, compatible_with: Optional[Version] = None) -> List[str]:
        """Versions of a object

        Args:
            name (str): Name of the object
            compatible_with (Version): Only return versions compatible with the given version

        Returns:
            List[str]: List of object versions
        """
        versions = []
        for tag in get_repo_tags(self._uri, self._oci_client):
            try:
                nv = ObjectID.parse_nv(tag)
                if nv.name != name:
                    continue
                if compatible_with:
                    if not compatible_with.is_compatible(nv.parse_version()):
                        continue
                versions.append(nv.version)
            except Exception:
                continue

        return versions

    def latest(self, name: str) -> Optional[str]:
        """Latest release

        Args:
            name (str): Name of the object

        Returns:
            Optional[str]: Latest release, or None if no releases
        """
        tags = get_repo_tags(self._uri, self._oci_client)

        latest_version: Optional[VersionInfo] = None
        for tag in tags:
            try:
                nv = ObjectID.parse_nv(tag)
                if nv.name != name:
                    continue
                info = VersionInfo.parse(nv.version[1:])
                if latest_version is None:
                    latest_version = info

                if info > latest_version:
                    latest_version = info
            except Exception:
                continue

        if latest_version is None:
            return None

        return f"v{str(latest_version)}"

    def releases(self, name: str) -> List[str]:
        """Releases for the object

        Args:
            name (str): Name of the object

        Returns:
            List[str]: A list of releases
        """
        tags = get_repo_tags(self._uri, self._oci_client)

        releases: List[str] = []
        for tag in tags:
            try:
                nv = ObjectID.parse_nv(tag)
                VersionInfo.parse(nv.version[1:])
                if name == nv.name:
                    releases.append(tag)
            except Exception:
                continue

        return releases

    def ids(self) -> List[ObjectID]:
        """List of object ids of all objects

        Returns:
            List[str]: A list of object ids
        """
        tags = get_repo_tags(self._uri, self._oci_client)

        ids: List[ObjectID] = []
        for tag in tags:
            try:
                nv = ObjectID.parse_nv(tag)
                id = self.build_id(nv.name, nv.version)
                ids.append(id)
            except Exception:
                continue

        return ids

    def delete(self, name: str, version: str) -> None:
        """Delete a object

        Args:
            name (str): Name of the object
            version (Optional[str], optional): Versions to delete, use 'all' for all versions. Defaults to None.
        """
        tags = get_repo_tags(self._uri, self._oci_client)

        for tag in tags:
            try:
                nv = ObjectID.parse_nv(tag)
                if name == nv.name and version == nv.version:
                    delete_repo_tag(self._uri, tag)
                    logging.info(f"deleted repo tag {tag}")
                    return
            except Exception:
                continue

        raise ValueError(f"could not find tag with name '{name}' and version '{version}' to delete")

    def clean(self, name: str, releases: bool = False) -> None:
        """Delete unused objects

        Args:
            name (str): Name of the pkg
            releases (bool, optional): Whether to delete releases. Defaults to False.
        """

        tags = get_repo_tags(self._uri, self._oci_client)

        for tag in tags:
            try:
                nv = ObjectID.parse_nv(tag)
                if name != nv.name:
                    continue
                if not releases:
                    VersionInfo.parse(nv.version)
            except Exception:
                continue
            delete_repo_tag(self._uri, tag)
            logging.info(f"deleted repo tag {tag}")

        return None
