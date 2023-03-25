import hashlib
import yaml
import logging
import json
from typing import Any, Type, get_type_hints

from .encoding import encode_any
from .schema import obj_api_schema
from modelos.project import Project
from modelos.util.source import get_source
from modelos.util.version import VersionBump, merge_bump

VERSION_SHA_LENGTH = 5


def interface_hash(schema: dict) -> str:
    """Generate a hash for the schema interface

    Args:
        schema (dict): A sorted schema

    Returns:
        str: A SHA256 hash
    """

    s = yaml.dump(schema)
    h = hashlib.new("sha256")
    h.update(str(s).encode())

    return h.hexdigest()[:VERSION_SHA_LENGTH]


FIRST_ORDER_SCHEMA = ["string", "number", "boolean"]


def calc_component_bump(
    old_schema: dict,
    new_schema: dict,
    path: str,
    action: str,
    parent: str = "",
    current_bump: VersionBump = VersionBump.NONE,
) -> VersionBump:
    """Check if the version should be bumped based on the component

    This follows the basic rules of API evoluion:

        If properties/paths change or are missing in the new schema, the major version is bumped
        If properties/paths are added, or defaults are changed, the minor version is bumped
        If properties change from required to not required, the patch version is bumped
        If properties change from not required to required, the major version is bumped

    Args:
        old_schema (dict): Old schema component
        new_schema (dict): New schema component
        path (str): Path this component lies under
        action (str): Action this component lies under
        parent (str, optional): Parent of the component. Defaults to "".
        current_bump(VersionBump, optional): The running version bump. Defaults to NONE.

    Raises:
        ValueError: If the schema is unparsable

    Returns:
        VersionBump: Amount to bump version
    """
    if "oneOf" in old_schema:
        if "oneOf" not in new_schema:
            logging.info(f"old schema is a oneOf '{action} {path} {parent}' new schema is not, bumping major version")
            return VersionBump.MAJOR

        # TODO: handle more in depth

    if "oneOf" in new_schema:
        if "oneOf" not in old_schema:
            logging.info(f"new schema is a oneOf '{action} {path} {parent}' old schema is not, bumping patch version")
            current_bump = merge_bump(current_bump, VersionBump.PATCH)

    old_type = old_schema["type"]
    new_type = new_schema["type"]

    if current_bump == VersionBump.MAJOR:
        return current_bump

    if old_type == "object":
        if new_type != "object":
            logging.info(f"old schema is an object '{action} {path} {parent}' new schema is not, bumping major version")
            return VersionBump.MAJOR

        if "properties" in old_schema:
            if "properties" not in new_schema:
                logging.info(f"properties '{action} {path}' not found in new schema, bumping major version")
                return VersionBump.MAJOR

            new_props = new_schema["properties"]
            old_props = old_schema["properties"]
            for old_name, old_sch in old_props.items():
                if old_name not in new_props:
                    logging.info(
                        f"property '{action} {path} {parent}.{old_name}' not found in new schema, bumping major version"
                    )
                    return VersionBump.MAJOR

                new_sch = new_props[old_name]
                current_bump = merge_bump(
                    current_bump,
                    calc_component_bump(old_sch, new_sch, path, action, parent + f".{old_name}", current_bump),
                )
                if current_bump == VersionBump.MAJOR:
                    return current_bump

            for new_name, new_sch in new_props.items():
                if new_name not in old_props:
                    logging.info(
                        f"added property '{action} {path} {parent}.{new_name}'"
                        + " found in new schema, bumping minor version"
                    )
                    current_bump = merge_bump(current_bump, VersionBump.MINOR)

                old_sch = old_props[new_name]
                current_bump = merge_bump(
                    current_bump,
                    calc_component_bump(old_sch, new_sch, path, action, parent + f".{new_name}", current_bump),
                )
                if current_bump == VersionBump.MAJOR:
                    return current_bump

        if "required" in old_schema:
            if "required" not in new_schema:
                logging.info(
                    f"required properties on old schema '{action} {path} {parent}'"
                    + " not found in new schema, bumping patch version"
                )
                current_bump = merge_bump(current_bump, VersionBump.PATCH)

            for req in old_schema["required"]:
                if req not in new_schema["required"]:
                    logging.info(
                        f"required property '{action} {path} {parent}.{req}'"
                        + " in old schema and not found in new schema, bumping patch version"
                    )
                    current_bump = merge_bump(current_bump, VersionBump.PATCH)

        if "required" in new_schema:
            if "required" not in old_schema:
                logging.info(
                    f"required properties added in new schema '{action} {path} {parent}'" + " bumping major version"
                )
                return VersionBump.MAJOR

            for req in new_schema["required"]:
                if req not in old_schema["required"]:
                    logging.info(
                        f"required property '{action} {path} {parent}.{req}'"
                        + " added in new schema, bumping major version"
                    )
                    return VersionBump.MAJOR

        if "additionalProperties" in old_schema:
            if "additionalProperties" not in new_schema:
                logging.info(
                    f"additional properties on old schema '{action} {path} {parent}'"
                    + " not found in new schema, bumping major version"
                )
                return VersionBump.MAJOR

            current_bump = merge_bump(
                current_bump,
                calc_component_bump(
                    old_schema["additionalProperties"],
                    new_schema["additionalProperties"],
                    path,
                    action,
                    parent + ".additionalProperties",
                    current_bump,
                ),
            )
            if current_bump == VersionBump.MAJOR:
                return current_bump

    elif old_type in FIRST_ORDER_SCHEMA:
        if old_type != new_type:
            logging.info(f"property '{action} {path} {parent}' does not match new schema, bumping major version")
            return VersionBump.MAJOR

        if "format" in old_schema and (old_schema["format"] != new_schema["format"]):
            logging.info(
                f"property '{action} {path} {parent}' has different format in new schema, bumping major version"
            )
            return VersionBump.MAJOR

    elif old_type == "array":
        if new_type != "array":
            logging.info(f"old schema is an array '{action} {path} {parent}' new schema is not, bumping major version")
            return VersionBump.MAJOR

        if "items" in old_schema:
            if "items" not in new_schema:
                logging.info(
                    f"old schema array has items '{action} {path} {parent}' new schema does not, bumping major version"
                )
                return VersionBump.MAJOR

            current_bump = merge_bump(
                current_bump,
                calc_component_bump(
                    old_schema["items"], new_schema["items"], path, action, parent + ".items", current_bump
                ),
            )
            if current_bump == VersionBump.MAJOR:
                return current_bump

        if "prefixItems" in old_schema:
            if "prefixItems" not in new_schema:
                logging.info(
                    f"old schema array has prefix items '{action} {path} {parent}' "
                    + " new schema does not, bumping major version"
                )
                return VersionBump.MAJOR

            if len(new_schema["prefixItems"]) != len(old_schema["prefixItems"]):
                logging.info(
                    f"old schema array has prefix items '{action} {path} {parent}'"
                    + " does not match length of new, bumping major version"
                )
                return VersionBump.MAJOR

            for i, old_item in enumerate(old_schema["prefixItems"]):
                new_item = new_schema["prefixItems"][i]
                current_bump = merge_bump(
                    current_bump,
                    calc_component_bump(old_item, new_item, path, action, parent + ".prefixItems", current_bump),
                )
                if current_bump == VersionBump.MAJOR:
                    return current_bump

    else:
        raise ValueError(f"unkown type for schema: {old_type}")

    return current_bump


def calc_schema_bump(old_schema: dict, new_schema: dict) -> VersionBump:
    """Calculate whether the OpenAPI interface version should be bumped

    This follows the basic rules of API evoluion:

        If properties/paths change or are missing in the new schema, the version is bumped.
        If properties/paths are added, the version is not bumped.
        If properties change from required to not required, the patch version is bumped
        If properties change from not required to required, the major version is bumped

    Args:
        old_schema (dict): Old schema
        new_schema (dict): New schema

    Returns:
        VersionBump: Amount to bump version
    """
    new_paths = new_schema["paths"]
    old_paths = old_schema["paths"]

    bump = VersionBump.NONE
    for path in old_paths:
        if path not in new_paths:
            logging.info(f"path '{path}' not found in new schema, bumping major version")
            return VersionBump.MAJOR

        for action, val in old_paths[path].items():
            if action not in new_paths[path]:
                logging.info(f"action '{action} {path}' not found in new schema, bumping major version")
                return VersionBump.MAJOR

            old_req_schema = val["requestBody"]["content"]["application/json"]["schema"]
            new_req_schema = new_paths[path][action]["requestBody"]["content"]["application/json"]["schema"]

            bump = calc_component_bump(old_req_schema, new_req_schema, path, action, current_bump=bump)

    for path in new_paths:
        if path not in old_paths:
            logging.info(f"path '{path}' added in new schema, bumping minor version")
            return VersionBump.MINOR

        for action, val in new_paths[path].items():
            if action not in old_paths[path]:
                logging.info(f"action '{action} {path}' added in new schema, bumping minor version")
                return VersionBump.MINOR

    return bump


def class_hash(cls: Type) -> str:
    """Generate a hash for the object class

    Args:
        cls (Any): The object class

    Returns:
        str: A SHA256 hash
    """

    # TODO: more robust object versioning

    project = Project()
    env = project.env_code()

    src = get_source(cls)

    h = hashlib.new("sha256")
    h.update(src.encode())
    h.update(env.encode())

    return h.hexdigest()[:VERSION_SHA_LENGTH]


def instance_hash(instance: Any) -> str:
    """Generate a hash for the instance

    Args:
        instance (Any): The object instance

    Returns:
        str: A SHA256 hash
    """
    annots = get_type_hints(instance)

    s = "0"

    annots = dict(sorted(annots.items()))
    for nm, typ in annots.items():
        if hasattr(instance, nm):
            jdict = encode_any(getattr(instance, nm), typ)
            s += json.dumps(jdict)

    h = hashlib.new("sha256")
    h.update(s.encode())

    return h.hexdigest()[:VERSION_SHA_LENGTH]


def build_obj_version_hash(client_cls: Type, server_cls: Type) -> str:
    """Build a version hash for the object class

    Args:
        obj (Any): Object to build hash for

    Returns:
        str: Object hash {interface}-{class}
    """
    schema = obj_api_schema(client_cls)
    iface_hash = interface_hash(schema)

    obj_hash = class_hash(server_cls)

    return f"{iface_hash}-{obj_hash}"


def build_inst_version_hash(client_cls: Type, obj: Any) -> str:
    """Build a version hash for the object instance

    Args:
        obj (Any): Object to build hash for

    Returns:
        str: Object hash {interface}-{class}-{instance}
    """
    obj_hash = build_obj_version_hash(client_cls, obj.__class__)
    inst_hash = instance_hash(obj)

    return f"{obj_hash}-{inst_hash}"
