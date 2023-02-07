from modelos.env.image.file import Dockerfile


def test_dockerfile():
    dockerfile = Dockerfile()

    dockerfile.from_("python:3.10")
    dockerfile.workdir("/app")
    dockerfile.copy(".", "/app")
    dockerfile.copy([".", "test.py"], "/app")
    dockerfile.add(".", "/app")
    dockerfile.add([".", "test.py"], "/app")
    dockerfile.run("pip instal poetry")
    dockerfile.entrypoint(["python", "app.py"])
    dockerfile.cmd(["python", "app.py"])
    dockerfile.expose(8080, "udp")

    print(str(dockerfile))
