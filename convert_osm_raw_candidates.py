#!/usr/bin/env python3
"""Convert ALL OSM PostPass objects to SAT POI candidates without category mapping."""
import json
from pathlib import Path

INPUT_FILE = Path("osm_postpass_data.json")
OUTPUT_FILE = Path("osm_candidates.json")

if not INPUT_FILE.exists():
    print(f"❌ {INPUT_FILE} not found")
    exit(1)

print(f"📥 Loading {INPUT_FILE}...")
osm_data = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
features = osm_data.get("features", [])

print(f"📊 Processing {len(features)} OSM objects from PostPass...")

candidates = []
skipped = 0

for feat in features:
    props = feat.get("properties", {})
    tags = props.get("tags", {})
    if not tags and "osm_id" in props:
        tags = props
    
    coords = feat.get("geometry", {}).get("coordinates", None)
    if not coords or len(coords) < 2 or not coords[0] or not coords[1]:
        skipped += 1
        continue
    
    osm_id = props.get("osm_id", "unknown")
    
    candidate = {
        "type": "Feature",
        "geometry": feat.get("geometry"),
        "properties": {
            "id": f"osm:{osm_id}",
            "name": tags.get("name") or f"OSM {osm_id}",
            "category": "Övrigt",  # NO mapping
            "section": "unknown",
            "operator": tags.get("operator") or tags.get("brand") or "",
            "website": tags.get("website") or "",
            "phone": tags.get("phone") or "",
            "osmId": f"node:{osm_id}",
        }
    }
    candidates.append(candidate)

output = {
    "type": "FeatureCollection",
    "features": candidates,
    "count": len(candidates),
    "source": "OSM (PostPass) - ref:stockholmarchipelagotrail"
}

OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"\n✅ Created {OUTPUT_FILE}:")
print(f"  Total candidates: {len(candidates)}")
print(f"  Skipped (no coords): {skipped}")
print(f"  All marked as: Övrigt (Misc)")
