#!/usr/bin/env python3
"""
Hämta OSM-data från PostPass (Geofabrik) med SQL API.
PostPass returnerar >900 poster mot 703 från standard Overpass.
"""

import urllib.request
import json
from pathlib import Path
from datetime import datetime
from urllib.parse import urlencode

# PostPass API endpoint
POSTPASS_URL = "https://postpass.geofabrik.de/api/0.2/interpreter"

# SQL Query för PostPass
SQL_QUERY = """
SELECT osm_id, tags, geom
FROM postpass_pointlinepolygon
WHERE tags ? 'ref:stockholmarchipelagotrail'
"""

OUTPUT_FILE = Path("osm_postpass_data.json")


def fetch_postpass_data() -> dict:
    """Hämta data från PostPass via SQL."""
    headers = {
        "User-Agent": "sat-sync/1.0 (+https://github.com/salgo60/sat-sync)",
    }
    
    # PostPass API expects POST with data parameter
    payload = {"data": SQL_QUERY}
    
    req = urllib.request.Request(
        POSTPASS_URL,
        data=urlencode(payload).encode('utf-8'),
        headers=headers,
    )
    
    print("🔍 Hämtar från PostPass (>900 poster)...")
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            result = json.loads(response.read().decode('utf-8'))
        return result
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP {e.code}: {e.reason}")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def main():
    result = fetch_postpass_data()
    
    if not result:
        print("⚠️  Kunde inte hämta data från PostPass")
        return
    
    # PostPass returns GeoJSON directly
    features = result.get('features', [])
    
    if not features:
        print(f"⚠️  Ingen data returnerad. Response: {result.keys()}")
        return
    
    print(f"✅ Hämtade {len(features)} element från PostPass")
    
    # Save as-is (already in GeoJSON format)
    output_data = {
        "type": "FeatureCollection",
        "features": features,
        "count": len(features),
        "source": "PostPass (Geofabrik)",
        "timestamp": datetime.now().isoformat(),
    }
    
    OUTPUT_FILE.write_text(
        json.dumps(output_data, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )
    
    # Count by type
    sat_poi = sum(1 for f in features if 'sat:poi:' in str(f.get('properties', {}).get('ref:stockholmarchipelagotrail', '')))
    sat_pier = sum(1 for f in features if 'sat:pier:' in str(f.get('properties', {}).get('ref:stockholmarchipelagotrail', '')))
    
    print(f"\n📊 Breakdown:")
    print(f"  Total elements: {len(features)}")
    print(f"  SAT POI refs: {sat_poi}")
    print(f"  SAT Pier refs: {sat_pier}")
    print(f"  Other refs: {len(features) - sat_poi - sat_pier}")
    print(f"\n✅ Saved to: {OUTPUT_FILE}")
    print(f"\n📝 Next step:")
    print(f"  python3 generate_osm_dashboard_support.py  # Convert to dashboard format")
    print(f"  python3 generate_poi_dashboard.py          # Regenerate dashboard")


if __name__ == '__main__':
    main()
