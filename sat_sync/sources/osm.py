import json
from urllib.request import urlopen
from urllib.parse import urlencode

from sat_sync.models import Identity


class OSMSource:
    """
    Hämtar SAT identifierare från OpenStreetMap via taggen ref:stockholmarchipelagotrail.
    Använder Overpass API för sökning.
    """

    OVERPASS_API = "https://overpass-api.de/api/interpreter"
    TAG = "ref:stockholmarchipelagotrail"

    def identities(self, external_id: str | None = None) -> list[Identity]:
        """
        Hämta SAT identifierare från OSM.
        
        Om external_id anges, söks specifikt efter den identifieraren.
        """
        if external_id:
            return self._search_by_external_id(external_id)
        else:
            return self._search_all()

    def _search_by_external_id(self, external_id: str) -> list[Identity]:
        """Söka efter en specifik SAT identifierare i OSM."""
        query = f"""
        [bbox:-1,-1,1,1];
        (
          node["{self.TAG}"="{external_id}"];
          way["{self.TAG}"="{external_id}"];
          relation["{self.TAG}"="{external_id}"];
        );
        out center;
        """

        result = self._query_overpass(query)
        identities = []

        for element in result.get("elements", []):
            tags = element.get("tags", {})
            sat_id = tags.get(self.TAG, "")
            name = tags.get("name", "")

            if sat_id:
                identities.append(
                    Identity(
                        sat_id=sat_id,
                        osm_id=element.get("id"),
                        name=name if name else None,
                    )
                )

        return identities

    def _search_all(self) -> list[Identity]:
        """Hämta alla SAT identifierare från OSM."""
        query = f"""
        [bbox:-1,-1,1,1];
        (
          node["{self.TAG}"];
          way["{self.TAG}"];
          relation["{self.TAG}"];
        );
        out center;
        """

        result = self._query_overpass(query)
        identities = []

        for element in result.get("elements", []):
            tags = element.get("tags", {})
            sat_id = tags.get(self.TAG, "")
            name = tags.get("name", "")

            if sat_id:
                identities.append(
                    Identity(
                        sat_id=sat_id,
                        osm_id=element.get("id"),
                        name=name if name else None,
                    )
                )

        return identities

    def _query_overpass(self, query: str) -> dict:
        """Kör en Overpass API-fråga."""
        data = query.encode("utf-8")

        try:
            request = urlopen(
                self.OVERPASS_API,
                data=data,
            )
            return json.loads(request.read().decode("utf-8"))
        except Exception as e:
            print(f"Fel vid Overpass API-fråga: {e}")
            return {"elements": []}
