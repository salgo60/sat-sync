#!/usr/bin/env python3
<<<<<<< HEAD
"""Convert OSM PostPass objects WITHOUT sat:/shr: refs to SAT POI candidates.

Objects that already have ref:stockholmarchipelagotrail = sat:poi:xxx / sat:pier:xxx /
sat:section:xxx are already tracked in the SAT system — skip them.
Objects with shr:xxx are AEDs from Hjärtstartarregistret — also skip them.
=======
"""Convert OSM PostPass objects WITHOUT sat: refs to SAT POI candidates.

Objects that already have ref:stockholmarchipelagotrail = sat:poi:xxx / sat:pier:xxx /
sat:section:xxx are already tracked in the SAT system — skip them.
>>>>>>> origin/main
Also skip objects whose OSM node IDs appear in SAT's piers or AED datasets.
Only include objects that are genuinely untracked in SAT.
"""
import json
import urllib.request
from pathlib import Path

INPUT_FILE = Path("osm_postpass_data.json")
OUTPUT_FILE = Path("osm_candidates.json")
HEADERS = {"User-Agent": "sat-sync/1.0 (+https://github.com/salgo60/sat-sync)"}

if not INPUT_FILE.exists():
    print(f"❌ {INPUT_FILE} not found")
    exit(1)

print(f"📥 Loading {INPUT_FILE}...")
osm_data = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
features = osm_data.get("features", [])
print(f"📊 {len(features)} OSM objects from PostPass")

# Fetch OSM node IDs that are already tracked as piers
pier_osm_ids: set[str] = set()
try:
    req = urllib.request.Request(
        "https://map.stockholmarchipelagotrail.com/data/piers-identity.json",
        headers=HEADERS,
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        piers = json.load(r)
    # piers don't embed OSM IDs directly — they're already filtered by sat:pier: prefix
    print(f"  ℹ️  Piers: {len(piers)} (excluded via sat:pier: prefix in ref tag)")
except Exception as e:
    print(f"  ⚠️  Could not fetch piers: {e}")

# Fetch OSM node IDs already tracked as AEDs
aed_osm_ids: set[str] = set()
try:
    req = urllib.request.Request(
        "https://map.stockholmarchipelagotrail.com/api/aed",
        headers=HEADERS,
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        aed_data = json.load(r)
    for f in aed_data.get("features", []):
        osm = f.get("properties", {}).get("osmId", "")
        if osm:
            aed_osm_ids.add(osm.replace("node/", "").replace("way/", ""))
    print(f"  ℹ️  AEDs with OSM IDs: {len(aed_osm_ids)} (will be excluded)")
except Exception as e:
    print(f"  ⚠️  Could not fetch AEDs: {e}")

candidates = []
skipped_no_coords = 0
skipped_already_in_sat = 0
skipped_aed = 0

for feat in features:
    props = feat.get("properties", {})
    tags = props.get("tags", {})
    if not tags and "osm_id" in props:
        tags = props

    coords = feat.get("geometry", {}).get("coordinates", None)
    if not coords or len(coords) < 2 or not coords[0] or not coords[1]:
        skipped_no_coords += 1
        continue

<<<<<<< HEAD
    # Skip objects already tracked in SAT (ref:stockholmarchipelagotrail = sat:... or shr:...)
    sat_ref = tags.get("ref:stockholmarchipelagotrail", "")
    if sat_ref.startswith("sat:") or sat_ref.startswith("shr:"):
=======
    # Skip objects already tracked in SAT (ref:stockholmarchipelagotrail = sat:...)
    sat_ref = tags.get("ref:stockholmarchipelagotrail", "")
    if sat_ref.startswith("sat:"):
>>>>>>> origin/main
        skipped_already_in_sat += 1
        continue

    # Skip AED nodes already tracked via Hjärtstartarregistret
    osm_id_str = str(props.get("osm_id", ""))
    if osm_id_str in aed_osm_ids:
        skipped_aed += 1
        continue

    osm_id = props.get("osm_id", "unknown")

    candidate = {
        "type": "Feature",
        "geometry": feat.get("geometry"),
        "properties": {
            "id": f"osm:{osm_id}",
            "name": tags.get("name") or f"OSM {osm_id}",
            "category": "Övrigt",  # NO mapping — SAT decides categories
            "section": "unknown",
            "operator": tags.get("operator") or tags.get("brand") or "",
            "website": tags.get("website") or "",
            "phone": tags.get("phone") or "",
            "osmId": f"node:{osm_id}",
        },
    }
    candidates.append(candidate)

output = {
    "type": "FeatureCollection",
    "features": candidates,
    "count": len(candidates),
    "source": "OSM (PostPass) - ref:stockholmarchipelagotrail (untracked only)",
}

OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"\n✅ Created {OUTPUT_FILE}:")
print(f"  Total candidates:         {len(candidates)}")
print(f"  Skipped (no coords):      {skipped_no_coords}")
print(f"  Skipped (already in SAT): {skipped_already_in_sat}")
print(f"  Skipped (AED in SAT):     {skipped_aed}")
print(f"  All marked as: Övrigt — SAT decides categories")
