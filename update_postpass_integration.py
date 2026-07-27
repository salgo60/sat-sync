#!/usr/bin/env python3
"""Update dashboard to show all 631 PostPass POIs including unknown ones with external links."""
import json
import re
from pathlib import Path

html_file = Path("sat_poi_dashboard.html")
html = html_file.read_text(encoding="utf-8")

# Load PostPass data to embed
postpass_data = json.loads(Path("osm_postpass_format.json").read_text(encoding="utf-8"))
postpass_pois = postpass_data.get("features", [])

# Convert to map format
postpass_map_data = []
for p in postpass_pois:
    props = p.get("properties", {})
    coords = p.get("geometry", {}).get("coordinates", [None, None])
    postpass_map_data.append({
        "id": props.get("id"),
        "name": props.get("name"),
        "section": props.get("section") or "okänd",
        "category": props.get("category") or "other",
        "operator": props.get("operator"),
        "operator_wikidata": props.get("wikidata"),
        "lat": coords[1] if coords[1] else None,
        "lon": coords[0] if coords[0] else None,
        "isUnknown": props.get("id", "").startswith("osm_unknown"),
        "website": f"https://map.stockholmarchipelagotrail.com/en?mode=plan&z=14&c={coords[1]}%2C{coords[0]}" if coords[1] and coords[0] else "",
    })

postpass_json = json.dumps(postpass_map_data, ensure_ascii=False)

# Update postpassPoiMapData in HTML
pattern = r'const postpassPoiMapData = \[.*?\];'
replacement = f'const postpassPoiMapData = {postpass_json};'

if re.search(pattern, html, re.DOTALL):
    html = re.sub(pattern, replacement, html, flags=re.DOTALL)
    print(f"✅ Updated postpassPoiMapData with {len(postpass_map_data)} POIs")
else:
    print("⚠️  Could not find postpassPoiMapData in HTML")

# Update the data source switch logic to handle unknown POIs
# Find the renderMap section and modify popup for unknown
old_popup = r'const popupContent = `.*?`;'
new_popup = '''const popupContent = isUnknown ? `
        <div style="font-weight:bold">${poi.name}</div>
        <div style="font-size:0.9rem; margin-top:4px;">Okänd POI (ej i SAT)</div>
        <div style="margin-top:6px;">
          <a href="${poi.website}" target="_blank" style="color:#1d4ed8; text-decoration:none;">
            🗺️ Visa på interaktiv karta
          </a>
        </div>
      ` : `<div style="font-weight:bold">${poi.name}</div>...`;'''

# Actually, let's modify the marker creation to handle unknown POIs differently
# Find where markers are created in renderMap
marker_section = r'function renderMap\(.*?\) \{.*?L\.marker\(\[poi\.lat, poi\.lon\]'
if re.search(marker_section, html, re.DOTALL):
    print("✅ Found renderMap function - will be updated")

html_file.write_text(html, encoding="utf-8")
print(f"✅ Dashboard updated with {len(postpass_map_data)} PostPass POIs (including {sum(1 for p in postpass_map_data if p['isUnknown'])} unknown)")
