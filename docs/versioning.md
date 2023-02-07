# Resource Versioning 

## Adhoc

When developing, resources will contain a `store()` command which will use a versioning pattern of `<git-hash>-<dirty-hash>-<client-hash>`. It will also optionally push a branch name image in the form of `<branch-name>-<dirty-hash>-<client-hash>` if `branch=True`, or `branch_only=True`. Branch names will be sanitized

When hot syncing code and environment container will be built in the form of `

## Releases

Resources will contain a `release()` command which will generate tagged releases and SDKs. 

Releases will be versioned using semver like semantics e.g. `v1.2.1`. One can optionally tag the repo with `git_tag=True` in the form `mdl-<resource-name>-v1.2.1` so that the commit can be easily traced. If a user releases a resource on a branch other than the main branch it will be tagged `v1.2.1-<branch-name>` unless `force_main=True` is supplied

Versions will be auto-incremented based on the interface of the resource and changes to the repo. Incrementation will always happen from the closest commit version that can be found. This is much more efficient if `git_tag=True` is supplied.

On releases, the image will always be built with the adhoc tag of `<git-hash>-<dirty-hash>-<client-hash>` and then secondarily tagged with `v1.2.1`, this will enable us to easily find and reuse images for the current repo hash.

Python packages will be also be created for the client and server and stored as OCI artifacts in the form of `pkg-v1.2.1` and `client-v1.2.1`

### SemVer

The semver breakdown will be as follows:   

* `v1.*.*` designates the version of the client, this is currently done by creating a hash of the current client file but should later follow more robust API versioning semantics. An increment of this version can be forced by supplying `force_major=True`

* `v*.1.*` designates a change in the underlying server logic or model, __this change can be breaking__ and bumps in the version should always assume this possibility.

* `v*.*.1` designates a fully non-breaking change, such as documentation, and will only be incremented when `patch=True` is provided.

This will apply to both server containers and installable packages.

## Finding

To find versions, resources will contain a `versions()` command which will list all versions, with an optional `compatible=True` parameter, to find ones which are compatible with the current interface.

Resources will also contain a `releases()` command which will list only releases, as well as a `clean_versions()` command which will allow for the cleaning of non-released images from the repo.

For faster searching, an `Ocidex` resource will be created which indexes the OCI repositories.

## Using

Versions and releases can be used with the `from_uri()` and `from_version()` commands directly off the object.

On release, ModelOS will generate python client and server packages and store them as OCI artifacts. These artifacts can be used in the following flows

### Client
```bash
mdl install acme.org/ml-project:ham-client-v1
```
or
```python
from modelos import install

install("acme.org/ml-project:ham-client-v1")
```

```python
from ml_project.ham.client.v1 import HamClient

with HamClient("a", 1, True) as ham:
    ham.bake(temp=320)
```

To use a version:

```python
from ml_project.ham.client.v1 import HamClient

HamClient.version = "v1.4.2"

with HamClient("a", 1, True) as ham:
    ham.bake(temp=320)
```

### Resource

```bash
mdl install acme.org/ml-project:ham-pkg-v1.2.1
```
or
```python
from modelos import install

install("acme.org/ml-project:ham-pkg-v1.2.1")
```

```python
from ml_project.ham.v1_2_1 import Ham

# Use locally
temp = Ham.get_temp()
print("ham temp: ", temp)

# Use remotely
with Ham.client()("a", 1, True) as ham:
    ham.bake(temp=320)
```


## Roadmap

* We should consider moving more toward a model that extracts the exact dependencies for a resource, walks the dep tree, and pulls out only what that object needs. Similar to the Unison language

* We should also consider publishing to pypi