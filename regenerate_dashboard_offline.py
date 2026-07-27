#!/usr/bin/env python3
"""Regenerate dashboard offline using cached data."""
import json
from pathlib import Path
from generate_poi_dashboard import POIDashboardGenerator

# Use cached data
generator = POIDashboardGenerator(email="salgo60@msn.com")

# Load cached POI data
pois_data = json.loads(Path("pois_data.json").read_text(encoding="utf-8"))
pois = [
    {
        "id": f["properties"].get("id"),
        "name": f["properties"].get("name"),
        "category": f["properties"].get("category"),
        "lat": f["geometry"]["coordinates"][1],
        "lon": f["geometry"]["coordinates"][0],
    }
    for f in pois_data.get("features", [])
]

stages = json.loads(Path("stages_data.json").read_text(encoding="utf-8")) if Path("stages_data.json").exists() else []
trail = json.loads(Path("trail_data.json").read_text(encoding="utf-8")) if Path("trail_data.json").exists() else {}
sections = json.loads(Path("sections_index_data.json").read_text(encoding="utf-8")) if Path("sections_index_data.json").exists() else []

osm_pois = None
if Path("osm_sat_format.json").exists():
    osm_data = json.loads(Path("osm_sat_format.json").read_text(encoding="utf-8"))
    osm_pois = osm_data.get("features", [])
    print(f"✅ Läste OSM-data: {len(osm_pois)} POI:er")

postpass_pois = None
if Path("osm_postpass_format.json").exists():
    postpass_data = json.loads(Path("osm_postpass_format.json").read_text(encoding="utf-8"))
    postpass_pois = postpass_data.get("features", [])
    print(f"✅ Läste PostPass-data: {len(postpass_pois)} POI:er")

html = generator.generate_html(pois, stages, trail, sections, osm_pois, postpass_pois)
Path("sat_poi_dashboard.html").write_text(html, encoding="utf-8")
print("✅ Dashboard regenererad offline!")
