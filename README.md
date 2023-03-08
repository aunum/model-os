# ![logo](./static/L_blue.svg)
An operating system for machine learning

## Installation
```
pip install modelos
```

## Docs 

To understand the direction of the project see [our slides](https://docs.google.com/presentation/d/1U51kZ2KyljTgodxCfSrJDlEvKQQKLWMjFYaY0XI5c3M/edit?usp=sharing)

## Usage

> **_NOTE:_**  ModelOS is pre-alpha and under heavy development, expect breakage

### Objects

Objects are distributed persistent Python objects.

A sample object
```python
from modelos import Object

class Foo(Object):

    name: str
    amount: int

    def __init__(self, name: str, amount: int) -> None:
        self.name = name
        self.amount = amount

    def add(amount: int) -> None:
        self.amount += amount

    def echo(s: str) -> str:
        return f"hello {s}"

    def stream(s: str) -> Iterable[str]:
        for i in range(self.amount):
            yield f"hello {s} {i}"

```

ModelOS objects work just like Python objects with some extra capabilities.

#### Developing Objects
Develop on the object remotely
```python
# Create a client which can be used to generate remote instances
FooClient = Foo.client(hot=True, repo="acme.org/ml-project")

# Creates a remote instance within the context then deletes it
with FooClient(name="bar", amount=7) as foo:
    foo.add(6)

    for s in foo.stream("baz"):
        print(s)

    # Store the object with its updated state
    uri = foo.store()
```
Example develop URI: `acme.org/ml-project:obj.foo.f2oij-2okzr-f8g2n`


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
```python
from modelos import install_client

# Install the latest client within a major version
install_client("acme.org/ml-project:obj.foo.v1")

from ml_project.foo.v1 import FooClient

# Use the latest release
with FooClient(amount=10) as foo:
    foo.echo("bar")

# Specify a class release version
FooClient.version = "v1.2"

with FooClient(amount=10) as foo:
    foo.echo("bar")

# Specify an instance version
with FooClient.instance("v1.2.3") as foo:
    foo.echo("bar")
```

Install a class and use locally or remotely
```python
from modelos import install

install("acme.org/ml-project:obj.foo.v1.2")

from ml_project.foo.v1_2 import Foo

# locally
foo = Foo(amount=12)
foo.add(5)

# remotely
with Foo.client()(amount=10) as foo:
    foo.echo("bar")
```

Install an instance and use it locally
```python
from modelos import install

install("acme.org/ml-project:obj.foo.v1.2.3")

from ml_project.foo.v1_2_3 import Foo

# load the object instance state
foo = Foo.from_env()

foo.echo("bar")
```

An example working project can be found at https://github.com/pbarker/kvd

#### Examples

A text classifier
```python
from modelos import Object
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
Packages are versioned filesystems

```python
from modelos.pkg import Pkg, clean

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
