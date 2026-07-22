from sat_sync.findings import Finding
from sat_sync.models import Identity

from .base import Rule
from .codes import FindingCode


class MultipleSourcesWithDifferentIDsRule(Rule):
    """
    Detekterar när samma objekt är katalogiserat i flera källor men med olika SAT ID:n.
    Detta indikerar antingen:
    - Duplicerade objekt i vår databas
    - Fel i externa sources
    - Att ett objekt har två olika SAT ID:n
    """

    @property
    def name(self) -> str:
        return "multiple_sources_different_ids"

    def evaluate(self, identities: list[Identity]) -> list[Finding]:
        """
        Jämför identifierare mellan källor för att hitta inkonsekvenser.
        """
        findings = []

        # Gruppera efter wikidata Q-nummer
        by_wikidata = {}
        for identity in identities:
            if identity.wikidata:
                if identity.wikidata not in by_wikidata:
                    by_wikidata[identity.wikidata] = []
                by_wikidata[identity.wikidata].append(identity)

        # Kolla om samma Wikidata objekt har flera SAT ID:n
        for wikidata_id, sat_identities in by_wikidata.items():
            sat_ids = {id.sat_id for id in sat_identities if id.sat_id}
            if len(sat_ids) > 1:
                # Undvik att lägga till Q två gånger om wikidata_id redan innehåller Q
                if not wikidata_id.startswith("Q"):
                    wikidata_id = f"Q{wikidata_id}"
                findings.append(
                    Finding(
                        code=FindingCode.WD_OSM_001,
                        severity="warning",
                        source="wikidata",
                        object_id=wikidata_id,
                    )
                )

        # Gruppera efter OSM ID
        by_osm = {}
        for identity in identities:
            if identity.osm_id:
                if identity.osm_id not in by_osm:
                    by_osm[identity.osm_id] = []
                by_osm[identity.osm_id].append(identity)

        # Kolla om samma OSM objekt har flera SAT ID:n
        for osm_id, sat_identities in by_osm.items():
            sat_ids = {id.sat_id for id in sat_identities if id.sat_id}
            if len(sat_ids) > 1:
                findings.append(
                    Finding(
                        code=FindingCode.WD_OSM_001,
                        severity="warning",
                        source="osm",
                        object_id=str(osm_id),
                    )
                )

        return findings
