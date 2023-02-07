from modelos import Object


class Spam:
    a: str
    b: int

    def __init__(self, a: str, b: int) -> None:
        """A Spam resource

        Args:
            a (str): A string
            b (int): An int
        """
        self.a = a
        self.b = b


class Baz(Object):
    """A simple Baz"""

    def ret(self, a: str, b: Spam) -> str:
        """A test function"""
        return a
