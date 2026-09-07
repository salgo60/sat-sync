from generate_poi_dashboard import sat_object_urls


def test_sat_object_urls_encode_identifier():
    assert sat_object_urls("sat:poi:zz9fn") == (
        "https://map.stockholmarchipelagotrail.com/?sat%3Apoi%3Azz9fn",
        "https://map.stockholmarchipelagotrail.com/api/objects/sat%3Apoi%3Azz9fn",
    )
