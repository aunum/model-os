import ast
import inspect
from dis import Bytecode
from typing import List, Type, Optional, Any, Set, get_args, get_type_hints
from types import NoneType
import logging
from inspect import signature

from unimport.main import Main as unimport_main
from black import format_str, FileMode

from modelos.util.notebook import get_notebook_class_code, find_import_statements, get_all_notebook_code
from modelos.object.encoding import (
    is_first_order,
    is_iterable_cls,
    is_tuple,
    is_list,
    is_optional,
    is_union,
    is_enum,
    is_dict,
    is_set,
)


def find_global_variable_node(source_code, variable_name):
    """Find the corresponding AST node for a global variable name"""
    tree = ast.parse(source_code)

    class GlobalVariableVisitor(ast.NodeVisitor):
        def __init__(self, variable_name):
            self.variable_name = variable_name
            self.variable_node = None

        def visit_Assign(self, node):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == self.variable_name:
                    self.variable_node = node
                    return

        def visit_Global(self, node):
            if self.variable_name in node.names:
                self.variable_node = node
                return

    visitor = GlobalVariableVisitor(variable_name)
    visitor.visit(tree)

    return visitor.variable_node


def _bytecode_analyzer(inst):
    from types import CodeType, FunctionType, ModuleType
    from importlib import import_module
    from functools import reduce

    if inst.opname == "IMPORT_NAME":
        path = inst.argval.split(".")
        path[0] = [import_module(path[0])]
        result = reduce(lambda x, a: x + [getattr(x[-1], a)], path)
        return ("modules", result)
    if inst.opname == "LOAD_GLOBAL":
        if inst.argval in globals() and type(globals()[inst.argval]) in [CodeType, FunctionType]:
            return ("code", globals()[inst.argval])
        if inst.argval in globals() and type(globals()[inst.argval]) == ModuleType:
            return ("modules", [globals()[inst.argval]])
        else:
            return None
    if "LOAD_" in inst.opname and type(inst.argval) in [CodeType, FunctionType]:
        return ("code", inst.argval)
    return None


# inspired from https://chapeau.freevariable.com/2017/12/module-frontier.html
def get_fn_globals(f) -> List[str]:
    """Get any globals used in a function

    Args:
        f (function): A function

    Returns:
        List[str]: A list of global var names
    """
    worklist = [f]
    seen = set()
    mods = set()
    global_vars = set()

    for fn in worklist:
        codeworklist = [fn]
        cvs = inspect.getclosurevars(fn)
        gvars = cvs.globals
        for k, v in gvars.items():
            global_vars.add(k)
            if inspect.isfunction(v) and id(v) not in seen:
                seen.add(id(v))
                mods.add(v.__module__)
                worklist.append(v)
            elif hasattr(v, "__module__"):
                mods.add(v.__module__)
        for block in codeworklist:
            for k, v in [_bytecode_analyzer(inst) for inst in Bytecode(block) if _bytecode_analyzer(inst)]:
                if k == "modules":
                    newmods = [mod.__name__ for mod in v if hasattr(mod, "__name__")]
                    mods.update(set(newmods))
                elif k == "code" and id(v) not in seen:
                    seen.add(id(v))
                    if hasattr(v, "__module__"):
                        mods.add(v.__module__)
                if inspect.isfunction(v):
                    worklist.append(v)
                elif inspect.iscode(v):
                    codeworklist.append(v)

    return list(global_vars)


def code_for_annotation(t: Type) -> Optional[List[str]]:
    """Get the corresponding code for a given annotation type

    Args:
        t (Type): Annotation type

    Returns:
        Optional[List[str]]: List of associated codes in the notebook
    """
    ret: List[str] = []

    def _code_for_annotation(t: Type):
        if t == NoneType or t is None or t == Any:
            pass
        if is_first_order(t):
            return
        elif (
            is_tuple(t) or is_list(t) or is_union(t) or is_dict(t) or is_optional(t) or is_iterable_cls(t) or is_set(t)
        ):
            args = get_args(t)
            for arg in args:
                _code_for_annotation(arg)
        elif is_enum(t):
            mod = inspect.getmodule(t)
            if mod and mod.__name__ == "__main__":
                try:
                    s = get_notebook_class_code(t)
                    ret.append(s)
                except Exception:
                    pass
        elif hasattr(t, "__annotations__"):
            annots = get_type_hints(t)
            for nm, typ in annots.items():
                _code_for_annotation(typ)
            mod = inspect.getmodule(t)
            if mod and mod.__name__ == "__main__":
                try:
                    s = get_notebook_class_code(t)
                    ret.append(s)
                except Exception:
                    pass
        else:
            mod = inspect.getmodule(t)
            if mod and mod.__name__ == "__main__":
                try:
                    s = get_notebook_class_code(t)
                    ret.append(s)
                except Exception:
                    pass

    _code_for_annotation(t)
    if ret:
        return ret
    return None


def get_bases(t: Type) -> Optional[List[Type]]:
    """Get bases for a type, not including the current or 'object'

    Args:
        t (Type): Type to get bases for

    Returns:
        Optional[List[Type]]: A list of bases if present or None.
    """
    mro = inspect.getmro(t)
    if len(mro) <= 2:
        return None
    mro = mro[1:-1]
    return list(mro)


def get_codes_for_cls(cls: Type) -> List[str]:
    """Get a list of codes related to a cls

    Args:
        cls (Type): The class

    Returns:
        List[str]: A list of codes
    """
    mod = inspect.getmodule(cls)
    if not mod or mod.__name__ != "__main__":
        logging.warning("trying to get code for cls outside of a notebook")
        return []
    code = get_all_notebook_code()
    fns = inspect.getmembers(cls, predicate=inspect.isfunction)
    methods = inspect.getmembers(cls, predicate=inspect.ismethod)

    fns.extend(methods)

    fin_codes: Set[str] = set()
    for name, fn in fns:
        globals = get_fn_globals(fn)
        for nm in globals:
            node = find_global_variable_node(code, nm)
            if not node:
                logging.warning(f"could not find ast node for global '{nm}'")
                continue
            cd = ast.unparse(node)
            fin_codes.add(cd)

        sig = signature(fn, eval_str=True, follow_wrapped=True)
        params = sig.parameters
        for nm in params:
            param = params[nm]
            t = param.annotation
            cds = code_for_annotation(t)
            if cds:
                for cd in cds:
                    fin_codes.add(cd)

        cds = code_for_annotation(sig.return_annotation)
        if cds:
            for cd in cds:
                fin_codes.add(cd)

    bases = get_bases(cls)
    if bases:
        for base in bases:
            cds = get_codes_for_cls(base)
            for cd in cds:
                fin_codes.add(cd)

    cls_code = get_notebook_class_code(cls)
    fin_codes.add(cls_code)

    return list(fin_codes)


def extract_cls_to_file(cls: Type) -> None:
    """Extract the given cls and its dependencies to a file

    Args:
        cls (Type): Class defiined in notebook to extract

    """
    ret_code = "# This code was generated by ModelOS\n"
    ret_code += "from __future__ import annotations\n"

    # get all import statements
    for stmt in find_import_statements():
        ret_code += stmt + "\n"

    # get all dependent objects
    for code in get_codes_for_cls(cls):
        ret_code += "\n"
        ret_code += code
        ret_code += "\n"

    ret_code = format_str(ret_code, mode=FileMode())

    fp = f"./obj_{cls.__name__.lower()}.py"
    with open(fp, "w+") as f:
        f.write(ret_code)

    unimport_main.run(["-r", fp])

    logging.info(f"sucessfully extracted class '{cls.__name__}' to file '{fp}'")
    return None
