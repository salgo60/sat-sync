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
