# Class Containers

The ModelOS object interface should change to support class methods and enable more efficient usage.

Roughly a python class should match to a container
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
FooRmt1 = Foo.remote(repo="acme.org/ml-project", group="Foos")

# Create two objects in that container
foo1 = FooRmt1(1, "bar")
foo1.echo()

foo2 = FooRmt1(2, "baz")
foo2.echo()

# Create another remote container in a different pod
FooRmt2 = Foo.remote(repo="acme.org/ml-project", group="Bars")

# Create two objects in that container
foo1 = FooRmt2(1, "bar")
foo1.echo()

foo2 = FooRmt2(2, "baz")
foo2.echo()

# Create an object using a class method
foo3 = FooRmt.default()
foo3.echo()

# Contexts should now work at both levels
with Foo.remote(repo="acme.org/ml-project", group="Bazs") as FooRmt:
    foo1 = FooRmt1(1, "bar")
    foo1.echo()

    with FooRmt1(2, "baz") as foo2:
        foo2.echo()

```

Using clients directly
```python
from foo_v1_2 import FooClient 

# Create a remote instance of the class
FooRmt = FooClient.remote(repo="acme.org/ml-project", group="Foos")

# Create two objects in that container
foo = FooRmt(1, "bar")
foo.echo()
```