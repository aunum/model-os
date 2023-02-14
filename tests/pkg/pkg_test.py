import yaml
import os
import logging

from modelos.pkg import Pkg, clean

logging.basicConfig(level=logging.INFO)


def test_pkg_simple():
    repo = "aunum/mdl-test"
    name = "foo"

    print("--- cleaning repo")
    clean(repo, name, releases=True)

    current_dir = os.path.dirname(os.path.realpath(__file__))
    data_dir = os.path.join(current_dir, "./data/")

    pkg = Pkg(name, data_dir, "A foo package", repo=repo)

    print("--- showing pkg")
    pkg.show()

    pkg.push()

    files = pkg.ls()
    assert "foo.yaml" in files
    assert "bar.csv" in files
    assert "nested" in files

    with pkg.open("./foo.yaml") as f:
        b = f.read()
        ym = yaml.load(b, Loader=yaml.FullLoader)
        assert ym["name"] == "foo"
        assert ym["version"] == "v1.2.3"

    with pkg.open("./nested/baz.txt") as f:
        lines = f.readlines()
        assert lines[0] == "A Baz!"

    print("--- describing pkg")
    pkg.describe(str(pkg.id()))

    info = pkg.info()
    assert info.name == "foo"
    assert info.description == "A foo package"
    print("info version: ", info.version)
    print("pkg hash: ", pkg.hash())
    assert info.version == pkg.hash()

    assert pkg.latest() is None

    print("--- releasing pkg")
    pkg.release("v0.0.1", labels={"type": "foo"}, tags=["baz"])

    print("latest: ", pkg.latest())
    assert pkg.latest() == "v0.0.1"
    info = pkg.info()
    print("info version: ", info.version)
    print("info: ", info.__dict__)
    assert info.version == "v0.0.1"
    assert info.labels == {"type": "foo"}
    assert info.tags == ["baz"]
    assert info.name == "foo"
    assert info.description == "A foo package"

    print("--- deleting pkg")
    pkg.delete()

    print("--- creating new pkg")
    pkgv1 = Pkg(
        "foo", data_dir, description="A new foo", version="v0.0.1", repo=repo, labels={"type": "foov1"}, tags=["bar"]
    )

    with pkgv1.open("./foo.yaml") as f:
        b = f.read()
        ym = yaml.load(b, Loader=yaml.FullLoader)
        assert ym["name"] == "foo"
        assert ym["version"] == "v1.2.3"

    with pkgv1.open("./nested/baz.txt") as f:
        lines = f.readlines()
        assert lines[0] == "A Baz!"

    print("--- releasing pkg again")
    pkgv1.release()
    assert pkgv1.latest() == "v0.1.0"
    info = pkgv1.info()
    assert info.version == "v0.1.0"
    assert info.labels == {"type": "foov1"}
    assert info.tags == ["bar"]
    assert info.name == "foo"
    assert info.description == "A new foo"

    print("--- writing new file")
    with pkgv1.open("./new.txt", "w") as f:
        f.write("New!")

    print("--- releasing with new file")
    pkgv1.release()
    assert pkgv1.latest() == "v0.2.0"
    info = pkgv1.info()
    assert info.version == "v0.2.0"
    assert info.labels == {"type": "foov1"}
    assert info.tags == ["bar"]
    assert info.name == "foo"
    assert info.description == "A new foo"

    print("--- deleting pkg again")
    pkgv1.delete()


if __name__ == "__main__":
    test_pkg_simple()
