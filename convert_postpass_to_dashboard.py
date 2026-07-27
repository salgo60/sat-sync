#!/usr/bin/env python3
"""
Konvertera PostPass GeoJSON-export till dashboard-format.
Usage:
  1. Hämta data från Overpass Turbo (PostPass SQL query)
  2. Spara som osm_postpass_data.json
  3. Kör denna scripten
  4. Regenerera dashboard
"""

import json
from pathlib import Path
from typing import Optional

INPUT_FILE = Path("osm_postpass_data.json")
OUTPUT_FILE = Path("osm_postpass_format.json")

OSM_TO_CATEGORY = {
    "amenity": {
        "cafe": "food", "restaurant": "food", "bar": "food",
        "fast_food": "food", "pub": "food", "shop": "shop",
        "supermarket": "shop", "gift": "shop", "antique": "shop",
        "pharmacy": "shop", "post_office": "shop", "bank": "shop",
        "toilet": "toilet", "bench": "rest", "shelter": "shelter",
        "shower": "shower", "sauna": "sauna", "parking": "rest",
        "picnic_table": "rest", "waste_basket": "rest",
    },
    "tourism": {
        "guest_house": "lodging", "hostel": "lodging", "hotel": "lodging",
        "apartment": "lodging", "chalet": "lodging", "alpine_hut": "lodging",
        "attraction": "attraction", "viewpoint": "viewpoint",
        "picnic_site": "rest", "camp_site": "lodging", "caravan_site": "lodging",
        "wilderness_hut": "lodging",
    },
    "leisure": {
        "beach": "beach", "picnic_table": "rest", "playground": "rest",
        "sauna": "sauna", "swimming_pool": "water",
    },
    "man_made": {
        "lighthouse": "lighthouse", "pier": "harbour",
        "breakwater": "harbour",
    },
    "waterway": {
        "boat_rental": "rowboat",
    },
    "shop": {
        "general": "shop", "supermarket": "shop", "convenience": "shop",
        "clothes": "shop", "books": "shop", "food": "shop",
    },
}

# Section boundaries (approximation)
SECTION_BOUNDS = {
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


def map_osm_to_category(tags: dict) -> str:
    """Map OSM tags to SAT POI category."""
    for tag_type, values in OSM_TO_CATEGORY.items():
        if tag_type in tags:
            tag_value = tags[tag_type]
            if tag_value in values:
                return values[tag_value]
    return "other"


def get_section_for_location(lat: float, lon: float) -> Optional[str]:
    """Map coordinates to SAT section."""
    if not lat or not lon:
        return None
    
    for section, ((lat_min, lat_max), (lon_min, lon_max)) in SECTION_BOUNDS.items():
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            return section
    return None


def convert_postpass_geojson(input_file: Path) -> dict:
    """Konvertera PostPass GeoJSON till dashboard-format."""
    
    if not input_file.exists():
        print(f"❌ {input_file} not found")
        return {"features": []}
    
    print(f"📥 Loading {input_file}...")
    geojson = json.loads(input_file.read_text(encoding="utf-8"))
    
    features = geojson.get("features", [])
    print(f"📊 Processing {len(features)} features...")
    
    converted = []
    
    for feat in features:
        props = feat.get("properties", {})
        ref = props.get("ref:stockholmarchipelagotrail") or props.get("ref", "")
        
        if not ref or not ref.startswith("sat:poi:"):
            continue
        
        poi_id = ref.replace("sat:poi:", "")
        
        # Extract coordinates
        coords = feat.get("geometry", {}).get("coordinates", [None, None])
        if not coords or len(coords) < 2:
            continue
        
        lon, lat = coords[0], coords[1]
        
        # Map to category and section
        category = map_osm_to_category(props)
        section = get_section_for_location(lat, lon)
        
        if not section:
            section = "unknown"
        
        converted_feat = {
            "type": "Feature",
            "geometry": feat.get("geometry"),
            "properties": {
                "id": poi_id,
                "name": props.get("name", f"POI {poi_id}"),
                "category": category,
                "section": section,
                "operator": props.get("operator") or props.get("brand") or "",
                "operator_wikidata": props.get("wikidata") or props.get("brand:wikidata") or "",
                "website": props.get("website") or "",
                "phone": props.get("phone") or "",
                "osmId": f"node:{props.get('osm_id', 'unknown')}",
            }
        }
        
        converted.append(converted_feat)
    
    return {
        "type": "FeatureCollection",
        "features": converted,
        "count": len(converted),
        "source": "PostPass (Geofabrik)",
    }


def main():
    result = convert_postpass_geojson(INPUT_FILE)
    
    if not result["features"]:
        print("⚠️  No features converted")
        return
    
    # Save converted data
    OUTPUT_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    
    print(f"\n✅ Conversion complete:")
    print(f"  Input: {len(result['features'])} POIs")
    print(f"  Output: {OUTPUT_FILE}")
    print(f"\n📝 Next step:")
    print(f"  1. python3 generate_poi_dashboard.py")
    print(f"  2. Dashboard will now include PostPass data source")


if __name__ == '__main__':
    main()
