from sat_sync.findings import Finding
from sat_sync.models import Identity

from .base import Rule


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
                        rule=self.name,
                        severity="info",
                        source=identity.source,
                        object_id=identity.sat_id,
                        message="Object has no linked Wikidata item.",
                    )
                )

        return findings