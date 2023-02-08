from pathlib import Path
import os

MDL_HOME_ENV = "MDL_HOME"
PKG_HOME_ENV = "MDL_PKG_HOME"
GLOBAL_CONGIG_ENV = "MDL_CONFIG_PATH"


def mdl_home() -> str:
    """ModelOS home directory"""

    home_env = os.environ.get(MDL_HOME_ENV)
    if home_env:
        return home_env

    home = Path.home().joinpath(".mdl/")
    return str(home)


def pkg_home() -> str:
    """Pkg home directory"""

    pkg_env = os.environ.get(PKG_HOME_ENV)
    if pkg_env:
        return pkg_env

    home = Path(mdl_home()).joinpath("pkg/")
    return str(home)


def global_config_path() -> str:
    """Path of the global config"""

    cfg_env = os.environ.get(GLOBAL_CONGIG_ENV)
    if cfg_env:
        return cfg_env

    path = Path(mdl_home()).joinpath("config.yaml")
    return str(path)
