from sat_sync.models import Identity
from sat_sync.rules.unknown_sat_identifier import UnknownSATIdentifierRule
from sat_sync.rules.codes import FindingCode


def test_unknown_sat_identifier_rule_flags_unknown_ids():
    """Test att regeln flaggar okända SAT ID:n."""
    known_ids = {"sat:poi:known1", "sat:poi:known2"}
    identities = [
        Identity(sat_id="sat:poi:known1"),
        Identity(sat_id="sat:poi:unknown1"),  # Okänd
        Identity(sat_id="sat:poi:unknown2"),  # Okänd
    ]

    rule = UnknownSATIdentifierRule(known_sat_ids=known_ids)
    findings = rule.evaluate(identities)

    assert len(findings) == 2
    assert all(f.code == FindingCode.SAT_UNKOWN_001 for f in findings)
    object_ids = {f.object_id for f in findings}
    assert object_ids == {"sat:poi:unknown1", "sat:poi:unknown2"}


def test_unknown_sat_identifier_rule_no_findings_for_known_ids():
    """Test att regeln inte flaggar när alla ID:n är kända."""
    known_ids = {"sat:poi:known1", "sat:poi:known2"}
    identities = [
        Identity(sat_id="sat:poi:known1"),
        Identity(sat_id="sat:poi:known2"),
    ]

    rule = UnknownSATIdentifierRule(known_sat_ids=known_ids)
    findings = rule.evaluate(identities)

    assert len(findings) == 0


def test_unknown_sat_identifier_rule_no_findings_without_known_ids():
    """Test att regeln inte flaggar utan känd databas."""
    identities = [
        Identity(sat_id="sat:poi:test1"),
        Identity(sat_id="sat:poi:test2"),
    ]

    rule = UnknownSATIdentifierRule()  # Ingen känd databas
    findings = rule.evaluate(identities)

    assert len(findings) == 0
