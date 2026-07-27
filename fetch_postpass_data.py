#!/usr/bin/env python3
"""
Hämta OSM-data från PostPass (Geofabrik) via Overpass Turbo med SQL.
PostPass har bättre indexering än Overpass API och ger >900 poster.
"""

import urllib.request
import json
from pathlib import Path
from datetime import datetime
from urllib.parse import quote

# Overpass API endpoint (routes to PostPass when using SQL syntax)
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# SQL Query för PostPass (via Overpass Turbo syntax)
SQL_QUERY = """
{{data:sql,server=https://postpass.geofabrik.de/api/0.2/}}
SELECT osm_id, tags, geom
FROM postpass_pointlinepolygon
WHERE tags ? 'ref:stockholmarchipelagotrail'
"""

OUTPUT_FILE = Path("osm_postpass_data.json")


def fetch_postpass_data() -> dict:
    """Hämta data från PostPass via Overpass API med SQL."""
    headers = {
        "User-Agent": "sat-sync/1.0 (+https://github.com/salgo60/sat-sync)",
    }
    
    req = urllib.request.Request(
        OVERPASS_URL,
        data=SQL_QUERY.encode('utf-8'),
        headers=headers,
    )
    
    print("🔍 Hämtar från PostPass via Overpass (SQL)...")
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            result = json.loads(response.read().decode('utf-8'))
        return result
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP {e.code}: {e.reason}")
        if e.code == 504:
            print("💡 Timeout - försök igen senare eller använd Overpass Turbo direkt:")
            print("   https://overpass-turbo.eu/?Q=%7B%7Bdata:sql,server=https://postpass.geofabrik.de/api/0.2/%7D%7D")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def main():
    result = fetch_postpass_data()
    
    if not result:
        print("⚠️  Kunde inte hämta data från PostPass")
        return
    
    # PostPass returns data in different formats depending on query type
    # Handle both OSM XML and SQL JSON responses
    rows = result.get('rows', result.get('elements', []))
    
    if not rows:
        print(f"⚠️  Ingen data returnerad. Response keys: {result.keys()}")
        return
    
    print(f"✅ Hämtade {len(rows)} element från PostPass")
    
    # Convert to GeoJSON format
    features = []
    for row in rows:
        # Handle different row formats from PostPass
        if isinstance(row, dict):
            osm_id = row.get('osm_id') or row.get('id')
            tags = row.get('tags', {})
            geom = row.get('geom') or row.get('geometry')
        else:
            continue
        
        if not osm_id or not tags:
            continue
        
        ref = tags.get('ref:stockholmarchipelagotrail', '')
        if not ref:
            continue
        
        # Parse geometry if it's a string (WKT or JSON)
        geometry = None
        if geom:
            try:
                if isinstance(geom, str):
                    geometry = json.loads(geom)
                else:
                    geometry = geom
            except:
                pass
        
        feature = {
            "type": "Feature",
            "osm_id": osm_id,
            "geometry": geometry,
            "properties": {
                "id": ref.replace("sat:poi:", "").replace("sat:pier:", ""),
                "ref": ref,
                "name": tags.get("name", ""),
                **tags  # Include all tags
            }
        }
        
        features.append(feature)
    
    # Save result
    output_data = {
        "type": "FeatureCollection",
        "timestamp": datetime.now().isoformat(),
        "source": "PostPass (Geofabrik)",
        "query": QUERY.strip(),
        "features": features,
        "count": len(features)
    }
    
    OUTPUT_FILE.write_text(
        json.dumps(output_data, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )
    
    print(f"\n📊 Summary:")
    print(f"  Total elements: {len(features)}")
    print(f"  SAT POI refs: {sum(1 for f in features if f['properties']['ref'].startswith('sat:poi:'))}")
    print(f"  SAT Pier refs: {sum(1 for f in features if f['properties']['ref'].startswith('sat:pier:'))}")
    print(f"\n✅ Saved to: {OUTPUT_FILE}")


if __name__ == '__main__':
    main()
