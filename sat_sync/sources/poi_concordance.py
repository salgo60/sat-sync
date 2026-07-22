import json
from urllib.request import urlopen
from pathlib import Path

from sat_sync.models import Identity


class POIConcordanceSource:
    """
    Hämtar SAT identifierare från den officiella POI concordance mappen.
    Källan mappar företags-identifierare (grillplatser:*, bad:*, etc.) till sat_id.
    """

    URL = "https://map.stockholmarchipelagotrail.com/data/geojson/poi-concordance.json"

    def __init__(self, datafile: Path | None = None):
        self.datafile = datafile

    def identities(self) -> list[Identity]:
        """Hämta SAT identifierare från concordance mappen."""
        if self.datafile:
            with open(self.datafile, encoding="utf-8") as f:
                data = json.load(f)
        else:
            with urlopen(self.URL) as response:
                data = json.loads(response.read().decode("utf-8"))

        identities = []
        for external_id, sat_id in data.get("satIdOf", {}).items():
            identities.append(
                Identity(
                    sat_id=sat_id,
                    name=None,
                )
            )

        return identities

    def external_identifiers(self) -> dict[str, str]:
        """Returnera alla externa identifierare mappad till sat_id."""
        if self.datafile:
            with open(self.datafile, encoding="utf-8") as f:
                data = json.load(f)
        else:
            with urlopen(self.URL) as response:
                data = json.loads(response.read().decode("utf-8"))

        return data.get("satIdOf", {})
