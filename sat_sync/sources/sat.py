from pathlib import Path
import json

from sat_sync.models import Identity


class SATSource:

    def __init__(self, datafile: Path):
        self.datafile = datafile

    def identities(self):
        with open(self.datafile, encoding="utf-8") as f:
            data = json.load(f)
        return self.identities_from_data(data)

    @staticmethod
    def identities_from_data(data: dict | list) -> list[Identity]:
        """Normalize a SAT JSON array or POI GeoJSON into reconciliation identities."""
        items = data if isinstance(data, list) else data.get("features", [])
        identities = []
        for item in items:
            props = item.get("properties", item)
            identities.append(
                Identity(
                    sat_id=props.get("id") or props.get("satId") or props.get("sat_id"),
                    name=props.get("name"),
                    wikidata=props.get("wikidata"),
                    osm_id=props.get("osm"),
                )
            )
        return identities