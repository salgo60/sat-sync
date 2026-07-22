from pathlib import Path

from sat_sync.sources.sat import SATSource
from sat_sync.rules.missing_wikidata import MissingWikidataRule
from sat_sync.models import Identity
from sat_sync.rules.codes import FindingCode 

def test_missing_wikidata_creates_finding():

    source = SATSource(Path("tests/data/sat_missing_wikidata.json"))

    identities = source.identities()

    findings = MissingWikidataRule().evaluate(identities)

    assert len(findings) == 1


def test_finding_contains_correct_sat_identifier():

    identities = [
        Identity(
            sat_id="sat:poi:abc123",
            wikidata=None,
        )
    ]

    findings = MissingWikidataRule().evaluate(identities)

    assert len(findings) == 1
    assert findings[0].object_id == "sat:poi:abc123"


def test_multiple_objects_only_missing_create_findings():

    identities = [
        Identity(sat_id="sat:poi:a", wikidata="Q1"),
        Identity(sat_id="sat:poi:b", wikidata=None),
        Identity(sat_id="sat:poi:c", wikidata="Q3"),
        Identity(sat_id="sat:poi:d", wikidata=None),
    ]

    findings = MissingWikidataRule().evaluate(identities)

    assert len(findings) == 2
    assert all(f.code == FindingCode.SAT_WD_001 for f in findings)

    object_ids = {f.object_id for f in findings}
    assert object_ids == {"sat:poi:b", "sat:poi:d"}
    


def test_existing_wikidata_creates_no_finding():

    identities = [
        Identity(
            sat_id="sat:poi:test",
            wikidata="Q12345",
        )
    ]

    findings = MissingWikidataRule().evaluate(identities)

    assert findings == []