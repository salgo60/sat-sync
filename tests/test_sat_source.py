from pathlib import Path

from sat_sync.sources.sat import SATSource


def test_load_sat_identities():

    source = SATSource()

    identities = source.identities(
        Path("sat_sync/data/sat.json")
    )

    assert len(identities) > 0