from modelos.pkg.id import PkgID


def test_pkg_id():
    uri = "aunum/ml-project:pkg.foo.v1.2.1"
    id = PkgID.parse(uri)
    assert id.host == "docker.io"
    assert id.repo == "aunum/ml-project"
    assert id.name == "foo"
    assert id.version == "v1.2.1"
    assert id.to_uri() == uri

    uri = "aunum.io/ml-project:pkg.foo-bar.fjjio-2io3j-7gh28"
    id = PkgID.parse(uri)
    assert id.host == "aunum.io"
    assert id.repo == "ml-project"
    assert id.name == "foo-bar"
    assert id.version == "fjjio-2io3j-7gh28"
    assert id.to_uri() == uri


if __name__ == "__main__":
    test_pkg_id()
