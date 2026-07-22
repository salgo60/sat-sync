from sat_sync.models import Identity
from sat_sync.rules.wikidata_osm_mismatch import WikidataOSMMismatchRule
from sat_sync.rules.codes import FindingCode


def test_wikidata_osm_mismatch_rule_detects_multiple_wikidata_ids():
    """Test att regeln detekterar när samma SAT ID har flera Wikidata ID:n."""
    identities = [
        Identity(sat_id="sat:poi:test01", wikidata="Q123"),
        Identity(sat_id="sat:poi:test01", wikidata="Q456"),  # Samma SAT, olika WD
    ]

    rule = WikidataOSMMismatchRule()
    findings = rule.evaluate(identities)

    assert len(findings) == 1
    assert findings[0].code == FindingCode.WD_OSM_001
    assert findings[0].source == "wikidata"


def test_wikidata_osm_mismatch_rule_detects_multiple_osm_ids():
    """Test att regeln detekterar när samma SAT ID har flera OSM ID:n."""
    identities = [
        Identity(sat_id="sat:poi:test01", osm_id=12345),
        Identity(sat_id="sat:poi:test01", osm_id=67890),  # Samma SAT, olika OSM
    ]

    rule = WikidataOSMMismatchRule()
    findings = rule.evaluate(identities)

    assert len(findings) == 1
    assert findings[0].code == FindingCode.WD_OSM_001
    assert findings[0].source == "osm"


def test_wikidata_osm_mismatch_rule_no_findings_with_consistent_ids():
    """Test att regeln inte flaggar när identifierare är konsistenta."""
    identities = [
        Identity(sat_id="sat:poi:test01", wikidata="Q123", osm_id=12345),
        Identity(sat_id="sat:poi:test02", wikidata="Q456", osm_id=67890),
    ]

    rule = WikidataOSMMismatchRule()
    findings = rule.evaluate(identities)

    assert len(findings) == 0
