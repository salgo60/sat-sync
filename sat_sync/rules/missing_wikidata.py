from sat_sync.findings import Finding
from sat_sync.models import Identity

from .base import Rule
from .codes import FindingCode


class MissingWikidataRule(Rule):

    @property
    def name(self) -> str:
        return "missing_wikidata"

    def evaluate(self, identities: list[Identity]) -> list[Finding]:

        findings = []

        for identity in identities:
            if identity.wikidata is None:
                findings.append(
                    Finding(
                        code=FindingCode.SAT_WD_001,
                        severity="info",
                        source="sat",
                        object_id=identity.sat_id,
                    )
                )

        return findings