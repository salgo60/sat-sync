from sat_sync.engine import ReconciliationEngine
from sat_sync.models import Identity
from sat_sync.rules.missing_wikidata import MissingWikidataRule
from sat_sync.rules.base import Rule
from sat_sync.findings import Finding
from sat_sync.rules.codes import FindingCode

def test_engine_runs_rule():

    identities = [
        Identity(
            sat_id="sat:poi:test",
            wikidata=None,
        )
    ]

    engine = ReconciliationEngine(
        rules=[MissingWikidataRule()]
    )

    findings = engine.run(identities)

    assert len(findings) == 1

def test_engine_with_no_rules_returns_no_findings():

    engine = ReconciliationEngine(rules=[])

    findings = engine.run([])

    assert findings == []
    

class DummyRule(Rule):

    @property
    def name(self):
        return "dummy"

    def evaluate(self, identities):
        return [
            Finding(
                code=FindingCode.SAT_WD_001,
                severity="info",
                source="dummy",
                object_id="dummy",
            )
        ]


def test_engine_collects_findings_from_multiple_rules():

    identities = [
        Identity(sat_id="sat:poi:test")
    ]

    engine = ReconciliationEngine(
        rules=[
            DummyRule(),
            DummyRule(),
        ]
    )

    findings = engine.run(identities)

    assert len(findings) == 2