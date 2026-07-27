#!/usr/bin/env python3
"""Fetch all 910 OSM objects with ref:stockholmarchipelagotrail."""
import json
import urllib.request
from pathlib import Path

# Overpass API query for ALL objects with the ref tag
query = """
[bbox:58.7,17.8,60.0,19.5];
(
  node["ref:stockholmarchipelagotrail"];
  way["ref:stockholmarchipelagotrail"];
  relation["ref:stockholmarchipelagotrail"];
);
out geom;
"""

overpass_url = "https://overpass-api.de/api/interpreter"

print("📥 Querying Overpass API for all ref:stockholmarchipelagotrail objects...")

req = urllib.request.Request(overpass_url, data=query.encode('utf-8'))
try:
    with urllib.request.urlopen(req, timeout=60) as response:
        osm_json = json.loads(response.read().decode('utf-8'))
    print(f"✅ Got {len(osm_json.get('elements', []))} OSM elements")
    
    # Convert to GeoJSON
    features = []
    for elem in osm_json.get('elements', []):
        if elem.get('type') == 'node':
            feat = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [elem['lon'], elem['lat']]
                },
                "properties": {
                    "osm_id": elem['id'],
                    "osm_type": "node",
                    **elem.get('tags', {})
                }
            }
            features.append(feat)
        elif elem.get('type') == 'way':
            if 'center' in elem:
                feat = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [elem['center']['lon'], elem['center']['lat']]
                    },
                    "properties": {
                        "osm_id": elem['id'],
                        "osm_type": "way",
                        **elem.get('tags', {})
                    }
                }
                features.append(feat)
    
    geojson = {
        "type": "FeatureCollection",
        "features": features
    }
    
    Path("osm_all_candidates.json").write_text(json.dumps(geojson, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"✅ Saved {len(features)} features to osm_all_candidates.json")
    
except urllib.error.HTTPError as e:
    print(f"❌ HTTP Error: {e}")
except Exception as e:
    print(f"❌ Error: {e}")
