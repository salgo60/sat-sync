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
                sat_id=item["sat_id"],
                name=item["name"],
            )
            for item in data
        ]