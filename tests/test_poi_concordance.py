import json
from pathlib import Path

from sat_sync.sources.poi_concordance import POIConcordanceSource


def test_poi_concordance_source_reads_identities(tmp_path):
    """Test att POI concordance källa läser identifierare korrekt."""
    data = {
        "generated": "2024-01-01",
        "license": "CC0-1.0",
        "satIdOf": {
            "grillplatser:G-001": "sat:poi:test01",
            "bad:B-001": "sat:poi:test02",
        }
    }

    filename = tmp_path / "concordance.json"
    filename.write_text(json.dumps(data))

    source = POIConcordanceSource(filename)
    identities = source.identities()

    assert len(identities) == 2
    assert identities[0].sat_id == "sat:poi:test01"
    assert identities[1].sat_id == "sat:poi:test02"


def test_poi_concordance_external_identifiers(tmp_path):
    """Test att externa identifierare kan hämtas."""
    data = {
        "generated": "2024-01-01",
        "license": "CC0-1.0",
        "satIdOf": {
            "grillplatser:G-001": "sat:poi:test01",
            "bad:B-001": "sat:poi:test02",
        }
    }

    filename = tmp_path / "concordance.json"
    filename.write_text(json.dumps(data))

    source = POIConcordanceSource(filename)
    external_ids = source.external_identifiers()

    assert "grillplatser:G-001" in external_ids
    assert "bad:B-001" in external_ids
    assert external_ids["grillplatser:G-001"] == "sat:poi:test01"
    assert external_ids["bad:B-001"] == "sat:poi:test02"
