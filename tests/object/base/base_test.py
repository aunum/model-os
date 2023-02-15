from typing import Iterator, Union, Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import logging
from enum import Enum

from modelos import Object
from modelos.scm import SCM
from nested.bar import Baz, Spam

logging.basicConfig(level=logging.INFO)


class Ham:
    a: str
    b: int

    def __init__(self, a: str, b: int) -> None:
        """A Ham object

        Args:
            a (str): A string
            b (int): An int
        """
        self.a = a
        self.b = b


class Eggs:
    h: Ham
    b: Dict[str, Ham]

    def __init__(self, h: Ham, b: Dict[str, Ham]) -> None:
        self.h = h
        self.b = b


class Foo(Object):
    """A simple Foo"""

    def test(self) -> None:
        """A test function"""
        print("hello")


class Bar(Object):
    """A Bar"""

    a: str
    b: int

    def __init__(self, a: str, b: int) -> None:
        """A Bar resource

        Args:
            a (str): A string
            b (int): An int
        """
        self.a = a
        self.b = b

    def echo(self, txt: str) -> str:
        """Echo a string back

        Args:
            txt (str): String to echo

        Returns:
            str: String echoed with a hello
        """
        return txt + " -- hello! " + "a: " + self.a + " b: " + str(self.b)

    def add(self, x: int, y: int) -> int:
        """Add x to y

        Args:
            x (int): Number
            y (int): Number

        Returns:
            int: Sum
        """
        return x + y

    def set(self, a: str, b: int) -> None:
        """Set the params

        Args:
            a (str): A string
            b (int): An int
        """
        self.a = a
        self.b = b

    def stream(self, a: str, num: int) -> Iterator[str]:
        """Stream back the string for the given number of times

        Args:
            a (str): String to stream
            num (int): Number of times to return

        Yields:
            Iterator[str]: An iterator
        """
        for i in range(num):
            yield f"{i}: {a}"

    def echo_ham(self, ham: Ham) -> Ham:
        """Echo a Ham

        Args:
            ham (Ham): Ham to echo

        Returns:
            Ham: Ham echoed
        """
        return ham

    def bake_hams(self, ham_by_name: Dict[str, Ham]) -> Dict[str, Ham]:
        """Bake the given hams

        Args:
            ham_by_name (Dict[str, Ham]): A map of Ham to name

        Returns:
            Dict[str, bool]: Whether the Hams were baked
        """
        ret: Dict[str, Ham] = {}
        for name, ham in ham_by_name.items():
            ret[name] = ham

        return ret

    def cook_eggs(self, egg_by_name: Dict[str, Eggs]) -> Dict[str, Eggs]:
        """Bake the eggs

        Args:
            egg_by_name (Dict[str, Ham]): A map of egg to name

        Returns:
            Dict[str, bool]: Whether the eggs were cooked
        """
        ret: Dict[str, Eggs] = {}
        for name, egg in egg_by_name.items():
            ret[name] = egg

        print("returning eggs: ", ret)
        return ret

    def echo_hams(self, hams: List[Ham]) -> List[Ham]:
        """Echo Hams

        Args:
            hams (List[Ham]): A list of Hams

        Returns:
            List[Ham]: A list of Hams
        """
        ret: List[Ham] = []

        for ham in hams:
            ret.append(ham)

        return ret

    def ham_tuple(self, hammy: Tuple[str, Ham]) -> Tuple[str, Ham]:
        """A Tuple of Hams

        Args:
            hammy (Tuple[str, Ham]): Name and Ham

        Returns:
            Tuple[str, Ham]: Name and Ham
        """
        return (hammy[0], hammy[1])


def test_simple_create():
    scm = SCM()

    FooClient = Foo.client(hot=True, dev_dependencies=True)

    # Create a remote instance
    print("creating foo")
    foo = FooClient()

    info = foo.info()
    print("foo info: ", info)
    assert info.name == "Foo"
    assert info.env_sha == scm.env_sha()

    print("foo labels: ", foo.labels())
    print("foo health: ", foo.health())
    print("foo test: ", foo.test())

    print("creating foo 2")
    foo2 = FooClient()

    print("foo2 info: ", foo2.info())
    print("foo2 labels: ", foo2.labels())

    print("deleting foo")
    foo.delete()

    print("foo2 health: ", foo2.health())
    print("foo2 test: ", foo2.test())

    print("delete foo2")
    foo2.delete()


def test_basic_ops():
    # Create a Bar client class with the given options
    print("creating bar")
    BarClient = Bar.client(hot=False, dev_dependencies=True, clean=False)

    # Create a remote Bar instance with the given parameters
    bar_client = BarClient("baz", 1)

    print("bar info: ", bar_client.info())
    print("testing echo basic")
    assert bar_client.echo("yellow") == "yellow" + " -- hello! " + "a: " + "baz" + " b: " + str(1)
    assert bar_client.add(1, 3) == 4
    bar_client.set("qoz", 5)
    assert bar_client.echo("yellow") == "yellow" + " -- hello! " + "a: " + "qoz" + " b: " + str(5)

    print("testing echo ham")
    ham_echoed = bar_client.echo_ham(Ham("d", 4))
    assert ham_echoed.__dict__ == Ham("d", 4).__dict__

    print("testing ham dicts")
    hams = bar_client.bake_hams({"charles": Ham("baz", 1), "yanni": Ham("foo", 2)})
    print("recieved hams: ", hams)
    assert hams["charles"].__dict__ == Ham("baz", 1).__dict__
    assert hams["yanni"].__dict__ == Ham("foo", 2).__dict__

    print("testing eggs dicts")
    eggs = bar_client.cook_eggs(
        {"jim": Eggs(Ham("baz", 1), {"mary": Ham("bar", 5)}), "bob": Eggs(Ham("foo", 2), {"anne": Ham("quz", 4)})}
    )
    print("recieved eggs: ", eggs)
    print("jim dict h: ", eggs["jim"].h.__dict__)
    print("jim dict b: ", eggs["jim"].b)
    print("jim dict b nested: ", eggs["jim"].b["mary"].__dict__)
    assert eggs["jim"].h.__dict__ == Ham("baz", 1).__dict__
    assert eggs["jim"].b["mary"].__dict__ == Ham("bar", 5).__dict__
    assert eggs["bob"].h.__dict__ == Ham("foo", 2).__dict__
    assert eggs["bob"].b["anne"].__dict__ == Ham("quz", 4).__dict__

    print("testing ham list")
    ham_list = bar_client.echo_hams([Ham("a", 1), Ham("b", 2)])
    assert len(ham_list) == 2
    assert ham_list[0].__dict__ == Ham("a", 1).__dict__
    assert ham_list[1].__dict__ == Ham("b", 2).__dict__

    print("testing ham tuple")
    name, hambone = bar_client.ham_tuple(("hambone", Ham("c", 3)))
    assert name == "hambone"
    assert hambone.__dict__ == Ham("c", 3).__dict__
    bar_client.delete()

    print("creating bar2")
    bar_client2 = Bar.client(dev_dependencies=True, clean=False)("qux", 2)

    print("bar2 info: ", bar_client2.info())
    print("bar2 echo blue: ", bar_client2.echo("blue"))
    assert bar_client2.echo("blue") == "blue" + " -- hello! " + "a: " + "qux" + " b: " + str(2)
    bar_client2.delete()


def test_stream():
    BarClient = Bar.client(dev_dependencies=True, clean=False)

    bar = BarClient("zoop", 6)
    for i, s in enumerate(bar.stream("test", 10)):
        assert s == f"{i}: test"

    bar.delete()


def test_save():
    BarClient = Bar.client(dev_dependencies=True, clean=False)

    print("creating and storing client")
    bar = BarClient("zoop", 6)
    bar.set("spam", 4)
    uri = bar.store()
    bar.delete()

    print("loading saved object from uri: ", uri)
    bar2 = Bar.from_uri(uri)
    msg = bar2.echo("eggs")
    print("echo msg: ", msg)
    assert msg == "eggs" + " -- hello! " + "a: " + "spam" + " b: " + str(4)
    bar2.delete()


def test_lock():
    BarClient = Bar.client(dev_dependencies=True, clean=False)

    print("creating and storing client")
    bar = BarClient("zoop", 6)
    bar.set("spam", 4)
    proc_uri = bar.process_uri
    info = bar.info()
    print("bar info: ", info)

    assert info.locked is False
    print("locking bar")
    bar.lock()
    info = bar.info()
    print("new bar info: ", info)
    assert info.locked is True
    assert bar.set("eggs", 3) is None

    print("Trying to connect to locked process: ", proc_uri)
    BarClient2 = Bar.client(uri=proc_uri)
    bar2 = BarClient2("ham", 6)
    assert bar2.health() == {"health": "ok"}
    info = bar2.info()
    print("bar2 info: ", info)
    assert info.locked is True

    try:
        bar.set("spam", 11)
        assert False
    except Exception:
        assert True

    bar.delete()
    bar2.delete()


def test_copy():
    BarClient = Bar.client(dev_dependencies=True, clean=False)

    print("creating client")
    bar = BarClient("ham", 6)
    bar.set("spam", 4)

    bar2 = bar.copy()
    msg = bar2.echo("eggs")
    print("copied msg: ", msg)
    assert msg == "eggs" + " -- hello! " + "a: " + "spam" + " b: " + str(4)

    bar.delete()
    bar2.delete()


def test_main_obj():
    scm = SCM()

    BazClient = Baz.client(dev_dependencies=True, clean=False)
    # Create a remote instance
    print("creating baz")
    baz = BazClient()

    info = baz.info()
    print("baz info: ", info)
    assert info.name == "Baz"
    assert info.env_sha == scm.env_sha()

    assert baz.ret("echoing back!", Spam("this", 2)) == "echoing back!"

    baz.delete()


class LotsOfUnions(Object):
    """An Object with lots of unions"""

    a: str
    b: List[str]
    c: bool

    def __init__(self, a: Union[str, int], b: Union[Dict[str, Any], List[str]], c: Optional[bool] = None) -> None:
        """A LotsOfUnions resource

        Args:
            a (Union[str, int]): An a
            b (Union[Dict[str, Any], List[str]]): A b
            c (Optional[bool], optional): A c. Defaults to None.
        """
        self.a = str(a)

        if isinstance(b, dict):
            b = list(b.keys())
        self.b = b

        if c is None:
            c = False
        self.c = c

    def echo(self, txt: Optional[str] = None) -> str:
        """Echo a string back

        Args:
            txt (str): String to echo

        Returns:
            str: String echoed with a hello
        """
        if txt is None:
            txt = "klaus"

        return txt + " -- hello! " + "a: " + self.a + " c: " + str(self.c)

    def returns_optional(self, a: Union[str, int]) -> Optional[str]:
        """Optionally returns the given string or returns None if int

        Args:
            a (Union[str, int]): A string or int

        Returns:
            Optional[str]: An optional string
        """
        if isinstance(a, int):
            return None
        else:
            return a

    def optional_obj(
        self, h: Union[Ham, Dict[str, Any]], return_dict: Optional[bool] = None
    ) -> Union[Ham, Dict[str, Any]]:
        """Receives either a Ham or a dictionary and optionally returns a ham

        Args:
            h (Union[Ham, Dict[str, Any]]): A Ham or a dictionary of Ham

        Returns:
            Union[Ham, Dict[str, Any]]: A Ham or nothing
        """
        if isinstance(h, dict):
            h = Ham(h["a"], h["b"])

        if return_dict:
            print("returning dictionary")
            ret = h.__dict__
            ret["c"] = True
            return ret

        print("not returning dictionary")
        return h

    def optional_lists(
        self, y: Union[List[Ham], Dict[str, Ham]], as_dict: bool = True
    ) -> Union[List[Ham], Dict[str, Ham]]:
        """Recieves lists and dictionaries of Ham

        Args:
            y (Union[List[Ham], Dict[str, Ham]]): A list or dictionary of Ham
            as_dict (bool, optional): Return as a dicdtionary. Defaults to True.

        Returns:
            Union[List[Ham], Dict[str, Ham]]: A list or a dictionary of Ham
        """
        if as_dict and type(y) == list:
            ret: Dict[str, Ham] = {}
            for i, v in enumerate(y):
                ret[str(i)] = v

            return ret
        return y

    def optional_tuples(self, x: Union[Tuple[str, Ham], Dict[str, Ham]]) -> Union[Tuple[str, Ham], Dict[str, Ham]]:
        """Handle optional tuples

        Args:
            x (Union[Tuple[str, Ham], Dict[str, Ham]]): A union of Tuple

        Returns:
            Union[Tuple[str, Ham], Dict[str, Ham]]: A union of Tuple
        """
        return x


def test_union():
    LouClient = LotsOfUnions.client(dev_dependencies=True, clean=False)

    print("=== testing echo")
    lou = LouClient(1, {"this": "that", "then": "there"}, True)
    msg = lou.echo("spam")
    print("msg1: ", msg)
    assert msg == "spam" + " -- hello! " + "a: " + "1" + " c: " + "True"

    msg = lou.echo()
    print("msg2: ", msg)
    assert msg == "klaus" + " -- hello! " + "a: " + "1" + " c: " + "True"

    assert lou.returns_optional("eggs") == "eggs"
    assert lou.returns_optional(1) is None

    print("=== testing optional object")
    a = lou.optional_obj(Ham("foo", 4))
    print("a: ", a.__dict__)
    assert a.__dict__ == Ham("foo", 4).__dict__

    # TODO: the following test fails because json_is_match matches the fields in Ham and ignores
    # the extra field, this likely needs to be solved by the optimization of returning
    # a `_type` field with all unions that tell which object it is

    # b = lou.optional_obj(Ham("bar", 5), True)
    # print("b: ", b)
    # assert b == {"a": "bar", "b": 5, "c": True}

    c = lou.optional_obj({"a": "baz", "b": 6})
    print("c: ", c.__dict__)
    assert c.__dict__ == Ham("baz", 6).__dict__

    print("=== testing optional lists")
    d = lou.optional_lists([Ham("a", 1), Ham("b", 2)], False)
    print("d: ", d)
    assert type(d) == list
    assert d[0].__dict__ == Ham("a", 1).__dict__
    assert d[1].__dict__ == Ham("b", 2).__dict__

    e = lou.optional_lists({"ham1": Ham("c", 3), "ham2": Ham("d", 4)})
    print("e: ", e)
    assert type(e) == dict
    assert e["ham1"].__dict__ == Ham("c", 3).__dict__
    assert e["ham2"].__dict__ == Ham("d", 4).__dict__

    f = lou.optional_lists([Ham("a", 1), Ham("b", 2)])
    print("f: ", f)
    assert type(f) == dict
    assert f["0"].__dict__ == Ham("a", 1).__dict__
    assert f["1"].__dict__ == Ham("b", 2).__dict__

    lou.delete()


class Nested(Object):
    """An object with many nested objects"""

    h: Ham
    d: Dict[str, Ham]
    lh: List[Ham]
    o: Optional[Ham]
    u: Union[str, Ham]

    def __init__(self, h: Ham, d: Dict[str, Ham], lh: List[Ham], u: Union[str, Ham], o: Optional[Ham] = None) -> None:
        self.h = h
        self.d = d
        self.lh = lh
        self.o = o
        self.u = u

    def get_d(self, name: str) -> Ham:
        if name not in self.d:
            raise ValueError("name not in object")
        return self.d[name]

    def set_d(self, name: str, ham: Ham) -> None:
        self.d[name] = ham
        return

    def get_h(self) -> Ham:
        return self.h

    def get_lh(self) -> List[Ham]:
        return self.lh

    def get_o(self) -> Optional[Ham]:
        return self.o

    def get_u(self) -> Union[str, Ham]:
        return self.u


def test_nested():
    NestedClient = Nested.client(dev_dependencies=True, clean=False)

    h = Ham("a", 1)
    d = {"a": Ham("a", 1), "b": Ham("b", 2)}
    lh = [Ham("x", 5), Ham("y", 4)]
    u = Ham("z", 10)
    nested1 = NestedClient(h, d, lh, u, None)

    assert nested1.get_h().__dict__ == h.__dict__

    assert nested1.get_d("a").__dict__ == Ham("a", 1).__dict__
    assert nested1.get_d("b").__dict__ == Ham("b", 2).__dict__

    nested1.set_d("c", Ham("c", 3))

    assert nested1.get_d("c").__dict__ == Ham("c", 3).__dict__

    try:
        nested1.get_d("z")
    except Exception as e:
        print("got exception: ", e)

    assert nested1.get_lh()[1].__dict__ == lh[1].__dict__
    assert nested1.get_o() is None
    assert nested1.get_u().__dict__ == u.__dict__

    uri = nested1.store(dev_dependencies=True)
    nested_restored = Nested.from_uri(uri)

    assert nested_restored.get_h().__dict__ == h.__dict__

    assert nested_restored.get_d("a").__dict__ == Ham("a", 1).__dict__
    assert nested_restored.get_d("b").__dict__ == Ham("b", 2).__dict__
    assert nested_restored.get_d("c").__dict__ == Ham("c", 3).__dict__

    assert nested_restored.get_lh()[1].__dict__ == lh[1].__dict__
    assert nested_restored.get_o() is None
    assert nested_restored.get_u().__dict__ == u.__dict__

    nested1.delete()
    nested_restored.delete()


@dataclass
class Data(Object):
    h: Ham
    d: Dict[str, Ham]
    lh: List[Ham]
    u: Union[str, Ham]
    o: Optional[Ham] = None

    def get_d(self, name: str) -> Ham:
        if name not in self.d:
            raise ValueError("name not in object")
        return self.d[name]

    def set_d(self, name: str, ham: Ham) -> None:
        self.d[name] = ham
        return

    def get_h(self) -> Ham:
        return self.h

    def get_lh(self) -> List[Ham]:
        return self.lh

    def get_o(self) -> Optional[Ham]:
        return self.o

    def get_u(self) -> Union[str, Ham]:
        return self.u


def test_dataclass():
    DataClient = Data.client(dev_dependencies=True, clean=False)

    h = Ham("a", 1)
    d = {"a": Ham("a", 1), "b": Ham("b", 2)}
    lh = [Ham("x", 5), Ham("y", 4)]
    u = Ham("z", 10)
    data1 = DataClient(h, d, lh, u, None)

    assert data1.get_h().__dict__ == h.__dict__

    assert data1.get_d("a").__dict__ == Ham("a", 1).__dict__
    assert data1.get_d("b").__dict__ == Ham("b", 2).__dict__

    data1.set_d("c", Ham("c", 3))

    assert data1.get_d("c").__dict__ == Ham("c", 3).__dict__

    try:
        data1.get_d("z")
    except Exception as e:
        print("got exception: ", e)

    assert data1.get_lh()[1].__dict__ == lh[1].__dict__
    assert data1.get_o() is None
    assert data1.get_u().__dict__ == u.__dict__

    uri = data1.store(dev_dependencies=True)
    print("creating dataclass from uri: ", uri)

    data_restored = Data.from_uri(uri)

    assert data_restored.get_h().__dict__ == h.__dict__

    assert data_restored.get_d("a").__dict__ == Ham("a", 1).__dict__
    assert data_restored.get_d("b").__dict__ == Ham("b", 2).__dict__
    assert data_restored.get_d("c").__dict__ == Ham("c", 3).__dict__

    assert data_restored.get_lh()[1].__dict__ == lh[1].__dict__
    assert data_restored.get_o() is None
    assert data_restored.get_u().__dict__ == u.__dict__

    data1.delete()
    data_restored.delete()


class EnumNums(Enum):
    RED = 1
    BLUE = 2
    GREEN = 3


class EnumStrings(Enum):
    ORANGE = "orange"
    APPLE = "apple"
    BANANA = "banana"


class Enumerated(Object):
    """A resource full of Enums"""

    n: EnumNums
    s: EnumStrings
    dn: Dict[str, EnumNums]

    def __init__(self, n: EnumNums, s: EnumStrings, dn: Dict[str, EnumNums]) -> None:
        self.n = n
        self.s = s
        self.dn = dn

    def set_n(self, n: EnumNums) -> None:
        self.n = n

    def get_n(self) -> EnumNums:
        return self.n

    def set_s(self, s: EnumStrings) -> None:
        self.s = s

    def get_s(self) -> EnumStrings:
        return self.s

    def get_dn(self, name: str) -> EnumNums:
        return self.dn[name]


def test_enum():
    EnumClient = Enumerated.client(dev_dependencies=True, clean=False)

    enum1 = EnumClient(EnumNums.BLUE, EnumStrings.APPLE, {"a": EnumNums.GREEN})

    assert enum1.get_n() == EnumNums.BLUE
    assert enum1.get_s() == EnumStrings.APPLE
    assert enum1.get_dn("a") == EnumNums.GREEN

    enum1.set_n(EnumNums.RED)
    assert enum1.get_n() == EnumNums.RED

    enum1.set_s(EnumStrings.ORANGE)
    assert enum1.get_s() == EnumStrings.ORANGE

    uri = enum1.store(dev_dependencies=True)

    enum_restored = Enumerated.from_uri(uri)
    assert enum_restored.get_n() == EnumNums.RED
    assert enum_restored.get_s() == EnumStrings.ORANGE
    assert enum_restored.get_dn("a") == EnumNums.GREEN

    enum_restored.delete()


def test_client():
    # how do we create from just the client? how do we store and install?

    from bar_client import BarClient  # noqa

    bar1 = BarClient("a", 1)
    print("echo: ", bar1.echo("world"))

    versions = BarClient.versions()
    print("versions: ", versions)

    BarClient.uri = versions[0]
    BarClient.hot = True

    bar1 = BarClient("b", 2)
    print("echo: ", bar1.echo("world"))


def test_logs():
    # ideally we should capture logs on the server side and return them to the client inline
    pass


def test_resources():
    pass


def test_notebook():
    pass


def test_numpy():
    # we need to make extensions for these types
    pass


def test_pandas():
    pass


def test_arrow():
    pass


def test_tf():
    pass


def test_torch():
    pass


def test_errors():
    pass


def test_source():
    pass


def test_diff():
    pass


def test_merge():
    pass


def test_sync():
    pass


def test_properties():
    pass


def test_set():
    pass


class Bacon(Ham):
    c: Dict[str, Any]

    def is_bacon(self) -> bool:
        return True


def test_derived():
    # We need to test if a derived object is provided or returned
    pass


def test_schema():
    pass


def test_generic():
    pass


def test_ui():
    pass


if __name__ == "__main__":
    # print("\n=====\ntesting simple create\n")
    # test_simple_create()

    print("\n=====\ntesting basic ops\n")
    test_basic_ops()

    # print("\n=====\ntesting stream\n")
    # test_stream()

    # print("\n=====\ntesting save\n")
    # test_save()

    # print("\n=====\ntesting lock\n")
    # test_lock()

    # print("\n=====\ntesting copy\n")
    # test_copy()

    # print("\n=====\ntesting main obj\n")
    # test_main_obj()

    # print("\n=====\ntesting union\n")
    # test_union()

    # print("\n=====\ntesting nested\n")
    # test_nested()

    # print("\n=====\ntesting nested\n")
    # test_dataclass()

    # print("\n=====\ntesting enums\n")
    # test_enum()

    # print("\n=====\ntesting client\n")
    # test_client()
