import json
import urllib.error

import pytest

import generate_osm_ref_report
from generate_osm_ref_report import build_report, classify, wiki_key_url


def test_classify_requested_categories():
    assert classify({"amenity": "shelter"}) == "Vindskydd"
    assert classify({"amenity": "toilets"}) == "Toalett"
    assert classify({"leisure": "firepit"}) == "Grillplats"
    assert classify({"amenity": "drinking_water"}) == "Dricksvatten"
    assert classify({"tourism": "camp_site"}) == "Tältplats"
    assert classify({"tourism": "hostel"}) == "Boende"
    assert classify({"shop": "supermarket"}) == "Handla mat"
    assert classify({"tourism": "museum"}) == "Museum"
    assert classify({"amenity": "restaurant"}) == "Restaurang / café"
    assert classify({"tourism": "viewpoint"}) == "Utsiktspunkt"
    assert (
        classify({"public_transport": "stop_position", "ferry": "yes"})
        == "Färjeläge"
    )
    assert classify({"place": "island"}) == "Ö / naturplats"
    assert classify({"amenity": "place_of_worship"}) == "Kyrka / kultur"
    assert classify({"leisure": "fitness_station"}) == "Aktivitet"
    assert classify({"shop": "clothes"}) == "Butik övrig"


def test_ferry_terminal_has_priority_over_other_tags():
    tags = {
        "amenity": "ferry_terminal",
        "tourism": "attraction",
        "public_transport": "station",
    }
    assert classify(tags) == "Färjeläge"


def test_build_report_counts_tag_coverage_per_category():
    elements = [
        {
            "type": "node",
            "id": 1,
            "lat": 59.0,
            "lon": 18.0,
            "tags": {
                "amenity": "toilets",
                "name": "A",
                "wheelchair": "yes",
                "ref:stockholmarchipelagotrail": "sat:poi:a",
            },
        },
        {
            "type": "node",
            "id": 2,
            "lat": 59.1,
            "lon": 18.1,
            "tags": {
                "amenity": "toilets",
                "name": "B",
                "ref:stockholmarchipelagotrail": "sat:poi:b",
            },
        },
    ]

    report = build_report(elements, "test")
    category = report["categories"][0]
    wheelchair = next(stat for stat in category["tagStats"] if stat["key"] == "wheelchair")

    assert report["totalObjects"] == 2
    assert category["name"] == "Toalett"
    assert wheelchair["count"] == 1
    assert wheelchair["percent"] == 50.0
    assert wheelchair["wikiUrl"] == wiki_key_url("wheelchair")


def test_fetch_rejects_empty_overpass_response(monkeypatch):
    class EmptyResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return json.dumps({"elements": []}).encode()

    monkeypatch.setattr(
        generate_osm_ref_report.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: EmptyResponse(),
    )

    with pytest.raises(RuntimeError, match="tomt resultat"):
        generate_osm_ref_report.fetch_osm_elements()
