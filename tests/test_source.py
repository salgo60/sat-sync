import pytest

from sat_sync.sources.base import Source


def test_source_can_be_instantiated():
    source = Source()
    assert isinstance(source, Source)
    
