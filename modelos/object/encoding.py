from typing import Dict, Any, Type, Union, TypeVar, Optional, get_args, get_origin, get_type_hints
from types import NoneType
from enum import Enum
import logging
from collections.abc import Iterable, Iterator

FIRST_ORDER_PRIMITIVES = [int, str, float, bool, bytes]


def json_is_type_match(t: Type, jdict: Any) -> bool:
    """Checks if the given type matchs the JSON dictionary

    Args:
        t (Type): A type to check against
        jdict (Any): JSON dict to check

    Returns:
        bool: Whether they match
    """
    if t == NoneType or t is None:
        return jdict is None

    if is_optional(t):
        args = get_args(t)
        return json_is_type_match(args[0], jdict) or json_is_type_match(args[1], jdict)

    if jdict is None:
        return t == NoneType

    if is_iterable_cls(t) and "response" in jdict:
        jdict = jdict["response"]

    if is_first_order(t):
        return isinstance(jdict, t)

    elif t == Any:
        return True

    elif hasattr(t, "__annotations__"):
        if not is_dict(type(jdict)):
            return False
        annots: Dict[str, Type] = get_type_hints(t)
        for nm, typ in annots.items():
            if not json_is_type_match(typ, jdict[nm]):
                return False
        return True

    elif is_dict(t):
        args = get_args(t)
        if len(args) != 2:
            raise ValueError(f"dictionary must by typed: {t}")

        for k, v in jdict.items():
            if not json_is_type_match(args[0], k):
                return False

            if not json_is_type_match(args[1], v):
                return False
        return True

    elif is_list(t):
        args = get_args(t)
        if len(args) != 1:
            raise ValueError(f"list must by typed: {t}")

        for v in jdict:
            if not json_is_type_match(args[0], v):
                return False
        return True

    elif is_tuple(t):
        args = get_args(t)
        for arg in args:
            for v in jdict:
                if not json_is_type_match(arg, v):
                    return False
        return True

    elif is_union(t):
        args = get_args(t)

        is_match = False
        for arg in args:
            is_match = json_is_type_match(arg, jdict)
            if is_match:
                break
        if not is_match:
            return False
        return True

    elif is_enum(t):
        try:
            t(jdict)
            return True
        except Exception:
            return False

    else:
        raise ValueError(f"type not supported: {t}")


def deep_isinstance(obj: Any, t: Optional[Type]) -> bool:
    """A variation of isinstance that works with type variables

    Args:
        obj (Any): Object to check
        t (Type): Type to check against

    Returns:
        bool: Whether it is an instance
    """

    if t is None or t is NoneType:
        return obj is None

    if is_dict(t):
        if not isinstance(obj, dict):
            return False
        args = get_args(t)
        if len(args) != 2:
            raise ValueError(f"dictionary must by typed: {t}")
        if args[1] == Any:
            return True
        for k, v in obj.items():
            if not isinstance(v, args[1]):
                return False
        return True

    elif is_list(t):
        if not isinstance(obj, list):
            return False
        args = get_args(t)
        if args[0] == Any:
            return True
        if len(args) != 1:
            raise ValueError(f"list must by typed: {t}")
        return isinstance(obj[0], args[0])

    elif is_tuple(t):
        if not isinstance(obj, tuple):
            return False
        args = get_args(t)
        for i, arg in enumerate(args):
            if arg == Any:
                return True
            if not isinstance(obj[i], arg):
                return False

    elif is_first_order(t):
        return isinstance(obj, t)

    elif hasattr(t, "__annotations__"):
        return isinstance(obj, t)

    else:
        raise ValueError(f"type not supported: {t}")

    return False


def obj_from_json(t: Type, jsn: Dict[str, Any]) -> Any:
    """Create an object from JSON

    Args:
        t (Type): Type of object
        jsn (Dict[str, Any]): JSON to create from

    Returns:
        Any: A new object
    """
    _ret = object.__new__(t)
    for k, v in jsn.items():
        setattr(_ret, k, v)
    return _ret


def is_type(t: Type) -> bool:
    """Check if a type is a type

    Args:
        t (Type): The type to check

    Returns:
        bool: Whether it is a type
    """
    is_typ = t == Type or t == type or (hasattr(t, "__origin__") and t.__origin__ == type)
    return is_typ


def is_dict(t: Type) -> bool:
    """Check if a type is a dict

    Args:
        t (Type): The type to check

    Returns:
        bool: Whether it is a dict
    """
    return t == dict or (hasattr(t, "__origin__") and t.__origin__ == dict)


def is_list(t: Type) -> bool:
    """Check if a type is a list

    Args:
        t (Type): The type to check

    Returns:
        bool: Whether it is a list
    """
    return t == list or (hasattr(t, "__origin__") and t.__origin__ == list)


def is_set(t: Type) -> bool:
    """Check if a type is a set

    Args:
        t (Type): The type to check

    Returns:
        bool: Whether it is a set
    """
    return t == set or (hasattr(t, "__origin__") and t.__origin__ == set)


def is_first_order(t: Type) -> bool:
    """Check if a type is first order i.e. int, str, bool, etc

    Args:
        t (Type): The type to check

    Returns:
        bool: Whether it is first order
    """
    return t in FIRST_ORDER_PRIMITIVES or (hasattr(t, "__origin__") and t.__origin__ in FIRST_ORDER_PRIMITIVES)


def is_union(t: Type) -> bool:
    """Check if a type is a union

    Args:
        t (Type): The type to check

    Returns:
        bool: Whether it is a union
    """
    is_union = hasattr(t, "__origin__") and t.__origin__ == Union
    return is_union


def is_tuple(t: Type) -> bool:
    """Check if a type is a tuple

    Args:
        t (Type): The type to check

    Returns:
        bool: Whether it is a tuple
    """
    return isinstance(t, tuple) or (hasattr(t, "__origin__") and t.__origin__ == tuple)


def is_enum(t: Type) -> bool:
    """Check if a type is an enum

    Args:
        t (Type): The type to check

    Returns:
        bool: Whether it is an enum
    """
    try:
        if issubclass(t, Enum):
            return True
    except:  # noqa
        pass

    return False


def is_optional(t: Type) -> bool:
    """Check if a type is optional

    Args:
        type (Type): A type

    Returns:
        bool: Whether the type is optional
    """
    return get_origin(t) is Union and type(None) in get_args(t)


def is_iterable_cls(t: Type) -> bool:
    """Check if type is iterable

    Args:
        t (Type): A type

    Returns:
        bool: Whether it is iterable
    """
    if t == Iterable:
        return True

    orig = get_origin(t)
    if orig is not None:
        if orig == Iterable:
            return True
        if orig == Iterator:
            return True

    return False


def encode_any(obj: Any, t: Type) -> Dict[str, Any]:
    """Encode any object to JSON

    To work with complex objects, provide a to_dict() method on your object.
    This can otherwise be slow and should be avoided in any performance bound areas

    Args:
        obj (Any): Any object
        t (Type): The type

    Returns:
        Dict[str, Any]: A JSON serializable dict
    """

    def _encode_any(obj: Any, t: Type):
        # print(f"encooding {obj} into '{t}'")
        _op = getattr(t, "to_dict", None)

        if is_type(t):
            raise NotImplementedError(f"types not yet supported for {t}")

        elif callable(_op):
            return obj.to_dict()

        elif is_first_order(t):
            return obj

        elif is_dict(t):
            args = get_args(t)
            if len(args) != 2:
                raise ValueError(f"Dict must by typed: {t}")

            if is_first_order(args[1]):
                return obj

            else:
                ret_dict = {}
                for k, v in obj.items():
                    _v = _encode_any(v, args[1])
                    ret_dict[k] = _v

                return ret_dict

        elif is_set(t):
            args = get_args(t)
            if len(args) != 1:
                raise ValueError(f"Sets must be typed: {t}")

            if is_first_order(args[0]):
                return obj

            else:
                ret_list = []

                for v in obj:
                    _v = _encode_any(v, args[0])
                    ret_list.append(_v)

                return ret_list

        elif is_list(t):
            args = get_args(t)
            if len(args) != 1:
                raise ValueError(f"List must be typed: {t}")

            if is_first_order(args[0]):
                return obj

            else:
                ret_list = []

                for v in obj:
                    _v = _encode_any(v, args[0])
                    ret_list.append(_v)

                return ret_list

        elif is_tuple(t):
            args = get_args(t)
            if len(args) == 0:
                raise ValueError(f"Tuple must by typed: {t}")

            json_list = []

            for i, v in enumerate(obj):
                _v = encode_any(v, args[i])
                json_list.append(_v)

            return json_list

        elif t == NoneType:
            return None

        elif is_union(t):
            args = get_args(t)
            if len(args) == 2 and args[1] == NoneType:
                # Handle optionals
                args = (args[1], args[0])

            for i, arg in enumerate(args):
                if deep_isinstance(obj, arg):
                    return _encode_any(obj, arg)
            raise ValueError(f"obj '{obj}' is not of any union types: {t}")

        elif is_enum(t):
            return obj.value

        elif t == Any:
            logging.warning(
                "Use of Any type may result in serialization failures; object supplied to Any "
                + "must be json serializable"
            )
            return obj

        # TODO: need to handle the given dict types
        elif hasattr(t, "__dict__"):
            d = obj.__dict__
            if hasattr(t, "__annotations__"):
                ret = {}
                annotations = get_type_hints(t)
                for nm, typ in annotations.items():
                    _v = _encode_any(d[nm], typ)
                    ret[nm] = _v
                return ret
            else:
                logging.warning(f"obj '{obj}' does not have annotations")
            return d
        else:
            raise ValueError(f"Do not know how to serialize obj '{obj}' of type: {t}")

    ret = _encode_any(obj, t)
    typ = type(ret)
    if is_first_order(typ) or is_list(typ) or is_tuple(typ) or is_enum(typ):
        ret = {"value": ret}

    return ret


T = TypeVar("T", bound=Type)


def decode_any(jdict: Dict[str, Any], t: T) -> T:
    """Decode any JSON dictionary into a type

    Args:
        jdict (Dict[str, Any]): A JSON dictionary
        t (T): Type to decode into

    Returns:
        T: The given type
    """

    # print(f"decoding {jdict} into '{t}'")
    try:
        if "value" in jdict:
            jdict = jdict["value"]
    except Exception:
        pass

    if is_type(t):
        raise NotImplementedError(f"types not yet supported for {t}")

    if is_first_order(t):
        return jdict  # type: ignore

    # start type checks
    _op = getattr(t, "from_dict", None)
    if callable(_op):
        return t.from_dict(jdict)

    elif t is None or t is NoneType:
        if jdict is not None:
            raise ValueError(f"Expected None but recieved {jdict}")
        return None  # type: ignore

    elif is_dict(t):
        args = get_args(t)
        if len(args) != 2:
            raise ValueError(f"Dict args must be typed: {t}")

        if is_first_order(args[1]):
            return jdict  # type: ignore

        ret_dict = {}
        for k, v in jdict.items():
            _v = decode_any(v, args[1])
            ret_dict[k] = _v

        return ret_dict  # type: ignore

    elif is_set(t):
        args = get_args(t)
        if len(args) != 1:
            raise ValueError(f"Sets must be typed: {t}")

        if is_first_order(args[0]):
            return jdict  # type: ignore

        ret_list = []
        for v in jdict:
            _v = decode_any(v, args[0])
            ret_list.append(_v)

        return ret_list  # type: ignore

    elif is_list(t):
        args = get_args(t)
        if len(args) != 1:
            raise ValueError(f"Lists must be typed: {t}")

        if is_first_order(args[0]):
            return jdict  # type: ignore

        ret_list = []
        for v in jdict:
            _v = decode_any(v, args[0])
            ret_list.append(_v)

        return ret_list  # type: ignore

    elif is_tuple(t):
        args = get_args(t)

        ret_tuple = ()

        if len(jdict) != len(args):
            raise ValueError(f"Type given does not have enough args for object: {t}")

        for i, v in enumerate(jdict):
            _v = decode_any(v, args[i])
            ret_tuple = ret_tuple + (_v,)  # type: ignore

        return ret_tuple  # type: ignore

    elif is_union(t):
        args = get_args(t)

        if len(args) == 0:
            logging.warning("found union with no args")

        if len(args) == 2 and args[1] == NoneType:
            # Handle optionals
            args = (args[1], args[0])

        for i, arg in enumerate(args):
            if json_is_type_match(arg, jdict):
                return decode_any(jdict, arg)

        raise ValueError(f"No type matched JSON: {jdict}")

    elif t == Any:
        # TODO: handle any types, may need some basic checks similar to Union
        logging.warning("Given Any type to decode into, too generic")
        return jdict  # type: ignore

    elif is_enum(t):
        return t(jdict)

    elif hasattr(t, "__annotations__"):
        annots = get_type_hints(t)
        ret_obj = object.__new__(t)  # type: ignore

        for k, v in jdict.items():
            _v = decode_any(v, annots[k])
            setattr(ret_obj, k, _v)

        return ret_obj

    else:
        raise ValueError(f"Do not know how to load jdict '{jdict}' of type: {t}")
