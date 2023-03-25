from typing import Any, get_type_hints, get_args, Optional, Dict, Type
import inspect
from types import NoneType
import logging

from modelos.object.encoding import is_first_order, is_dict, is_enum, is_tuple, is_optional, is_list, is_union


VERSION_HASH_LENGTH = 5


type_map = {
    int: {"type": "integer"},
    float: {"type": "number", "format": "float"},
    str: {"type": "string"},
    bool: {"type": "boolean"},
    bytes: {"type": "string", "format": "byte"},
    bytearray: {"type": "string", "format": "byte"},
}


def build_json_schema(obj: Any, default: Optional[Any] = None, sort: bool = True) -> dict:
    """Build JSON schema for the given object

    Args:
        obj (Any): Object to build schema for
        default (Optional[Any], optional): Default value. Defaults to None.
        sort (bool, optional): Whether to sort. Defaults to True.

    Returns:
        dict: A JSON schema representation of the object
    """
    print("obj: ", obj)
    if obj is None or obj == NoneType:
        return {}

    if is_first_order(obj):
        out = type_map[obj].copy()
        if default:
            out["default"] = default
        return out

    elif is_dict(obj):
        args = get_args(obj)

        if len(args) != 2:
            raise ValueError("Dictionaries must be typed")

        if args[0] != str:
            raise ValueError(f"Only string keys are supported in dictionaries: {obj}")

        out_d: Dict[str, Any] = {"type": "object"}

        val = build_json_schema(args[1])
        out_d["additionalProperties"] = val
        return out_d

    elif is_tuple(obj):
        args = get_args(obj)

        items = []
        for arg in args:
            typ = build_json_schema(arg)
            items.append(typ)

        return {"type": "array", "prefixItems": items}

    elif is_optional(obj):
        args = get_args(obj)
        return build_json_schema(args[0], default=default)

    elif is_list(obj):
        args = get_args(obj)

        if len(args) != 1:
            raise ValueError(f"Lists must be typed: {obj}")

        typ = build_json_schema(args[0])
        return {"type": "array", "items": typ}

    elif is_union(obj):
        args = get_args(obj)

        if sort:
            print("args: ", args)
            args = sorted(args)  # type: ignore

        items = []
        for arg in args:
            typ = build_json_schema(arg)
            items.append(typ)

        return {"oneOf": items}

    elif is_enum(obj):
        items = []

        member_map = obj._member_map_.items()
        if sort:
            member_map = dict(sorted(member_map)).items()

        for _, v in member_map:
            items.append(v.value)

        return {"type": "string", "enum": items}

    elif obj == Any:
        return {"type": "AnyType"}

    elif hasattr(obj, "__annotations__"):
        annots = get_type_hints(obj)

        props = {}
        opts = []
        if sort:
            annots = dict(sorted(annots.items()))  # type: ignore

        for nm, typ in annots.items():
            prop = build_json_schema(typ)
            if "default" in prop:
                if not prop[default]:
                    prop.pop("default")
            else:
                opts.append(nm)
            props[nm] = prop

        ret = {"type": "object", "properties": props}
        if opts:
            if sort:
                opts = sorted(opts)
            ret["required"] = opts

        return ret

    else:
        logging.warning(f"skipping serialization of unsupported type: '{obj}' type: '{type(obj)}'")
        return {}


def obj_api_schema(obj: Type, sort: bool = True) -> dict:
    """Build an OpenAPI schema for the object

    Args:
        obj (Any): Object to build schema for
        sort (bool, optional): Whether to sort the schema. Defaults to True.

    Returns:
        dict: An OpenAPI 3.1 spec
    """
    fns = inspect.getmembers(obj, predicate=inspect.isfunction)

    paths = {}

    if sort:
        fns = sorted(fns)

    for name, fn in fns:
        print("fn name: ", fn)
        if name.startswith("_"):
            continue

        req_props = {}
        required = []

        sig = inspect.signature(fn, eval_str=True, follow_wrapped=True)
        params = sig.parameters.items()

        if sort:
            params = dict(sorted(params)).items()

        for k, v in params:
            if k == "self" or k == "cls":
                continue

            default = None
            if v.default != inspect._empty:
                default = v.default
            else:
                required.append(k)

            print("annotation: ", v.annotation)
            schema = build_json_schema(v.annotation, default)
            req_props[k] = schema

        req_schema = {"type": "object", "properties": req_props}
        if required:
            req_schema["required"] = required

        hints = get_type_hints(fn)

        ret_schema = build_json_schema(hints["return"])

        if not ret_schema:
            route = {
                "post": {
                    "requestBody": {"content": {"application/json": {"schema": req_schema}}},
                    "responses": {"200": {"description": "ok"}},
                }
            }

        else:
            if ret_schema["type"] != "object":
                ret_schema = {"type": "object", "properties": {"value": ret_schema}}

            route = {
                "post": {
                    "requestBody": {"content": {"application/json": {"schema": req_schema}}},
                    "responses": {"200": {"content": {"application/json": {"schema": ret_schema}}}},
                }
            }

        paths[f"/{name}"] = route

    doc = ""
    if obj.__doc__:
        doc = obj.__doc__

    spec = {"openapi": "3.1.0", "info": {"description": doc, "title": obj.__name__}, "paths": paths}

    if sort:
        spec = dict(sorted(spec.items()))

    return spec
