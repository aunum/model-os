from dataclasses import make_dataclass, is_dataclass, field
from typing import Generic, TypeVar, Type, Optional
import inspect
import json

from modelos.util.generic import RuntimeGeneric
from modelos.object.encoding import encode_any


class Opts:
    """Options for a resource"""

    def to_json(self) -> str:
        """Convert the opts to JSON string

        Returns:
            str: JSON string
        """
        jdict = encode_any(self, type(self))
        return json.dumps(jdict)


M = TypeVar("M")


class OptsBuilder(RuntimeGeneric, Generic[M]):
    @classmethod
    def build(cls, reg_cls: Type) -> Optional[Type[M]]:
        """Generate a dataclass for a class

        Args:
            reg_cls: (Type): A regular python class to convert to a dataclass

        Returns:
            Type[M]: A Dataclass that inherits Type[M]
        """
        if is_dataclass(cls):
            raise ValueError("cannot create a dataclass from a dataclass")

        sig: inspect.Signature = inspect.signature(reg_cls.__init__)
        fin_params = []
        for param in sig.parameters:
            if param == "self":
                continue
            if sig.parameters[param].default == inspect._empty:
                # TODO: we may need to handle this in the future and just return a type of optional
                if param != "args" and param != "kwargs":
                    fin_params.append((param, sig.parameters[param].annotation))
            else:
                fin_params.append(
                    (
                        param,
                        sig.parameters[param].annotation,
                        field(default=sig.parameters[param].default),
                    )  # type: ignore
                )
        if len(fin_params) == 0:
            return None
        generic_args = cls.__args__  # type: ignore
        if len(generic_args) == 0:
            return make_dataclass(reg_cls.__name__ + "Opts", fin_params)
        else:
            return make_dataclass(reg_cls.__name__ + "Opts", fin_params, bases=generic_args)
