import yaml

from modelos.pkg import Pkg


def test_pkg():
    pkg = Pkg.push("./data/", "foo", "A foo pkg", "v1.2.3", {"type": "foo"})
    pkg.describe()

    files = pkg.ls()
    assert "foo.yaml" in files
    assert "bar.csv" in files
    assert "nested" in files

    with pkg.patch() as patch:
        patch.write()

    with pkg.open("./foo.yaml") as f:
        b = f.read()
        ym = yaml.load(b)
        assert ym["name"] == "foo"
        assert ym["version"] == "v1.2.3"

    with pkg.open("./nested/baz.txt") as f:
        lines = f.readlines()
        assert lines[0] == "A Baz!"


if __name__ == "__main__":
    test_pkg()
