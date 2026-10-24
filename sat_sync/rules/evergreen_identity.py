from sat_sync.evergreen import build_findings
from sat_sync.models import Identity
from sat_sync.rules.base import Rule


class EvergreenIdentityRule(Rule):
    """Reconcile SAT identities against OSM and Wikidata observations."""

    def __init__(self, osm_data: dict, wikidata_assertions: list[dict]):
        self.osm_data = osm_data
        self.wikidata_assertions = wikidata_assertions

    @property
    def name(self) -> str:
        return "evergreen_identity"

    def evaluate(self, identities: list[Identity]) -> list[dict]:
        return build_findings(identities, self.osm_data, self.wikidata_assertions)
