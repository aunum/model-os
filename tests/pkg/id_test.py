from modelos.pkg.repo import OCIPkgRepo


def test_pkg_id():
    uri = "aunum/ml-project:pkg.fs.foo.v1.2.1"
    id = OCIPkgRepo.parse(uri)
    assert id.host == "docker.io"
    assert id.repo == "aunum/ml-project"
    assert id.name == "foo"
    assert id.scheme == "fs"
    assert id.version == "v1.2.1"

    uri = "aunum.io/ml-project:pkg.py.foo-bar.fjjio-2io3j-7gh28"
    id = OCIPkgRepo.parse(uri)
    assert id.host == "aunum.io"
    assert id.repo == "ml-project"
    assert id.name == "foo-bar"
    assert id.scheme == "py"
    assert id.version == "fjjio-2io3j-7gh28"


if __name__ == "__main__":
    test_pkg_id()
