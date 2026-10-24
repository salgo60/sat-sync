import json

from sat_sync.sources.wikidata import WikidataSource


def test_wikidata_source_can_be_instantiated():
    """Test att Wikidata källa kan instansieras."""
    source = WikidataSource()
    assert source is not None


def test_wikidata_source_has_sparql_endpoint():
    """Test att Wikidata källa har rätt SPARQL endpoint."""
    source = WikidataSource()
    assert source.SPARQL_ENDPOINT == "https://query.wikidata.org/sparql"


def test_wikidata_source_has_property():
    """Test att Wikidata källa använder rätt property."""
    source = WikidataSource()
    assert source.PROPERTY == "P14545"


def test_wikidata_query_uses_sparql_json_accept_and_contact_user_agent(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return json.dumps({"results": {"bindings": []}}).encode()

    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return Response()

    monkeypatch.setattr("sat_sync.sources.wikidata.urlopen", fake_urlopen)
    WikidataSource()._query_wikidata("SELECT * WHERE {}")

    request, timeout = requests[0]
    assert request.headers["Accept"] == "application/sparql-results+json"
    assert "salgo60@msn.com" in request.headers["User-agent"]
    assert timeout == 60
