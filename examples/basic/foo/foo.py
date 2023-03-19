from typing import Iterable

from modelos import Object


class Foo(Object):
    a: str

    def __init__(self, a: str) -> None:
        self.a = a

    def echo(self, s: str) -> str:
        return s

    def stream(self, num: int) -> Iterable[str]:
        for i in range(num):
            yield (str(i))


if __name__ == "__main__":
    FooClient = Foo.client()

    with FooClient(a="bar") as foo:
        assert foo.echo("this") == "this"

        for s in foo.stream(10):
            print(s)

        foo.store()
