from generate_poi_dashboard import (
    POIDashboardGenerator, osm_description_names, poi_display_name, sat_object_urls,
)


def test_sat_object_urls_encode_identifier():
    assert sat_object_urls("sat:poi:zz9fn") == (
        "https://map.stockholmarchipelagotrail.com/?sat%3Apoi%3Azz9fn",
        "https://map.stockholmarchipelagotrail.com/api/objects/sat%3Apoi%3Azz9fn",
    )


def test_osm_description_priority_and_exact_sat_references():
    features = [
        {"properties": {"tags": {
            "ref:stockholmarchipelagotrail": "sat:poi:a; sat:poi:b",
            "description": "Generic description",
        }}},
        {"properties": {"tags": {
            "ref:stockholmarchipelagotrail": "sat:poi:a",
            "description:sv": " Svensk beskrivning ",
        }}},
        {"properties": {"tags": {
            "ref:stockholmarchipelagotrail": "sat:poi:c",
            "description:sv": "  ", "description": "Fallback",
        }}},
        {"properties": {"tags": {"description": "Unlinked"}}},
    ]
    assert osm_description_names(features) == {
        "sat:poi:a": "Svensk beskrivning",
        "sat:poi:b": "Generic description",
        "sat:poi:c": "Fallback",
    }


def test_description_only_replaces_missing_names():
    descriptions = {"sat:poi:a": "OSM description"}
    for missing in (None, "", "   "):
        assert poi_display_name({"id": "sat:poi:a", "name": missing}, descriptions) == "OSM description"
    assert poi_display_name({"id": "sat:poi:a", "name": "Existing"}, descriptions) == "Existing"
    assert poi_display_name({"id": "sat:poi:a", "name_localized": {"sv": "Namn"}}, descriptions) == "Namn"
    assert poi_display_name({"id": "sat:poi:unknown"}, descriptions) == ""


def test_description_is_in_static_table_and_client_data(monkeypatch):
    generator = POIDashboardGenerator(email="test@example.com")
    monkeypatch.setattr(generator, "fetch_latest_pr", lambda: (0, ""))
    description = 'Vatten <källa> & </script><script>alert(1)</script>'
    html = generator.generate_html(
        [{"id": "sat:poi:a", "name": None, "section": "test", "category": "water"}],
        [], {"type": "FeatureCollection", "features": []}, [],
        osm_descriptions={"sat:poi:a": description},
    )
    assert "<td>Vatten &lt;källa&gt; &amp; &lt;/script&gt;" in html
    assert '"name": "Vatten \\u003ckälla>' in html
    assert description not in html
