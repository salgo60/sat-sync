from sat_sync.findings import Finding
from sat_sync.models import Identity

from .base import Rule
from .codes import FindingCode


class UnknownSATIdentifierRule(Rule):
    """
    Detekterar SAT identifierare från externa källor som inte finns i vår känd databas.
    Detta kan indikera:
    - En ny SAT identifierare som inte registrerats lokalt än
    - Ett stavfel eller korrupterade data
    """

    def __init__(self, known_sat_ids: set[str] | None = None):
        self.known_sat_ids = known_sat_ids or set()

    @property
    def name(self) -> str:
        return "unknown_sat_identifier"

    def evaluate(self, identities: list[Identity]) -> list[Finding]:
        """
        Flagga SAT identifierare som inte finns i den kända databasen.
        """
        findings = []

        for identity in identities:
            if (
                identity.sat_id
                and self.known_sat_ids
                and identity.sat_id not in self.known_sat_ids
            ):
                findings.append(
                    Finding(
                        code=FindingCode.SAT_UNKOWN_001,
                        severity="info",
                        source="external",
                        object_id=identity.sat_id,
                    )
                )

        return findings
