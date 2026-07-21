import json
from pathlib import Path

from sat_sync.sources.base import Source

def test_load_sat_identities():

    source = SATSource()

    identities = source.identities(
        Path("sat_sync/data/sat.json")
    )

    assert len(identities) > 0


def test_sat_source_reads_identities(tmp_path):

    data = [
        {
            "satId": "sat:poi:abc12",
            "wikidata": "Q123",
            "osm": 12345,
            "name": "Example"
        }
    ]

    filename = tmp_path / "concordance.json"
    filename.write_text(json.dumps(data))

    source = SATSource(filename)

    identities = source.identities()

    assert len(identities) == 1

    identity = identities[0]

    assert identity.sat_id == "sat:poi:abc12"
    assert identity.wikidata == "Q123"
    assert identity.osm_id == 12345
    assert identity.name == "Example"    