from pathlib import Path
import json

from sat_sync.models import Identity


class SATSource:

    def __init__(self, datafile: Path):
        self.datafile = datafile

    def identities(self):
        with open(self.datafile, encoding="utf-8") as f:
            data = json.load(f)

        return [
            Identity(
                sat_id=item.get("satId") or item.get("sat_id"),
                name=item.get("name"),
                wikidata=item.get("wikidata"),
                osm_id=item.get("osm"),
            )
            for item in data
        ]