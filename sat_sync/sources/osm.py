import json
import time
import urllib.error
from urllib.request import Request, urlopen
from urllib.parse import urlencode

from sat_sync.models import Identity


class OSMSource:
    """
    Hämtar SAT identifierare från OpenStreetMap via taggen ref:stockholmarchipelagotrail.
    Använder Overpass API för sökning.
    """

    OVERPASS_API = "https://overpass-api.de/api/interpreter"
    TAG = "ref:stockholmarchipelagotrail"
    USER_AGENT = "sat-sync/1.0 (+https://github.com/salgo60/sat-sync; salgo60@msn.com)"
    RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}

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

    def object_types(self, osm_ids: list[int]) -> dict[int, list[str]]:
        """Resolve object types for numeric OSM IDs without assuming geometry type."""
        ids = sorted(
            {osm_id for osm_id in osm_ids if isinstance(osm_id, int) and not isinstance(osm_id, bool)}
        )
        object_types: dict[int, list[str]] = {}
        for start in range(0, len(ids), 300):
            id_list = ",".join(str(osm_id) for osm_id in ids[start : start + 300])
            query = f"[out:json][timeout:60];nwr(id:{id_list});out ids;"
            request = Request(
                self.OVERPASS_API,
                data=query.encode("utf-8"),
                headers={
                    "Accept": "application/json",
                    "User-Agent": self.USER_AGENT,
                },
            )
            for attempt in range(3):
                try:
                    with urlopen(request, timeout=90) as response:
                        result = json.loads(response.read().decode("utf-8"))
                    break
                except urllib.error.HTTPError as error:
                    if error.code not in self.RETRYABLE_HTTP_CODES or attempt == 2:
                        raise
                    time.sleep(2**attempt)
                except (TimeoutError, urllib.error.URLError):
                    if attempt == 2:
                        raise
                    time.sleep(2**attempt)
            for element in result.get("elements", []):
                object_types.setdefault(element["id"], []).append(element["type"])
        return object_types

    def _query_overpass(self, query: str) -> dict:
        """Kör en Overpass API-fråga."""
        data = query.encode("utf-8")

        try:
            request = Request(
                self.OVERPASS_API,
                data=data,
                headers={
                    "Accept": "application/json",
                    "User-Agent": self.USER_AGENT,
                },
            )
            with urlopen(request, timeout=90) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as e:
            print(f"Fel vid Overpass API-fråga: {e}")
            return {"elements": []}
