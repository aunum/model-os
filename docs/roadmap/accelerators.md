# Accelerators

ModelOS should support accelerators

```python
from mdl import Object

class Foo(Object):
    a: int
    b: str

    def __init__(self, a: int, b: str) -> None:
        self.a = a
        self.b = b

    @classmethod
    def default(cls) -> Foo:
        return cls(1, "bar")

    def echo(self) -> str:
        return f"{self.a} {self.b}"


# Create a remote container in a pod referenced by the group
# will fail if the pod doesn't support GPU
FooRmt1 = Foo.remote(repo="acme.org/ml-project", group="Foos", gpu=1)

# Create two objects in that container
foo1 = FooRmt1(1, "bar")
foo1.echo()
```