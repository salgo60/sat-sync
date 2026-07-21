from sat_sync.findings import Finding
from sat_sync.rules.base import Rule
from sat_sync.rules.codes import FindingCode


class MissingInOSMRule(Rule):

    @property
    def name(self):
        return "missing_in_osm"

    def evaluate(self, identities, osm_identifiers):

        findings = []

        for identity in identities:
            if identity.sat_id not in osm_identifiers:
                findings.append(
                    Finding(
                        code=FindingCode.SAT_OSM_001,
                        severity="warning",
                        source="sat",
                        object_id=identity.sat_id,
                    )
                )

        return findings
def test_multiple_static_identifiers_only_missing_create_findings():

    sat = [
        Identity(sat_id="sat:poi:a"),
        Identity(sat_id="sat:poi:b"),
        Identity(sat_id="sat:poi:c"),
    ]

    osm_identifiers = {
        "sat:poi:a",
        "sat:poi:c",
    }

    findings = MissingInOSMRule().evaluate(
        sat,
        osm_identifiers,
    )

    assert len(findings) == 1
    assert findings[0].object_id == "sat:poi:b"