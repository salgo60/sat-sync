import pytest

from generate_osm_trail_report import build_report, value_url


def sample_elements():
    return [
        {
            "type": "relation",
            "id": 19012437,
            "members": [{"type": "relation", "ref": 100, "role": ""}],
            "tags": {"type": "superroute", "route": "hiking", "name": "SAT"},
        },
        {
            "type": "relation",
            "id": 100,
            "members": [
                {"type": "way", "ref": 200, "role": ""},
                {"type": "node", "ref": 300, "role": ""},
            ],
            "tags": {
                "type": "route",
                "route": "hiking",
                "name": "SAT Etapp Test",
                "distance": "10 km",
                "ref:stockholmarchipelagotrail": "sat:section:test",
            },
        },
        {
            "type": "way",
            "id": 200,
            "tags": {
                "highway": "track",
                "surface": "compacted",
                "foot": "designated",
            },
        },
        {"type": "node", "id": 300, "tags": {"information": "route_marker"}},
    ]


def test_build_report_preserves_route_hierarchy():
    report = build_report(sample_elements(), "test")

    assert report["sectionCount"] == 1
    assert report["totalMemberships"] == 2
    assert report["uniqueSegmentCount"] == 2
    assert report["sections"][0]["name"] == "SAT Etapp Test"
    assert report["sections"][0]["wayCount"] == 1
    assert report["sections"][0]["nodeCount"] == 1


def test_build_report_calculates_segment_coverage():
    report = build_report(sample_elements(), "test")
    section = report["sections"][0]

    assert section["featureCoverage"]["surface"] == {"count": 1, "percent": 50.0}
    surface = next(stat for stat in report["tagStats"] if stat["key"] == "surface")
    assert surface["count"] == 1
    assert surface["percent"] == 50.0


def test_build_report_requires_superroute():
    with pytest.raises(ValueError, match="19012437"):
        build_report([], "test")


def test_value_urls_link_external_identifiers():
    assert value_url("wikidata", "Q131318799") == (
        "https://www.wikidata.org/wiki/Q131318799"
    )
    assert value_url("wikipedia", "en:Stockholm Archipelago Trail") == (
        "https://en.wikipedia.org/wiki/Stockholm_Archipelago_Trail"
    )
    assert value_url(
        "wikimedia_commons", "Category:Stockholm_Archipelago_Trail"
    ) == "https://commons.wikimedia.org/wiki/Category:Stockholm_Archipelago_Trail"
