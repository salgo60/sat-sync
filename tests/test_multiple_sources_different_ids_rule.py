from sat_sync.models import Identity
from sat_sync.rules.multiple_sources_different_ids import MultipleSourcesWithDifferentIDsRule
from sat_sync.rules.codes import FindingCode


def test_multiple_sources_different_ids_detects_wikidata_duplicates():
    """Test att regeln detekterar när samma Wikidata ID är länkat till flera SAT ID:n."""
    identities = [
        Identity(sat_id="sat:poi:test01", wikidata="Q123"),
        Identity(sat_id="sat:poi:test02", wikidata="Q123"),  # Samma WD, olika SAT
    ]

    rule = MultipleSourcesWithDifferentIDsRule()
    findings = rule.evaluate(identities)

    assert len(findings) == 1
    assert findings[0].code == FindingCode.WD_OSM_001
    assert findings[0].source == "wikidata"
    assert findings[0].object_id == "Q123"


def test_multiple_sources_different_ids_detects_osm_duplicates():
    """Test att regeln detekterar när samma OSM ID är länkat till flera SAT ID:n."""
    identities = [
        Identity(sat_id="sat:poi:test01", osm_id=12345),
        Identity(sat_id="sat:poi:test02", osm_id=12345),  # Samma OSM, olika SAT
    ]

    rule = MultipleSourcesWithDifferentIDsRule()
    findings = rule.evaluate(identities)

    assert len(findings) == 1
    assert findings[0].code == FindingCode.WD_OSM_001
    assert findings[0].source == "osm"
    assert findings[0].object_id == "12345"


def test_multiple_sources_different_ids_no_findings_with_unique_mapping():
    """Test att regeln inte flaggar när mappningen är unik."""
    identities = [
        Identity(sat_id="sat:poi:test01", wikidata="Q123", osm_id=12345),
        Identity(sat_id="sat:poi:test02", wikidata="Q456", osm_id=67890),
    ]

    rule = MultipleSourcesWithDifferentIDsRule()
    findings = rule.evaluate(identities)

    assert len(findings) == 0


def test_multiple_sources_different_ids_no_findings_without_external_ids():
    """Test att regeln inte flaggar när det saknas externa ID:n."""
    identities = [
        Identity(sat_id="sat:poi:test01"),
        Identity(sat_id="sat:poi:test02"),
    ]

    rule = MultipleSourcesWithDifferentIDsRule()
    findings = rule.evaluate(identities)

    assert len(findings) == 0
