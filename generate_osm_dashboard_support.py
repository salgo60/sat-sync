#!/usr/bin/env python3
"""
Convert OSM elements (with ref:stockholmarchipelagotrail) to dashboard format.
This prepares OSM data for comparison with SAT POI data.
"""

import json
from pathlib import Path
from typing import Optional

OSM_FILE = Path("osm_sat_refs.json")
SAT_POIS_URL = "https://map.stockholmarchipelagotrail.com/data/geojson/pois.geojson"

# Map OSM tags to SAT category
OSM_TO_CATEGORY = {
    "amenity": {
        "cafe": "food",
        "restaurant": "food",
        "bar": "food",
        "fast_food": "food",
        "pub": "food",
        "shop": "shop",
        "supermarket": "shop",
        "gift": "shop",
        "antique": "shop",
        "pharmacy": "shop",
        "post_office": "shop",
        "bank": "shop",
        "toilet": "toilet",
        "bench": "rest",
        "shelter": "shelter",
        "shower": "shower",
        "sauna": "sauna",
        "parking": "rest",
        "picnic_table": "rest",
        "waste_basket": "rest",
    },
    "tourism": {
        "guest_house": "lodging",
        "hostel": "lodging",
        "hotel": "lodging",
        "apartment": "lodging",
        "chalet": "lodging",
        "alpine_hut": "lodging",
        "attraction": "attraction",
        "viewpoint": "viewpoint",
        "picnic_site": "rest",
        "camp_site": "lodging",
        "caravan_site": "lodging",
        "wilderness_hut": "lodging",
    },
    "leisure": {
        "beach": "beach",
        "picnic_table": "rest",
        "playground": "rest",
        "sauna": "sauna",
        "swimming_pool": "water",
    },
    "man_made": {
        "lighthouse": "lighthouse",
        "pier": "harbour",
        "breakwater": "harbour",
    },
    "waterway": {
        "boat_rental": "rowboat",
    },
    "shop": {
        "general": "shop",
        "supermarket": "shop",
        "convenience": "shop",
        "clothes": "shop",
        "books": "shop",
        "food": "shop",
    },
}


def map_osm_to_category(tags: dict) -> str:
    """Map OSM tags to SAT POI category."""
    for tag_type, values in OSM_TO_CATEGORY.items():
        if tag_type in tags:
            tag_value = tags[tag_type]
            if tag_value in values:
                return values[tag_value]
    return "other"


def get_sat_section_for_location(lat: float, lon: float) -> Optional[str]:
    """Map coordinates to SAT section (simplified - uses bounds)."""
    # Stockholm archipelago bounds with approximate section mapping
    # This is simplified; in reality would use more precise boundaries
    sections = {
        "finnhamn": ((59.46, 59.48), (18.78, 18.88)),
        "ingmarso": ((59.48, 59.50), (18.68, 18.78)),
        "moja": ((59.48, 59.52), (18.20, 18.38)),
        "grinda": ((59.38, 59.45), (18.45, 18.65)),
        "sandhamn": ((59.28, 59.38), (18.70, 18.85)),
        "uto": ((59.00, 59.20), (18.65, 18.90)),
        "arholma": ((59.60, 59.68), (18.30, 18.50)),
        "furusund": ((59.62, 59.72), (18.90, 19.10)),
        "landsort": ((58.95, 59.10), (18.70, 18.95)),
        "nattaro": ((59.15, 59.30), (18.50, 18.70)),
        "orno": ((59.35, 59.50), (18.90, 19.10)),
        "svartso": ((59.45, 59.58), (18.15, 18.35)),
    }
    
    for section, ((lat_min, lat_max), (lon_min, lon_max)) in sections.items():
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            return section
    
    return None  # Outside known sections


def convert_osm_to_sat_format(osm_data: dict) -> dict:
    """Convert OSM elements with sat:poi refs to SAT POI format."""
    
    features = []
    
    for elem in osm_data.get("elements", []):
        tags = elem.get("tags", {})
        ref = tags.get("ref:stockholmarchipelagotrail", "")
        
        # Only process sat:poi: references
        if not ref.startswith("sat:poi:"):
            continue
        
        poi_id = ref.replace("sat:poi:", "")
        
        # Extract coordinates
        lat = elem.get("lat")
        lon = elem.get("lon")
        if not lat or not lon:
            continue
        
        # Map to section
        section = get_sat_section_for_location(lat, lon)
        
        # Map to category
        category = map_osm_to_category(tags)
        
        # Extract name
        name = tags.get("name", f"Unknown ({poi_id})")
        
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat]
            },
            "properties": {
                "id": poi_id,
                "name": name,
                "category": category,
                "section": section or "unknown",
                "operator": tags.get("operator") or tags.get("brand") or "",
                "wikidata": tags.get("wikidata") or tags.get("brand:wikidata") or "",
                "website": tags.get("website") or "",
                "phone": tags.get("phone") or "",
                "osmId": f"{elem.get('type')}:{elem.get('id')}",
            }
        }
        
        features.append(feature)
    
    return {
        "type": "FeatureCollection",
        "features": features
    }


def main():
    print("📥 Loading OSM data...")
    osm_data = json.loads(OSM_FILE.read_text())
    
    print("🔄 Converting to SAT format...")
    sat_format_osm = convert_osm_to_sat_format(osm_data)
    
    # Save for dashboard integration
    output_file = Path("osm_sat_format.json")
    output_file.write_text(
        json.dumps(sat_format_osm, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    
    print(f"✅ Conversion complete: {len(sat_format_osm['features'])} POIs")
    print(f"📊 Saved to: {output_file}")
    print("\nSample POI:")
    if sat_format_osm['features']:
        print(json.dumps(sat_format_osm['features'][0], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
