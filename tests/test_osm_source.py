import json

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
