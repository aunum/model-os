# Core Types

The core types of ModelOS

## Repo
Repositories are [OCI compliant](https://opencontainers.org/) repositories and are used to store ModelOS state

```sh
$ mdl add acme.org/ml-project
```
or in Python

```python
from modelos import Repo

Repo.add("acme.org/ml-project")
```

List contents of repo

```sh
$ mdl list repo

URI                                                LAST_UPDATED
acme.org/ml-project:obj.ham.v1.2.3                 2020-02-04 07:46:29
acme.org/ml-project:pkg.mnist.v2.1.3               2022-08-12 21:30:10
acme.org/ml-project:env.ml-project.fi3j450         2021-03-11 13:54:31
acme.org/ml-project:fn.echo.v1.1.5                 2021-01-02 08:28:36
```

## Object
Objects are distributed Python objects

A sample object
```python
from modelos import Object

class Ham(Object):

    temp: int
    weight: int
    brand: str

    def __init__(self, weight: int, brand: str) -> None:
        self.weight = weight
        self.brand = brand

    def bake(self, temp: int) -> None:
        self.temp = temp

    def cut(self, weight: int) -> int:
        self.weight = self.weight - weight
        return self.weight

```

### Developing Objects
Develop on the object remotely
```python
# Create a client which can be used to generate remote instances
HamClient = Ham.client(hot=True)

# Creates a remote instance within the context then deletes it
with HamClient(weight=12, brand="black forest") as ham:
    ham.bake(temp=340)

    # Store the object
    uri = ham.store()
```
Example develop URI: `acme.org/ml-project:obj.ham.f2oij-2oijr-f8g2n`


### Releasing Objects
Release the object to be used by others. This creates a semver for the object and client/server packages
```python
HamClient = Ham.client()

# Creates a remote instance within the context then deletes it
with HamClient(weight=14, brand="honey baked") as ham:
    ham.bake(temp=340)

    uri = ham.release()
```
Example release URI: `acme.org/ml-project:obj.ham.v1.2.3`   

#### Versioning scheme

__v1__: interface version   
__v1.2__: class version   
__v1.2.3__: instance version   

### Using Objects
Install a client from a release and use it to generate a remote instance
```python
from modelos import install

install("acme.org/ml-project:obj.ham.v1")

from ml_project.ham.v1 import HamClient

# Use the latest release
with HamClient(weight=10) as ham:
    ham.bake(temp=320)

# Specify a class release version
HamClient.version = "v1.2"

with HamClient(weight=10) as ham:
    ham.bake(temp=320)

# Specify an object version
with HamClient.instance("v1.2.3") as ham:
    ham.bake(temp=320)
```

Install a class and use locally or remotely
```python
from modelos import install

install("acme.org/ml-project:obj.ham.v1.2")

from ml_project.ham.v1_2 import Ham

# locally
ham = Ham(weight=12)
ham.bake(temp=300)

# remotely
with Ham.client()(weight=10) as ham:
    ham.bake(temp=320)
```

Install an object and use it locally
```python
from modelos import install

install("acme.org/ml-project:obj.ham.v1.2.3")

from ml_project.ham.v1_2_3 import Ham

# load the object state
ham = Ham.from_env()

ham.bake(temp=400)
```

### Finding Objects
List objects
```sh
$ mdl list obj

NAME       LATEST_VERSION    REPO
ham        v1.2.1            acme.org/ml-project
```

List running processes
```sh
$ mdl ps

NAME           PROCESS                                URI
ham            k8s://ham-v1-2-3-e0skr.default         acme.org/ml-project:obj-ham-v1.2.3
```

## Packages
Packages are immutable versioned filesystems

```sh
$ mdl push ./mnist/ mnist --version v1.2.3
```

This will result in an artifact like `acme.org/ml-project:pkg.mnist.v1.2.3`


List all packages
```sh
$ mdl pkgs list
NAME          VERSION
mnist         v1.3.2
```

Pull a package into `$MDL_PKG_HOME`
```sh
$ mdl pull mnist -v 1.2.3
```

Open a shell in the package
```
$ mdl sh acme.org/ml-project:pkg-mnist-v1.2.3
```

Use a package from Python
```python
from modelos import Pkg

# Create a package
uri = Pkg.push("./mnist/", "mnist", "v1.2.3")

# Get the package
pkg = Pkg.pull("acme.org/ml-project:pkg.mnist.v1.2.3")

# List contents of the package
pkg.ls()

# Open a file from the package
with pkg.open("/data/train.csv") as f:
    train_csv = f.read()
```

## Environments
Environments are Python environments that can be used to execute code remotely

URI Example: `acme.org/ml-project:env.ml-project.f93jf-owjr4-82kvi`

```sh
$ mdl build --push
```

```python
from modelos import Env

env = Env.build(push=True)
```

_In progress_

## Functions

Functions are stateless Python functions

URI Example: `acme.org/ml-project:fn.echo.v1.3.2`

```python
from modelos import fn

@fn
def echo(msg: str) -> str:
    return str
```

_In progress_

## CLI

```
$ mdl

Macros:
    build       Build a containerized environment for this project
    run         Run Python remotely
    install     Install objects
    pull        Pull data
    push        Push data
    add         Add a repository
    list        List all things
    ps          Show running objects
    ls          List package contents
    clean       Clean all
    sync        Sync code remotely
    load        Get all clients for current processes
    ctx         The current operating context
    ensure      Ensure the runtime is setup for ModelOS
    notebook    Open a notebook for the repo
    sh          Open a shell
    ui          Open the UI

Command Groups:
    repo        Repository actions
    obj         Distributed objects
    fn          Distributed functions
    pkg         Package actions
    env         Development environments
    runtime     Runtime commands

```


# FAQ

#### Why OCI everything

* Everyone has access to an image registry and they are durable
* OCI artifacts enable use to store arbitrary code in these registries
* Git can't store binaries well
* Pypi is hard to stand up and manage internally
* Clean consistent versioning scheme
* Simplicity!