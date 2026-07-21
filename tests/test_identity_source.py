import pytest

from sat_sync.sources.base import IdentitySource


def test_identity_source_cannot_be_instantiated():

    with pytest.raises(TypeError):
        IdentitySource()
        

class DummySource(IdentitySource):
    pass


def test_identity_source_requires_implementation():

    with pytest.raises(TypeError):
        DummySource()