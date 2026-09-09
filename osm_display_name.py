"""Display labels for unnamed OSM candidates, without changing OSM data."""


def osm_display_name(tags: dict, osm_id: str) -> str:
    for key in ("name", "description:sv", "description"):
        value = tags.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    # Prefer object-defining tags over attributes such as access or wheelchair.
    for key in ("emergency", "tourism", "amenity", "leisure", "historic",
                "shop", "natural", "man_made", "waterway", "highway"):
        value = tags.get(key)
        if isinstance(value, str) and value.strip() and value.strip() != "no":
            return f"{key}={value.strip()}"
    return f"OSM {osm_id}"
