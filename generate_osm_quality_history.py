#!/usr/bin/env python3
"""
Analyze SAT POI data quality compared to OSM.
Counts how many SAT POIs are in OSM and their completeness.
"""

import json
from collections import Counter
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional

POIS_URL = "https://map.stockholmarchipelagotrail.com/data/geojson/pois.geojson"
OSM_FILE = Path("osm_sat_refs.json")
OUTPUT_FILE = Path("sat_poi_quality_history.json")

FIELD_ALIASES = {
    "wheelchair": ["wheelchair"],
    "fee": ["fee", "charge"],
    "image": ["image", "photos"],
    "website": ["website"],
    "phone": ["phone", "contact:phone"],
    "operator": ["operator", "brand"],
}


def has_field(tags: dict, aliases: list[str]) -> bool:
    """Check if tags have any of the given field aliases."""
    for field in aliases:
        if field in tags and tags[field]:
            return True
    return False


def percentage(part: int, total: int) -> float:
    """Calculate percentage."""
    if total == 0:
        return 0.0
    return round((part / total) * 100, 1)


def build_osm_snapshot(osm_data: dict, sat_pois: dict) -> dict:
    """Analyze OSM data completeness."""
    
    osm_elements = osm_data.get("elements", [])
    osm_total = len(osm_elements)
    
    # Track SAT POI references in OSM
    sat_poi_in_osm = {}
    field_counter = Counter()
    
    for elem in osm_elements:
        tags = elem.get("tags", {})
        ref = tags.get("ref:stockholmarchipelagotrail", "")
        
        # Only track sat:poi: references (skip piers, etc.)
        if ref.startswith("sat:poi:"):
            poi_id = ref.replace("sat:poi:", "")
            if poi_id not in sat_poi_in_osm:
                sat_poi_in_osm[poi_id] = {"osm_tags": tags}
        
        # Count fields
        for field, aliases in FIELD_ALIASES.items():
            if has_field(tags, aliases):
                field_counter[field] += 1
    
    # Compare with SAT POIs
    matched_with_data = 0
    field_gaps = {field: 0 for field in FIELD_ALIASES}
    
    for poi_id, osm_info in sat_poi_in_osm.items():
        if poi_id in sat_pois:
            matched_with_data += 1
            sat_poi = sat_pois[poi_id]
            osm_tags = osm_info["osm_tags"]
            
            # Check field gaps
            for field, aliases in FIELD_ALIASES.items():
                # Missing in OSM?
                if not has_field(osm_tags, aliases):
                    # Check if it's in SAT
                    field_gaps[field] += 1
    
    field_coverage = {}
    for field in FIELD_ALIASES:
        count = field_counter[field]
        field_coverage[field] = {
            "count": count,
            "percent": percentage(count, osm_total),
            "gaps_vs_sat": field_gaps[field],
        }
    
    now_utc = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    
    return {
        "dataSource": "osm",
        "snapshot_at": now_utc,
        "totalOsmElements": osm_total,
        "satPoiInOsm": {
            "count": len(sat_poi_in_osm),
            "percent": percentage(len(sat_poi_in_osm), 679),  # 679 = total SAT POIs
        },
        "matchedWithValidSatPoi": {
            "count": matched_with_data,
            "percent": percentage(matched_with_data, len(sat_poi_in_osm)) if sat_poi_in_osm else 0,
        },
        "fieldCoverage": field_coverage,
    }


def main():
    print("📥 Loading OSM data from osm_sat_refs.json...")
    if not OSM_FILE.exists():
        print("❌ osm_sat_refs.json not found. Run fetch first.")
        return
    
    osm_data = json.loads(OSM_FILE.read_text(encoding="utf-8"))
    
    print("📥 Loading SAT POI GeoJSON...")
    import urllib.request
    pois_url = "https://map.stockholmarchipelagotrail.com/data/geojson/pois.geojson"
    req = urllib.request.Request(pois_url, headers={"User-Agent": "sat-sync/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        pois_geojson = json.loads(r.read().decode("utf-8"))
    
    # Build SAT POI ID -> properties mapping
    sat_pois = {}
    for feat in pois_geojson.get("features", []):
        props = feat.get("properties", {})
        poi_id = props.get("id")
        if poi_id:
            sat_pois[poi_id] = props
    
    print(f"📊 Analyzing {len(sat_pois)} SAT POIs against OSM...")
    osm_snapshot = build_osm_snapshot(osm_data, sat_pois)
    
    # Load existing quality history
    if OUTPUT_FILE.exists():
        history = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
    else:
        history = {"source": POIS_URL, "versions": []}
    
    # Add OSM snapshot to latest version
    if history.get("versions"):
        latest = history["versions"][-1]
        latest["osmComparison"] = osm_snapshot
    else:
        history["osmComparison"] = osm_snapshot
    
    OUTPUT_FILE.write_text(
        json.dumps(history, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    
    print(f"\n✅ OSM Analysis Complete:")
    print(f"  Total OSM elements: {osm_snapshot['totalOsmElements']}")
    print(f"  SAT POIs in OSM: {osm_snapshot['satPoiInOsm']['count']} ({osm_snapshot['satPoiInOsm']['percent']:.1f}%)")
    print(f"\n✅ Quality history updated: {OUTPUT_FILE}")


if __name__ == '__main__':
    main()
