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
