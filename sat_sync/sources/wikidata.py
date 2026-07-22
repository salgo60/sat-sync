import json
from urllib.request import urlopen
from urllib.parse import urlencode

from sat_sync.models import Identity


class WikidataSource:
    """
    Hämtar SAT identifierare från Wikidata via Property P14545
    (Stockholm Archipelago Trail ID).
    """

    PROPERTY = "P14545"
    SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

    def identities(self, external_id: str | None = None) -> list[Identity]:
        """
        Hämta SAT identifierare från Wikidata.
        
        Om external_id anges, söks specifikt efter den identifieraren.
        Annars returneras alla objekt med P14545.
        """
        if external_id:
            return self._search_by_external_id(external_id)
        else:
            return self._search_all()

    def _search_by_external_id(self, external_id: str) -> list[Identity]:
        """Söka efter en specifik externa identifierare."""
        query = f"""
        SELECT ?item ?itemLabel ?sat_id WHERE {{
          ?item wdt:P14545 "{external_id}" .
          ?item rdfs:label ?itemLabel .
          FILTER(LANG(?itemLabel) = "sv")
        }}
        LIMIT 1
        """

        result = self._query_wikidata(query)
        identities = []

        for binding in result.get("results", {}).get("bindings", []):
            sat_id = binding.get("sat_id", {}).get("value", "")
            name = binding.get("itemLabel", {}).get("value", "")
            identities.append(
                Identity(
                    sat_id=sat_id,
                    wikidata=binding.get("item", {}).get("value", "").split("/")[-1],
                    name=name,
                )
            )

        return identities

    def _search_all(self, limit: int = 10000) -> list[Identity]:
        """Hämta alla SAT identifierare från Wikidata."""
        query = f"""
        SELECT ?item ?itemLabel ?sat_id WHERE {{
          ?item wdt:P14545 ?sat_id .
          ?item rdfs:label ?itemLabel .
          FILTER(LANG(?itemLabel) = "sv")
        }}
        LIMIT {limit}
        """

        result = self._query_wikidata(query)
        identities = []

        for binding in result.get("results", {}).get("bindings", []):
            sat_id = binding.get("sat_id", {}).get("value", "")
            name = binding.get("itemLabel", {}).get("value", "")
            identities.append(
                Identity(
                    sat_id=sat_id,
                    wikidata=binding.get("item", {}).get("value", "").split("/")[-1],
                    name=name,
                )
            )

        return identities

    def _query_wikidata(self, sparql_query: str) -> dict:
        """Kör en SPARQL-fråga mot Wikidata."""
        params = {
            "query": sparql_query,
            "format": "json",
        }

        url = f"{self.SPARQL_ENDPOINT}?{urlencode(params)}"

        try:
            with urlopen(url) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as e:
            print(f"Fel vid Wikidata-fråga: {e}")
            return {"results": {"bindings": []}}
