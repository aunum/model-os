import os


def list_files(startpath: str, base_idt: str = "", include_root: bool = False):
    """Print files in a tree format

    Args:
        startpath (str): Path to list
        base_idt (str, optional): Base indent for the whole tree. Defaults to "".
        include_root (bool, optional): Whether to include the root dir. Defaults to False.
    """
    for root, _, files in os.walk(startpath):
        if os.path.basename(os.path.normpath(root)) == ".mdl":
            continue
        level = root.replace(startpath, "").count(os.sep)
        indent = " " * 4 * (level)
        if not include_root and root != startpath:
            print("{}{}{}/".format(base_idt, indent, os.path.basename(root)))
        subindent = " " * 4 * (level + 1)
        for f in files:
            print("{}{}{}".format(base_idt, subindent, f))
