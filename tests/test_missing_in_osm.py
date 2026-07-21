from sat_sync.models import Identity
from sat_sync.rules.missing_in_osm import MissingInOSMRule


def test_static_sat_identifier_missing_in_osm_creates_finding():

    sat = [
        Identity(sat_id="sat:poi:abc12"),
    ]

    osm_identifiers = set()

    findings = MissingInOSMRule().evaluate(
        sat,
        osm_identifiers,
    )

    assert len(findings) == 1
    assert findings[0].object_id == "sat:poi:abc12"
def test_existing_static_sat_identifier_creates_no_finding():

    sat = [
        Identity(sat_id="sat:poi:abc12"),
    ]

    osm_identifiers = {
        "sat:poi:abc12",
    }

    findings = MissingInOSMRule().evaluate(
        sat,
        osm_identifiers,
    )

    assert findings == []