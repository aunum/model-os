from modelos.virtual.container.id import ImageID


def test_from_ref():
    id = ImageID.from_ref("aunum.io/ml-project:obj-ham-v1.2.3")
    assert id.host == "aunum.io"
    assert id.repository == "ml-project"
    assert id.tag == "obj-ham-v1.2.3"

    id = ImageID.from_ref("aunum/ml-project:obj-ham-v1.2.3")
    assert id.host == "docker.io"
    assert id.repository == "aunum/ml-project"
    assert id.tag == "obj-ham-v1.2.3"

    id = ImageID.from_ref("gcr.io/google-samples/hello-app:1.0")
    assert id.host == "gcr.io"
    assert id.repository == "google-samples/hello-app"
    assert id.tag == "1.0"

    id = ImageID.from_ref("e9ae3c220b23.dkr.ecr.us-west-1.amazonaws.com/ml-project:1.0")
    assert id.host == "e9ae3c220b23.dkr.ecr.us-west-1.amazonaws.com"
    assert id.repository == "ml-project"
    assert id.tag == "1.0"


if __name__ == "__main__":
    test_from_ref()
