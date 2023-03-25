# Secrets

ModelOS should enable secure encrypted storage of objects

```python
from mdl import EncryptedObject

class Foo(EncryptedObject):
    secret_a: str

    def __init__(self, secret_a: str) -> None:
        self.secret_a = secret_a

FooRmt = Foo.remote(repo="acme.org/ml-project", group="Foos")

# Create an object that uses a secret
foo1 = FooRmt(secret_a=os.getenv("BAZ_KEY"))

# Store in OCI as an ecrypted object
foo1.store()
```

[Sig Store](https://www.sigstore.dev/) should be used here.