import json
import urllib.error

from sat_sync.sources.osm import OSMSource


def test_osm_source_can_be_instantiated():
    """Test att OSM källa kan instansieras."""
    source = OSMSource()
    assert source is not None


def test_osm_source_has_overpass_api():
    """Test att OSM källa har rätt Overpass API endpoint."""
    source = OSMSource()
    assert source.OVERPASS_API == "https://overpass-api.de/api/interpreter"


def test_osm_source_has_tag():
    """Test att OSM källa använder rätt tagg."""
    source = OSMSource()
    assert source.TAG == "ref:stockholmarchipelagotrail"


def test_object_types_resolves_numeric_ids_without_assuming_their_type(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return json.dumps(
                {"elements": [{"type": "way", "id": 123}, {"type": "node", "id": 456}]}
            ).encode()

    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return Response()

    monkeypatch.setattr("sat_sync.sources.osm.urlopen", fake_urlopen)
    resolved = OSMSource().object_types([123, 456, True])

    assert resolved == {123: ["way"], 456: ["node"]}
    assert b"nwr(id:123,456)" in requests[0][0].data
    assert requests[0][1] == 90
    assert requests[0][0].headers["Accept"] == "application/json"
    assert "salgo60@msn.com" in requests[0][0].headers["User-agent"]


def test_object_types_retries_temporary_gateway_errors(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return json.dumps({"elements": [{"type": "way", "id": 123}]}).encode()

    attempts = []

    def fake_urlopen(request, timeout):
        attempts.append(request)
        if len(attempts) == 1:
            raise urllib.error.HTTPError(
                request.full_url, 502, "Bad Gateway", {}, None
            )
        return Response()

    sleeps = []
    monkeypatch.setattr("sat_sync.sources.osm.urlopen", fake_urlopen)
    monkeypatch.setattr("sat_sync.sources.osm.time.sleep", sleeps.append)

    assert OSMSource().object_types([123]) == {123: ["way"]}
    assert len(attempts) == 2
    assert sleeps == [1]
