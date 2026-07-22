from sat_sync.findings import Finding
from sat_sync.models import Identity

from .base import Rule
from .codes import FindingCode


class WikidataOSMMismatchRule(Rule):
    """
    Detekterar avvikelser mellan Wikidata och OSM identifierare för samma SAT objekt.
    Flaggar när ett SAT ID finns i båda men med olika externa ID:n.
    """

    @property
    def name(self) -> str:
        return "wikidata_osm_mismatch"

    def evaluate(self, identities: list[Identity]) -> list[Finding]:
        """
        Jämför Wikidata och OSM identifierare för samma SAT ID.
        """
        findings = []

        # Gruppera identiteter per sat_id
        by_sat_id = {}
        for identity in identities:
            if identity.sat_id not in by_sat_id:
                by_sat_id[identity.sat_id] = []
            by_sat_id[identity.sat_id].append(identity)

        # Jämför identifierare för samma SAT ID
        for sat_id, sat_identities in by_sat_id.items():
            wikidata_ids = {id.wikidata for id in sat_identities if id.wikidata}
            osm_ids = {id.osm_id for id in sat_identities if id.osm_id}

            # Om samma SAT ID har flera externa ID:n från samma källa
            if len(wikidata_ids) > 1:
                findings.append(
                    Finding(
                        code=FindingCode.WD_OSM_001,
                        severity="warning",
                        source="wikidata",
                        object_id=sat_id,
                    )
                )

            if len(osm_ids) > 1:
                findings.append(
                    Finding(
                        code=FindingCode.WD_OSM_001,
                        severity="warning",
                        source="osm",
                        object_id=sat_id,
                    )
                )

        return findings
