# ![logo](./static/L_blue.svg)
An operating system for machine learning

## Installation
```
pip install model-os
```
> **_NOTE:_**  ModelOS is pre-alpha and under heavy development, expect breakage

ModelOS requires a working Kubernetes cluster, to get a local one try [KinD](https://kind.sigs.k8s.io/)
## Concepts
ModelOS adds capabilities to Python objects, it can help you:

* __Run__ objects remotely
* __Store__ objects with their state for later use
* __Share__ objects with teammates or the public
* __Combine__ objects in a distributed manner
* __Access__ objects from any language
* __Publish__ objects as independently versioned packages
* __Extract__ objects from notebooks
* __Find__ objects based on tags and labels
* __Visualize__ objects as they interact
* __Version__ objects automatically based on their logic and state

To understand the direction of the project see [our slides](https://docs.google.com/presentation/d/1U51kZ2KyljTgodxCfSrJDlEvKQQKLWMjFYaY0XI5c3M/edit?usp=sharing). 

tl;dr Blending the best ideas from [Ray](https://www.ray.io/) & [Huggingface](https://huggingface.co/) & [Pathways](https://blog.google/technology/ai/introducing-pathways-next-generation-ai-architecture/)

## Quick Start

```python
from mdl import Object

# Inherit Object on any typed Python class
class Foo(Object):

    bar: int

    def __init__(self, bar: int) -> None:
        self.bar = bar

    def echo(self, word: str) -> str:
        return f"{self.bar} {word}"

    def inc(self) -> None:
        self.bar += 1

# Create a client for the object capabale of spawning remote instances
FooClient = Foo.client(repo="acme.org/ml-project")

# Create a remote instance that only lives within the context
with FooClient(10) as foo:

    # Use the object just as you normally would
    assert foo.echo("cats") == "10 cats"

    # Update the object's state
    foo.inc()

    # Store the object
    uri = foo.store()

# Load the stored object as a remote process
with Foo.from_uri(uri) as foo:

    # Check that the state update was restored
    assert foo.echo("cats") == "11 cats"

    # Release the object, generating client and server packages
    uri = foo.release()

    # The release semver is automatically calculated
    assert uri == "acme.org/ml-project:obj.foo.v1.2.3"

# Dynamically load the object class at the given version
Foo = load("acme.org/ml-project:obj.foo.v1.2.3")

# Get the OpenAPI schema for the object
Foo.schema()
```
See more [examples in docs](./examples/)

## Usage

### Objects

Objects are distributed persistent Python objects.

A sample object
```python
from mdl import Object

class Foo(Object):

    id: str
    amount: int

    def __init__(self, id: str, amount: int) -> None:
        self.id = id
        self.amount = amount

    def add(self, amount: int) -> None:
        self.amount += amount

    def echo(self, s: str) -> str:
        return f"hello {s}"

    def stream(self, s: str) -> Iterable[str]:
        for i in range(self.amount):
            yield f"hello {s} {i}"

```

ModelOS objects work just like Python objects with some extra capabilities.

#### Developing Objects
Develop on the object remotely
```python
# Create a client which can be used to generate remote instances
FooClient = Foo.client(repo="acme.org/ml-project")

# Creates a remote instance
foo = FooClient(name="bar", amount=7)
foo.add(6)

# Iterable types automaticallly generate websocket streams
for s in foo.stream("baz"):
    print(s)

# Store the object with its updated state
uri = foo.store()
```

#### Releasing Objects
Release the object to be used by others. This creates a semver for the object and client/server packages
```python
FooClient = Foo.client()

# Creates a remote instance within the context then deletes it
with FooClient(name="bar", amount=7) as foo:
    foo.add(2)

    # release version is automatically calculated based on object state
    uri = foo.release()
```
Example release URI: `acme.org/ml-project:obj.foo.v1.2.3`   

#### Using Objects
Install a client from a release and use it to generate a remote instance

```sh
$ mdl install foo --client

successfully installed foo_client_v1
```

```python
from foo_client_v1 import FooClient

foo = FooClient(amount=10)
foo.echo("bar")
```

Install a class and use locally or remotely
```sh
$ mdl install foo -v 1.2

successfully installed foo_v1_2
```
```python
from foo_v1_2 import Foo

# locally
foo = Foo(amount=12)
foo.add(5)

# remotely
foo = Foo.client()(amount=10)
foo.echo("bar")
```

Install an instance and use it locally
```sh
$ mdl install foo -v 1.2.3

successfully installed foo_v1_2_3
```
```python
from foo_v1_2_3 import Foo

# load the object instance state
foo = Foo.from_env()

foo.echo("bar")
```

Use an object dynamically
```python
from mdl import load

Foo = load("foo", version="v1.2.3")

foo = Foo.client()(amount=10)
foo.echo("bar")
```

Install an object from a full URI
```sh
$ mdl install acme.org/ml-project:obj.foo.v1.2.3

successfully installed ml_project_foo_v1_2_3
```
```python
from ml_project_foo_v1_2_3 import Foo

foo = Foo.from_env()

foo.echo("bar")
```

An example working project can be found at https://github.com/pbarker/kvd

#### Examples

A text classifier
```python
from mdl import Object
from simpletransformers.classification import ClassificationModel, ClassificationArgs
import pandas as pd


class TextClassifier(Object):
    model: ClassificationModel

    def __init__(self, model_args: ClassificationArgs) -> None:
        self.model = ClassificationModel("bert", "bert-base-cased", num_labels=3, args=model_args)

    def train(self, df: pd.DataFrame) -> None:
        self.model.train_model(df)

    def predict(self, txt: str) -> List[int]:
        preds, _ = self.model.predict([txt])
        return preds


TextClassifierClient = TextClassifier.client(hot=True)
model_args = ClassificationArgs(num_train_epochs=1)

with TextClassifierClient(model_args) as model:
    train_data = [
        ["Aragorn was the heir of Isildur", 1],
        ["Frodo was the heir of Isildur", 0],
    ]
    train_df = pd.DataFrame(train_data)
    train_df.columns = ["text", "labels"]

    model.train(train_df)
    uri = model.store("acme.org/ml-project")

model = TextClassifier.from_uri(uri)
preds = model.predict("Merrry is stronger than Pippin")
```

See more [examples in docs](./examples/)

## Packages
Packages are versioned filesystems with support for large files

```python
from mdl import Pkg, clean

# Create a new package from the ./data dir
pkg = Pkg("foo", "./data", "A foo package", remote="acme.org/ml-project")

# See package contents
pkg.show()

# Push the package to its remote
pkg.push()

# List files in the package
files = pkg.ls()

# Open a file in the package
with pkg.open("./foo.yaml") as f:
    b = f.read()

# Release the package
pkg.release("v0.0.1", labels={"type": "foo"}, tags=["baz"])

# Check the latest package is our release
assert pkg.latest() == "v0.0.1"

# Delete the package
pkg.delete()

# Describe a remote package
info = Pkg.describe("acme.org/ml-project:pkg.fs.bar.v1.2.3")

# Use a remote package
bar_pkg = Pkg("bar", version="v1.2.3", remote="acme.org/ml-project")

# Clean packages
clean("acme.org/ml-project", "foo")
```

See the [tests](./tests/pkg/pkg_test.py) for more examples

## Roadmap

- [ ] Releasing
- [ ] Properties
- [ ] Packages
- [ ] Environments
- [ ] Runtimes
- [ ] Extension objects
- [ ] Finding / indexing
- [ ] Docs / landing
- [ ] UI / CLI
- [ ] Schema
- [ ] Bi-directional streaming
- [ ] Smarter versioning
- [ ] Checkpoint API
