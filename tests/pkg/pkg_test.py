import yaml
import os
import logging

from modelos.pkg import Pkg, clean
from modelos.pkg.repo.uri import remote_pkgrepo_from_uri

logging.basicConfig(level=logging.INFO)


def test_pkg_simple():
    remote = "aunum/mdl-test"
    name = "foo"

    print("\n--- cleaning repo")
    clean(remote, name, releases=True)

    print("\n--- creating pkg")
    current_dir = os.path.dirname(os.path.realpath(__file__))
    data_dir = os.path.join(current_dir, "./data/")

    pkg = Pkg(name, data_dir, "A foo package", remote=remote)

    print("\n--- showing pkg")
    pkg.show()

    print("\n--- pushing pkg")
    pkg.push()

    files = pkg.ls()
    assert "foo.yaml" in files
    assert "bar.csv" in files
    assert "nested" in files

    print("\n--- writing to pkg")
    with pkg.open("./foo.yaml") as f:
        b = f.read()
        ym = yaml.load(b, Loader=yaml.FullLoader)
        assert ym["name"] == "foo"
        assert ym["version"] == "v1.2.3"

    with pkg.open("./nested/baz.txt") as f:
        lines = f.readlines()
        assert lines[0] == "A Baz!"

    print("\n--- describing pkg")
    remote_repo = remote_pkgrepo_from_uri(remote)
    pkg_uri = remote_repo.build_uri(pkg.id())
    pkg.describe(pkg_uri)

    info = pkg.info()
    assert info.name == "foo"
    assert info.description == "A foo package"
    assert info.version == pkg.hash()

    assert pkg.latest() is None

    print("\n--- releasing pkg")
    pkg.release("v0.0.1", labels={"type": "foo"}, tags=["baz"])

    assert pkg.latest() == "v0.0.1"
    info = pkg.info()
    assert info.version == "v0.0.1"
    assert info.labels == {"type": "foo"}
    assert info.tags == ["baz"]
    assert info.name == "foo"
    assert info.description == "A foo package"

    print("\n--- deleting pkg")
    pkg.delete()

    print("\n--- creating new pkg")
    pkgv1 = Pkg(
        "foo",
        data_dir,
        description="A new foo",
        version="v0.0.1",
        remote=remote,
        labels={"type": "foov1"},
        tags=["bar"],
    )

    with pkgv1.open("./foo.yaml") as f:
        b = f.read()
        ym = yaml.load(b, Loader=yaml.FullLoader)
        assert ym["name"] == "foo"
        assert ym["version"] == "v1.2.3"

    with pkgv1.open("./nested/baz.txt") as f:
        lines = f.readlines()
        assert lines[0] == "A Baz!"

    print("\n--- releasing pkg again")
    pkgv1.release()
    assert pkgv1.latest() == "v0.1.0"
    info = pkgv1.info()
    assert info.version == "v0.1.0"
    assert info.labels == {"type": "foov1"}
    assert info.tags == ["bar"]
    assert info.name == "foo"
    assert info.description == "A new foo"

    print("\n--- writing new file")
    with pkgv1.open("./new.txt", "w") as f:
        f.write("New!")

    print("\n--- releasing with new file")
    pkgv1.release()
    assert pkgv1.latest() == "v0.2.0"
    info = pkgv1.info()
    assert info.version == "v0.2.0"
    assert info.labels == {"type": "foov1"}
    assert info.tags == ["bar"]
    assert info.name == "foo"
    assert info.description == "A new foo"

    print("\n--- modifying file")
    with pkgv1.open("./new.txt", "a") as f:
        f.write("appended!")

    print("\n--- releasing with modified file")
    pkgv1.release()
    assert pkgv1.latest() == "v1.0.0"
    info = pkgv1.info()
    assert info.version == "v1.0.0"
    assert info.labels == {"type": "foov1"}
    assert info.tags == ["bar"]
    assert info.name == "foo"
    assert info.description == "A new foo"

    print("\n--- deleting pkg again")
    pkgv1.delete()

    print("\n--- cleaning repo")
    clean(remote, name, releases=True)


if __name__ == "__main__":
    test_pkg_simple()
