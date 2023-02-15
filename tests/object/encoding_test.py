from typing import Dict, List, Union, Tuple, Optional
from types import NoneType
from dataclasses import dataclass
from enum import Enum

from deepdiff import DeepDiff

from modelos.object.encoding import encode_any, decode_any, json_is_type_match
from modelos.object.opts import OptsBuilder, Opts


class Ham:
    a: str
    b: int
    c: bool

    def __init__(self, a: str, b: int, c: bool) -> None:
        self.a = a
        self.b = b
        self.c = c


class Spam:
    h: Ham
    d: Dict[str, Ham]
    lh: List[Ham]
    u: Union[str, Ham]

    def __init__(self, h: Ham, d: Dict[str, Ham], lh: List[Ham], u: Union[str, Ham]) -> None:
        self.h = h
        self.d = d
        self.lh = lh
        self.u = u


@dataclass
class Data:
    e: int
    c: Ham
    b: Spam
    ext: Optional[Dict[str, str]] = None


def test_int():
    val = 1
    enc = encode_any(val, int)
    assert enc == {"value": 1}

    dec = decode_any(enc, int)
    assert dec == val


def test_str():
    val = "str"
    enc = encode_any(val, str)
    assert enc == {"value": "str"}

    dec = decode_any(enc, str)
    assert dec == val


def test_none():
    val = None
    enc = encode_any(val, NoneType)
    assert enc == {"value": None}

    dec = decode_any(enc, NoneType)
    assert dec == val


def test_bool():
    val = True
    enc = encode_any(val, bool)
    assert enc == {"value": True}

    dec = decode_any(enc, bool)
    assert dec == val


def test_list():
    val = ["a", "b"]
    enc = encode_any(val, List[str])
    assert enc == {"value": val}

    dec = decode_any(enc, List[str])
    assert len(DeepDiff(val, dec, ignore_order=True)) == 0


def test_list_obj():
    val = [Ham("a", 1, True), Ham("b", 2, False)]
    enc = encode_any(val, List[Ham])
    assert enc["value"][0] == Ham("a", 1, True).__dict__

    dec = decode_any(enc, List[Ham])
    assert len(DeepDiff(val, dec, ignore_order=True)) == 0


def test_dict():
    val = {"a": Ham("a", 1, True), "b": Ham("b", 2, False)}
    enc = encode_any(val, Dict[str, Ham])
    assert enc["a"] == Ham("a", 1, True).__dict__

    dec = decode_any(enc, Dict[str, Ham])
    assert len(DeepDiff(val, dec, ignore_order=True)) == 0


def test_tuple():
    val = ("hello", Ham("b", 2, False))
    enc = encode_any(val, Tuple[str, Ham])
    assert enc["value"][1] == Ham("b", 2, False).__dict__

    dec = decode_any(enc, Tuple[str, Ham])
    assert len(DeepDiff(val, dec, ignore_order=True)) == 0


class EnumNums(Enum):
    RED = 1
    BLUE = 2
    GREEN = 3


def test_enum():
    val = EnumNums.BLUE

    enc = encode_any(val, EnumNums)
    print("enc: ", enc)
    assert enc == {"value": 2}

    dec = decode_any(enc, EnumNums)
    assert dec == val


def test_union():
    print("ham annots start :", Ham.__annotations__)
    val = Ham("b", 2, False)
    enc = encode_any(val, Union[str, Ham])
    print("ham annots end: ", Ham.__annotations__)
    print("ham enc: ", enc)
    assert enc == Ham("b", 2, False).__dict__

    dec = decode_any(enc, Union[str, Ham])
    assert dec.__dict__ == val.__dict__

    val = {"ham1": Ham("a", 1, False), "ham2": Ham("b", 2, True)}
    enc = encode_any(val, Union[List[Ham], Dict[str, Ham]])
    assert enc["ham1"] == Ham("a", 1, False).__dict__
    assert enc["ham2"] == Ham("b", 2, True).__dict__

    dec = decode_any(enc, Union[List[Ham], Dict[str, Ham]])
    diff = DeepDiff(val, dec, ignore_order=True)
    assert len(diff) == 0


def test_nested():
    val = Spam(Ham("b", 2, False), {"a": Ham("b", 2, False)}, [Ham("b", 2, False)], Ham("b", 2, False))

    enc = encode_any(val, Spam)
    dec = decode_any(enc, Spam)

    diff = DeepDiff(val, dec, ignore_order=True)
    assert len(diff) == 0

    assert json_is_type_match(Spam, enc) is True


def test_dataclass():
    val = Data(
        1,
        Ham("b", 2, False),
        Spam(Ham("b", 2, False), {"a": Ham("b", 2, False)}, [Ham("b", 2, False)], Ham("b", 2, False)),
    )

    enc = encode_any(val, Data)
    assert json_is_type_match(Data, enc) is True
    dec = decode_any(enc, Data)
    assert len(DeepDiff(val, dec, ignore_order=True)) == 0


def test_ops():
    HamOpts = OptsBuilder[Opts].build(Ham)
    val = HamOpts("a", 1, False)

    enc = encode_any(val, HamOpts)
    dec = decode_any(enc, HamOpts)
    assert len(DeepDiff(val, dec, ignore_order=True)) == 0

    SpamOpts = OptsBuilder[Opts].build(Spam)
    val = SpamOpts(Ham("b", 2, False), {"a": Ham("b", 2, False)}, [Ham("b", 2, False)], Ham("b", 2, False))
    enc = encode_any(val, type(val))
    dec = decode_any(enc, type(val))
    assert len(DeepDiff(val, dec, ignore_order=True)) == 0


if __name__ == "__main__":
    test_int()
    test_bool()
    test_str()
    test_dict()
    test_list()
    test_list_obj()
    test_tuple()
    test_enum()
    test_union()
    test_nested()
    test_dataclass()
    test_ops()
